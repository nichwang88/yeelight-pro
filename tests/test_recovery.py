"""Recovery regressions using in-memory streams; run with unittest on HA Python."""
import asyncio
import json
import unittest
from unittest.mock import patch

from custom_components.yeelight_pro import XEntity
from custom_components.yeelight_pro.binary_sensor import XBinarySensorEntity
from custom_components.yeelight_pro.core.device import GatewayDevice, XDevice
from custom_components.yeelight_pro.core.gateway import ProGateway

NODE = {'id': 301931871, 'nt': 2, 'type': 129, 'n': 'test sensor'}


class Entity(XEntity):
    def __init__(self, device, conv):
        super().__init__(device, conv)
        self.states = []

    def async_set_state(self, data):
        super().async_set_state(data)
        self.states.append(data)


class Reader:
    def __init__(self):
        self.queue = asyncio.Queue()

    async def readline(self):
        return await self.queue.get()

    def feed(self, data):
        self.queue.put_nowait(json.dumps(data).encode() + b'\r\n')


class Writer:
    def __init__(self, reader, drop_topologies=0):
        self.reader = reader
        self.drop_topologies = drop_topologies
        self.commands = []
        self.closed = False

    def write(self, raw):
        command = json.loads(raw)
        self.commands.append(command)
        if command['method'] == 'gateway_get.topology':
            if self.drop_topologies:
                self.drop_topologies -= 1
            else:
                self.reader.feed({'method': 'gateway_post.topology', 'nodes': [NODE]})
        elif command['method'] == 'gateway_get.node':
            self.reader.feed({'id': command['id'], 'nodes': [{**NODE, 'params': {'mv': True}, 'o': True}]})

    async def drain(self):
        pass

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.gateways = []

    async def asyncTearDown(self):
        for gateway in self.gateways:
            await gateway.stop()

    def gateway(self, **options):
        gateway = ProGateway('test.invalid', **options)
        gateway.add_setup('binary_sensor', lambda device, conv: Entity(device, conv))
        self.gateways.append(gateway)
        return gateway

    async def test_property_before_topology_has_parent_and_entity(self):
        gateway = self.gateway()
        await gateway.on_message(json.dumps({'method': 'gateway_post.prop', 'nodes': [{**NODE, 'params': {'mv': True}}]}).encode())
        device = gateway.devices[NODE['id']]
        self.assertIsNotNone(gateway.device)
        self.assertEqual(device.entities['motion'].states[-1]['motion'], True)

    async def test_cached_failed_entity_is_retried(self):
        gateway = self.gateway()
        gateway.device = GatewayDevice(gateway)
        # Use the proper class, with a deliberately missing entity after setup.
        device = await XDevice.from_node(gateway, NODE)
        device.entities.clear()
        await XDevice.from_node(gateway, NODE)
        self.assertIn('motion', device.entities)

    async def test_ready_timeout_does_not_cancel_connection_signal(self):
        gateway = self.gateway(timeout=0.01)
        future = asyncio.get_running_loop().create_future()
        gateway._msgs['ready'] = future
        await gateway.ready()
        self.assertFalse(future.cancelled())

    async def test_eof_closes_stale_writer(self):
        gateway = self.gateway()
        reader = Reader(); writer = Writer(reader)
        gateway.reader = reader; gateway.writer = writer
        reader.queue.put_nowait(b'')
        await gateway.readline()
        self.assertIsNone(gateway.writer)
        self.assertTrue(writer.closed)

    async def test_duplicate_late_reply_does_not_break_message_loop(self):
        gateway = self.gateway()
        future = asyncio.get_running_loop().create_future()
        future.cancel(); gateway._msgs[42] = future
        await gateway.on_message(b'{"id":42}')

    async def test_node_readback_without_method_updates_motion(self):
        gateway = self.gateway()
        await gateway.on_message(json.dumps({'id':42,'nodes':[{**NODE,'params':{'mv':False}}]}).encode())
        self.assertIs(gateway.devices[NODE['id']].entities['motion'].states[-1]['motion'],False)

    async def test_repeated_properties_retry_failed_entity_setup(self):
        gateway=self.gateway()
        device=await XDevice.from_node(gateway,NODE)
        await device.prop_changed({'params':{'mv':True}})
        device.entities.clear()
        await device.prop_changed({'params':{'mv':True}})
        self.assertTrue(device.entities['motion'].states[-1]['motion'])

    async def test_unavailable_restore_does_not_invent_no_motion(self):
        gateway=self.gateway()
        device=await XDevice.from_node(gateway,NODE)
        sensor=XBinarySensorEntity(device,device.converters['motion'])
        sensor.async_restore_last_state('unavailable',{})
        self.assertIsNone(sensor.is_on)
        sensor.async_restore_last_state('on',{})
        self.assertIs(sensor.is_on,True)

    async def test_scene_setup_remains_deduplicated(self):
        gateway=self.gateway();gateway.device=GatewayDevice(gateway);gateway.device.gateways.append(gateway)
        added=[]
        def setup(device,conv):
            added.append(conv.attr);device.entities[conv.attr]=Entity(device,conv)
        gateway.add_setup('button',setup)
        await asyncio.gather(*(gateway.device.add_scene({'id':nid,'nt':6,'n':'scene'}) for nid in [1,2,1,3,2]))
        self.assertEqual(sorted(added),['scene_1','scene_2','scene_3'])

    async def test_control_payload_and_ack_are_preserved(self):
        gateway=self.gateway();reader=Reader()
        class AckWriter(Writer):
            def write(self,raw):
                command=json.loads(raw);self.commands.append(command)
                self.reader.feed({'id':command['id'],'result':['ok']})
        writer=AckWriter(reader);gateway.reader=reader;gateway.writer=writer
        task=asyncio.create_task(gateway.readline())
        nodes=[{'id':1270,'nt':2,'params':{'p':False}}]
        response=await gateway.send('gateway_set.prop',nodes=nodes)
        await task
        self.assertEqual(response['result'],['ok'])
        self.assertEqual(writer.commands[0]['nodes'],nodes)
        self.assertFalse(gateway._msgs)

    async def test_failed_write_cleans_pending_request(self):
        gateway=self.gateway();reader=Reader()
        class BrokenWriter(Writer):
            async def drain(self):raise BrokenPipeError('isolated failure')
        gateway.writer=BrokenWriter(reader)
        with self.assertRaises(BrokenPipeError):
            await gateway.send('gateway_get.node',params={'id':1270})
        self.assertFalse(gateway._msgs)

    async def test_dropped_topology_retries_and_reads_current_motion(self):
        gateway = self.gateway(timeout=0.03)
        reader = Reader(); writer = Writer(reader, drop_topologies=1)
        async def connect(*args, **kwargs):
            return reader, writer
        with patch('asyncio.open_connection', connect):
            await gateway.start()
            for _ in range(100):
                device = gateway.devices.get(NODE['id'])
                entity = device and device.entities.get('motion')
                if entity and entity.states and entity.states[-1].get('motion') is True:
                    break
                await asyncio.sleep(0.02)
            self.assertTrue(entity and entity.states and entity.states[-1].get('motion'))
            self.assertGreaterEqual(sum(x['method']=='gateway_get.topology' for x in writer.commands), 2)
            self.assertTrue(all(x['method'].startswith('gateway_get.') for x in writer.commands))

    async def test_reconnect_requests_topology_again(self):
        gateway = self.gateway(timeout=0.03)
        streams=[]
        async def connect(*args, **kwargs):
            reader=Reader();writer=Writer(reader);streams.append((reader,writer));return reader,writer
        with patch('asyncio.open_connection', connect):
            await gateway.start()
            streams[0][0].queue.put_nowait(b'')
            for _ in range(100):
                if len(streams)>1 and any(x['method']=='gateway_get.topology' for x in streams[1][1].commands):break
                await asyncio.sleep(0.02)
            self.assertGreater(len(streams),1)
            self.assertTrue(any(x['method']=='gateway_get.topology' for x in streams[1][1].commands))


if __name__ == '__main__':
    unittest.main()
