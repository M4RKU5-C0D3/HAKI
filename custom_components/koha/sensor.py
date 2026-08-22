from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .client import Checkout

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities([
        LoanCountSensor(coordinator, entry),
        NextDueSensor(coordinator, entry),
    ])


class KohaBaseSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry: ConfigEntry, key: str, name: str):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Koha Library",
            "manufacturer": "Koha",
        }


class LoanCountSensor(KohaBaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "loans", "Library Loans")

    @property
    def native_value(self):
        checkouts: list[Checkout] = self.coordinator.data
        if checkouts is None:
            return None
        return len(checkouts)

    @property
    def extra_state_attributes(self):
        checkouts: list[Checkout] = self.coordinator.data
        if checkouts is None:
            return {}
        return {
            "checkouts": [
                {
                    "title": c.title,
                    "author": c.author,
                    "due_date": c.due_date.strftime("%d.%m.%Y") if c.due_date else None,
                    "barcode": c.barcode,
                    "item_number": c.item_id,
                    "overdue": c.is_overdue,
                    "due_today": c.is_due_today,
                    "renewals_used": c.renewals_used,
                    "renewals_max": c.renewals_max,
                    "renewals_left": c.renewals_max - c.renewals_used
                    if c.renewals_max is not None and c.renewals_used is not None
                    else None,
                }
                for c in checkouts
            ],
            "overdue_count": sum(1 for c in checkouts if c.is_overdue),
            "due_today_count": sum(1 for c in checkouts if c.is_due_today),
        }


class NextDueSensor(KohaBaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "next_due", "Library Next Due")

    @property
    def native_value(self):
        checkouts: list[Checkout] = self.coordinator.data
        if not checkouts:
            return None
        due_dates = [c.due_date for c in checkouts if c.due_date is not None]
        if not due_dates:
            return None
        return min(due_dates).strftime("%d.%m.%Y")
