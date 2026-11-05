"""The climate platform must not require the legacy-temperature migration."""

import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from homeassistant.const import UnitOfTemperature

from custom_components.yeelight_pro import dr
from custom_components.yeelight_pro.climate import BathHeaterClimateEntity, XClimateEntity
from custom_components.yeelight_pro.core.device import ClimateDevice, GatewayDevice
from custom_components.yeelight_pro.core.gateway import ProGateway


def test_climate_import_uses_supported_temperature_api():
    result = subprocess.run(
        [sys.executable, "-c", "import custom_components.yeelight_pro.climate"],
        capture_output=True, text=True, check=True,
    )
    assert "provides the deprecated" not in result.stderr


@pytest.mark.parametrize("entity_class", [XClimateEntity, BathHeaterClimateEntity])
@pytest.mark.parametrize("display_unit", [UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT])
def test_temperature_updates_use_native_values_without_deprecation(monkeypatch, caplog, entity_class, display_unit):
    hass = SimpleNamespace(config=SimpleNamespace(units=SimpleNamespace(temperature_unit=display_unit)))
    gateway = ProGateway("test.invalid", hass=hass, entry_id="entry")
    gateway.device = GatewayDevice(gateway)
    device = ClimateDevice({"id": 15, "nt": 2, "type": 15, "n": "Climate"})
    device.hass = hass
    device.gateways.append(gateway)
    registry = SimpleNamespace(async_get_device=Mock(return_value=SimpleNamespace(id="parent")))
    monkeypatch.setattr(dr, "async_get", lambda hass: registry)
    entity = entity_class(device, device.converters["climate"])
    entity.async_set_state({"current_temperature": 24.5, "target_temperature": 26})
    assert entity.native_temperature_unit == UnitOfTemperature.CELSIUS
    assert entity.native_current_temperature == 24.5
    assert entity.native_target_temperature == 26
    assert not [record for record in caplog.records if "deprecated" in record.message and "yeelight_pro" in record.message]
