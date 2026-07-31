from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity

from .const import DOMAIN, SCAN_INTERVAL_SECONDS
from .client import KohaClient, Checkout

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    client: KohaClient = hass.data[DOMAIN][entry.entry_id]

    async def _update():
        await client.login()
        return await client.get_checkouts()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=_update,
        update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
    )
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([DueTodayBinarySensor(coordinator, entry)])


class DueTodayBinarySensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_due_today"
        self._attr_name = "Library Due Today"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Koha Library",
            "manufacturer": "Koha",
        }

    @property
    def is_on(self):
        checkouts: list[Checkout] = self.coordinator.data
        if not checkouts:
            return False
        return any(c.is_due_today for c in checkouts)
