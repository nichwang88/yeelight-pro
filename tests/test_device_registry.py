"""Preserve gateway links without the deprecated via_device identifier tuple."""

from types import SimpleNamespace
from unittest.mock import Mock

from custom_components.yeelight_pro import XEntity, dr
from custom_components.yeelight_pro.core.converters.base import Converter
from custom_components.yeelight_pro.core.device import GatewayDevice, XDevice
from custom_components.yeelight_pro.core.gateway import ProGateway


def device():
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_get_entry=lambda entry_id: object()))
    gateway = ProGateway("test.invalid", hass=hass, entry_id="entry")
    gateway.device = GatewayDevice(gateway)
    child = XDevice({"id": 301931871, "nt": 2, "type": 129, "n": "Test sensor"})
    child.hass = hass
    child.gateways.append(gateway)
    return child


def test_mesh_entity_links_existing_gateway_without_changing_identifiers(monkeypatch):
    child = device()
    registry = SimpleNamespace(
        async_get_device=Mock(return_value=SimpleNamespace(id="parent-registry-id")),
        async_get_or_create=Mock(),
    )
    monkeypatch.setattr(dr, "async_get", lambda hass: registry)
    entity = XEntity(child, Converter("motion", "binary_sensor"))
    info = entity.device_info.as_dict()
    assert info.get("via_device_id") == "parent-registry-id"
    assert "via_device" not in info
    assert info["identifiers"] == {("yeelight_pro", 301931871)}
    assert entity.unique_id == "301931871-motion"
    registry.async_get_or_create.assert_not_called()


def test_property_before_gateway_entity_registers_parent_first(monkeypatch):
    child = device()
    registry = SimpleNamespace(
        async_get_device=Mock(return_value=None),
        async_get_or_create=Mock(return_value=SimpleNamespace(id="new-parent-id")),
    )
    monkeypatch.setattr(dr, "async_get", lambda hass: registry)
    entity = XEntity(child, Converter("motion", "binary_sensor"))
    assert entity.device_info.as_dict().get("via_device_id") == "new-parent-id"
    kwargs = registry.async_get_or_create.call_args.kwargs
    assert kwargs["config_entry_id"] == "entry"
    assert kwargs["identifiers"] == {("yeelight_pro", "test.invalid")}


def test_gateway_does_not_link_to_itself(monkeypatch):
    child = device()
    gateway = child.gateway.device
    gateway.hass = child.hass
    registry = Mock()
    monkeypatch.setattr(dr, "async_get", lambda hass: registry)
    entity = XEntity(gateway, Converter("scene", "button"))
    info = entity.device_info.as_dict()
    assert info.get("via_device_id") is None
    assert "via_device" not in info
    registry.async_get_device.assert_not_called()
