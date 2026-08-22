from __future__ import annotations

import logging
from datetime import date, timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERID,
    DOMAIN,
    SCAN_INTERVAL_SECONDS,
    SERVICE_RENEW,
)
from .client import Checkout, KohaClient, KohaRenewError

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CALENDAR]

RENEW_SCHEMA = vol.Schema(
    {
        vol.Optional("config_entry_id"): cv.string,
        vol.Optional("entity_id"): cv.string,
        vol.Exclusive("barcode", "media_target"): cv.string,
        vol.Exclusive("title", "media_target"): cv.string,
    }
)


def _fmt_due(due) -> str | None:
    if isinstance(due, date):
        return due.strftime("%d.%m.%Y")
    return None if due is None else str(due)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration-wide services."""

    async def handle_renew(call: ServiceCall) -> dict:
        barcode: str | None = call.data.get("barcode")
        title: str | None = call.data.get("title")
        if not barcode and not title:
            raise HomeAssistantError(
                "Provide 'barcode' or 'title' of the loan you want to renew"
            )

        runtimes = dict(hass.data.get(DOMAIN, {}))
        entry_id_filter = call.data.get("config_entry_id")
        entity_id_filter = call.data.get("entity_id")
        if entry_id_filter:
            runtimes = {k: v for k, v in runtimes.items() if k == entry_id_filter}
            if not runtimes:
                raise HomeAssistantError(f"Unknown config_entry_id '{entry_id_filter}'")
        elif entity_id_filter:
            registry = er.async_get(hass)
            reg = registry.async_get(entity_id_filter)
            if (
                reg is None
                or reg.platform != DOMAIN
                or reg.config_entry_id not in runtimes
            ):
                raise HomeAssistantError(
                    f"'{entity_id_filter}' is not an entity of this integration"
                )
            runtimes = {reg.config_entry_id: runtimes[reg.config_entry_id]}
        elif len(runtimes) > 1:
            raise HomeAssistantError(
                "Several libraries are configured — specify 'config_entry_id' or 'entity_id'"
            )

        matches: list[tuple[str, Checkout]] = []
        for entry_id, runtime in runtimes.items():
            for checkout in runtime["coordinator"].data or []:
                if barcode is not None:
                    hit = checkout.barcode == barcode
                else:
                    hit = bool(checkout.title) and title.lower() in checkout.title.lower()
                if hit:
                    matches.append((entry_id, checkout))

        if not matches:
            raise HomeAssistantError("No active loan matches the given criteria")
        if len(matches) > 1:
            titles = ", ".join(f"'{c.title}'" for _, c in matches)
            raise HomeAssistantError(
                f"Multiple loans match ({titles}) — narrow it down using 'barcode'"
            )

        entry_id, checkout = matches[0]
        runtime = hass.data[DOMAIN][entry_id]
        old_due = checkout.due_date

        try:
            renewed = await runtime["client"].renew_checkout(checkout.item_id)
        except KohaRenewError as err:
            raise HomeAssistantError(f"Renewal failed: {err}") from err

        if (
            not isinstance(old_due, date)
            or not isinstance(renewed.due_date, date)
            or renewed.due_date <= old_due
        ):
            raise HomeAssistantError(
                f"Renewal rejected by Koha for '{checkout.title}' — the due date did "
                "not move (e.g. too many renewals already used or item on hold)"
            )

        await runtime["coordinator"].async_request_refresh()

        _LOGGER.info(
            "Renewed '%s': due %s -> %s (%s/%s renewals used)",
            renewed.title,
            _fmt_due(old_due),
            _fmt_due(renewed.due_date),
            renewed.renewals_used,
            renewed.renewals_max,
        )
        return {
            "success": True,
            "title": renewed.title,
            "barcode": renewed.barcode,
            "old_due_date": _fmt_due(old_due),
            "new_due_date": _fmt_due(renewed.due_date),
            "renewals_used": renewed.renewals_used,
            "renewals_max": renewed.renewals_max,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_RENEW,
        handle_renew,
        schema=RENEW_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = KohaClient(
        session=session,
        url=entry.data[CONF_URL],
        userid=entry.data[CONF_USERID],
        password=entry.data[CONF_PASSWORD],
    )

    async def _update():
        await client.login()
        return await client.get_checkouts()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{entry.entry_id}",
        update_method=_update,
        update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
