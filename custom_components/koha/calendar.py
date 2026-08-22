from __future__ import annotations

import logging
from datetime import datetime, date

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
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

    async_add_entities([LibraryCalendar(coordinator, entry)])


class LibraryCalendar(CoordinatorEntity, CalendarEntity):
    def __init__(self, coordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_name = "Library"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Koha Library",
            "manufacturer": "Koha",
        }

    @property
    def event(self):
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        checkouts: list[Checkout] = self.coordinator.data
        if not checkouts:
            return []
        events = []
        for c in checkouts:
            if c.due_date is None:
                continue
            due = c.due_date
            if isinstance(due, date) and not isinstance(due, datetime):
                due = datetime.combine(due, datetime.min.time())
            if start_date <= due <= end_date:
                events.append(
                    CalendarEvent(
                        start=due.date(),
                        end=due.date(),
                        summary=f"Due: {c.title}",
                        description=f"{c.title}{' by ' + c.author if c.author else ''}",
                    )
                )
        return events
