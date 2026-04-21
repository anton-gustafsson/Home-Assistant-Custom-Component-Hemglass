"""Hemglass."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import HemglassCoordinator, DOMAIN

PLATFORMS: list[str] = ["sensor", "calendar"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = HemglassCoordinator(
        hass,
        float(entry.data["latitude"]),
        float(entry.data["longitude"]),
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
