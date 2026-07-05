import asyncio

from homeassistant.core import HomeAssistant
from custom_components.yeelight_pro.core.device import GatewayDevice
from custom_components.yeelight_pro.core.gateway import ProGateway


class Hass(HomeAssistant):
    def __init__(self):
        asyncio.get_running_loop = lambda: asyncio.new_event_loop()
        HomeAssistant.__init__(self)
        self.bus.async_fire = self.async_fire
        self.events = []

    def async_fire(self, *args, **kwargs):
        self.events.append(args)


def get_gateway(host=None):
    if not host:
        host = '127.0.0.1'
    return ProGateway(host)


def test_gateway():
    host = '127.0.0.1'
    gtw = get_gateway(host)
    assert gtw.host == host


def test_concurrent_scene_setup_deduplicates_buttons():
    async def run():
        gtw = get_gateway()
        gtw.device = GatewayDevice(gtw)
        gtw.device.gateways.append(gtw)

        added = []

        def setup(device, conv):
            added.append(conv.attr)

            class Entity:
                added = False

            device.entities[conv.attr] = Entity()

        gtw.add_setup('button', setup)

        nodes = [
            {'id': 651155, 'nt': 6, 'n': 'Scene A'},
            {'id': 651175, 'nt': 6, 'n': 'Scene B'},
            {'id': 651155, 'nt': 6, 'n': 'Scene A Duplicate'},
            {'id': 651174, 'nt': 6, 'n': 'Scene C'},
        ]
        await asyncio.gather(*(gtw.device.add_scene(node) for node in nodes))

        assert sorted(added) == ['scene_651155', 'scene_651174', 'scene_651175']
        assert len(added) == len(set(added))

    asyncio.run(run())
