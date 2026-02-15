"""Support for climate."""
import logging

from homeassistant.core import callback
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    DOMAIN as ENTITY_DOMAIN,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
)
from homeassistant.components.climate.const import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    ATTR_FAN_MODE,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    HVACAction,
    HVACMode,
)
from homeassistant.helpers.restore_state import RestoreEntity

from . import (
    XDevice,
    XEntity,
    Converter,
    async_add_setuper,
)

_LOGGER = logging.getLogger(__name__)


def setuper(add_entities):
    def setup(device: XDevice, conv: Converter):
        if not (entity := device.entities.get(conv.attr)):
            if getattr(device, 'is_bath_heater', False):
                entity = BathHeaterClimateEntity(device, conv)
            else:
                entity = XClimateEntity(device, conv)
        if not entity.added:
            add_entities([entity])
    return setup


async def async_setup_entry(hass, config_entry, async_add_entities):
    await async_add_setuper(hass, config_entry, ENTITY_DOMAIN, setuper(async_add_entities))


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    await async_add_setuper(hass, config or discovery_info, ENTITY_DOMAIN, setuper(async_add_entities))


class XClimateEntity(XEntity, ClimateEntity, RestoreEntity):
    def __init__(self, device: XDevice, conv: Converter, option=None):
        super().__init__(device, conv, option)
        self.mode = None
        self.is_on = False

        # https://developers.home-assistant.io/docs/core/entity/climate#supported-features
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
        ]
        self._attr_fan_modes = [
            FAN_LOW,
            FAN_MEDIUM,
            FAN_HIGH,
        ]

        self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
        self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
        self._attr_supported_features |= ClimateEntityFeature.TURN_ON
        self._attr_supported_features |= ClimateEntityFeature.TURN_OFF

        self._attr_hvac_mode = HVACMode.OFF
        self._attr_fan_mode = None
        self._attr_temperature_unit = self.hass.config.units.temperature_unit
        self._attr_target_temperature_step = 1

    @callback
    def async_set_state(self, data: dict):
        for k, v in data.items():
            setattr(self, k, v)
        self._attr_hvac_mode = self.mode if self.is_on else HVACMode.OFF


    @callback
    def async_restore_last_state(self, state: str, attrs: dict):
        pass

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        kwargs['target_temperature'] = kwargs['temperature']
        await self.device_send_props(kwargs)

    async def async_set_hvac_mode(self, hvac_mode, **kwargs):
        """Set new target hvac mode."""
        if HVACMode.OFF == hvac_mode:
            kwargs['is_on'] = False
        else:
            kwargs['is_on'] = True
            kwargs['mode'] = hvac_mode

        await self.device_send_props(kwargs)

    async def async_set_fan_mode(self, fan_mode, **kwargs):
        """Set new target fan mode."""
        kwargs['fan_mode'] = fan_mode
        await self.device_send_props(kwargs)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        kwargs['is_on'] = True
        await self.device_send_props(kwargs)

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        kwargs['is_on'] = False
        await self.device_send_props(kwargs)


class BathHeaterClimateEntity(XEntity, ClimateEntity, RestoreEntity):
    """Climate entity for bath heater (浴霸).

    Bath heaters only support heating (暖风) mode, not cooling or dehumidifying.
    Individual functions (换气/吹风/暖风/干燥) are controlled via separate switch entities.
    This climate entity provides temperature monitoring and on/off control.
    """

    def __init__(self, device: XDevice, conv: Converter, option=None):
        super().__init__(device, conv, option)
        self.is_on = False
        self.bath_heater_mode = 0

        # Also subscribe to bath_heater_mode updates
        self.subscribed_attrs.add('bath_heater_mode')

        # Bath heater only supports OFF and HEAT (暖风)
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.HEAT,
        ]

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

        self._attr_hvac_mode = HVACMode.OFF
        self._attr_temperature_unit = self.hass.config.units.temperature_unit
        self._attr_target_temperature_step = 1
        self._attr_min_temp = 16
        self._attr_max_temp = 40

    @callback
    def async_set_state(self, data: dict):
        if 'is_on' in data:
            self.is_on = data['is_on']
        if 'current_temperature' in data:
            self._attr_current_temperature = data['current_temperature']
        if 'target_temperature' in data:
            self._attr_target_temperature = data['target_temperature']
        if 'bath_heater_mode' in data:
            self.bath_heater_mode = data['bath_heater_mode']
            self._attr_extra_state_attributes['bath_heater_mode'] = data['bath_heater_mode']

        # Determine HVAC mode from power state
        if self.is_on:
            self._attr_hvac_mode = HVACMode.HEAT
        else:
            self._attr_hvac_mode = HVACMode.OFF

    @callback
    def async_restore_last_state(self, state: str, attrs: dict):
        pass

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        kwargs['target_temperature'] = kwargs['temperature']
        await self.device_send_props(kwargs)

    async def async_set_hvac_mode(self, hvac_mode, **kwargs):
        """Set HVAC mode. Only OFF and HEAT are supported."""
        if hvac_mode == HVACMode.OFF:
            kwargs['is_on'] = False
        elif hvac_mode == HVACMode.HEAT:
            kwargs['is_on'] = True
        else:
            _LOGGER.warning('Bath heater does not support mode: %s', hvac_mode)
            return
        await self.device_send_props(kwargs)

    async def async_turn_on(self, **kwargs):
        """Turn the bath heater on."""
        kwargs['is_on'] = True
        await self.device_send_props(kwargs)

    async def async_turn_off(self, **kwargs):
        """Turn the bath heater off."""
        kwargs['is_on'] = False
        await self.device_send_props(kwargs)
