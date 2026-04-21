"""Calendar platform for Hemglass."""
from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import HemglassCoordinator, DOMAIN, STOCKHOLM


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator: HemglassCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([HemglassCalendar(coordinator, config_entry.data["name"])])


class HemglassCalendar(CoordinatorEntity, CalendarEntity):

    def __init__(self, coordinator: HemglassCoordinator, name: str):
        super().__init__(coordinator)
        d = coordinator.data
        self._attr_unique_id = f"{DOMAIN}_calendar_{name}_{d['stopLat']}_{d['stopLong']}"
        self._attr_name = name

    @property
    def event(self) -> CalendarEvent | None:
        # Returns the nearest upcoming event
        future = self.coordinator.data.get("futureDates", [])
        dates = future if future else ([self.coordinator.data.get("nextDate")] if self.coordinator.data.get("nextDate") else [])
        return self._build_event(dates[0]) if dates else None

    async def async_get_events(self, hass, start_date: datetime, end_date: datetime):
        d = self.coordinator.data
        future = d.get("futureDates", [])
        if not future and d.get("nextDate"):
            future = [d["nextDate"]]

        if start_date.tzinfo is None:
            start_date = STOCKHOLM.localize(start_date)
        if end_date.tzinfo is None:
            end_date = STOCKHOLM.localize(end_date)

        events = []
        for raw_date in future:
            ev = self._build_event(raw_date)
            if ev is None:
                continue
            ev_start = ev.start if isinstance(ev.start, datetime) else datetime.combine(ev.start, datetime.min.time()).replace(tzinfo=STOCKHOLM)
            ev_end = ev.end if isinstance(ev.end, datetime) else datetime.combine(ev.end, datetime.min.time()).replace(tzinfo=STOCKHOLM)
            if ev_start < end_date and ev_end > start_date:
                events.append(ev)
        return events

    def _build_event(self, raw_date: str) -> CalendarEvent | None:
        if not raw_date:
            return None
        d = self.coordinator.data
        try:
            date_part = raw_date.split("T")[0] if "T" in raw_date else raw_date
            time_part = raw_date.split("T")[1][:8] if "T" in raw_date else d.get("nextTime", "")
            if time_part:
                start_dt = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M:%S")
            else:
                start_dt = datetime.strptime(date_part, "%Y-%m-%d").replace(hour=8, minute=0)
            start_dt = STOCKHOLM.localize(start_dt)
        except (ValueError, AttributeError):
            return None

        cancelled = d.get("cancelled", False)
        description_parts = [p for p in [d.get("salesMan"), d.get("comment")] if p]
        if cancelled and d.get("cancelledMessage"):
            description_parts.append(f"Cancelled: {d['cancelledMessage']}")
        location = ", ".join(p for p in [d.get("streetAddress"), d.get("city")] if p) or None

        return CalendarEvent(
            start=start_dt,
            end=start_dt + timedelta(hours=1),
            summary=f"{self._attr_name} (Cancelled)" if cancelled else self._attr_name,
            description="\n".join(description_parts) if description_parts else None,
            location=location,
        )
