"""Platform for sensor integration."""
from datetime import date

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import HemglassCoordinator, DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator: HemglassCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    name = config_entry.data["name"]
    async_add_entities([
        HemglassSensor(coordinator, name),
        HemglassTruckSensor(coordinator, name),
        HemglassDaysUntilSensor(coordinator, name),
    ])


class HemglassSensor(CoordinatorEntity, Entity):

    def __init__(self, coordinator: HemglassCoordinator, name: str):
        super().__init__(coordinator)
        d = coordinator.data
        self._attr_unique_id = f"{DOMAIN}_{name}_{d['stopLat']}_{d['stopLong']}"
        self._name = name
        self._icon = "mdi:calendar"

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        next_date = self.coordinator.data.get("nextDate", "")
        return next_date.split("T")[0] if next_date else None

    @property
    def icon(self):
        return self._icon

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data
        return {
            "latitude": d["stopLat"],
            "longitude": d["stopLong"],
            "streetAddress": d["streetAddress"],
            "city": d["city"],
            "time": d["nextTime"],
            "ETA": d["eta"],
            "salesman": d["salesMan"],
            "depot": d["depotName"],
            "email": d["depotEmail"],
            "comment": d["comment"],
            "canceled": d["cancelled"],
            "canceledMessage": d["cancelledMessage"],
            "truckIsActiveToday": d["truckIsActiveToday"],
            "truckLocationUpdated": d["truckLocationUpdated"],
            "truckLatitude": d["truckLatitude"],
            "truckLongitude": d["truckLongitude"],
            "truckIsOffTrack": d["truckIsOffTrack"],
            "routeID": d["routeId"],
        }


class HemglassTruckSensor(CoordinatorEntity, Entity):

    def __init__(self, coordinator: HemglassCoordinator, name: str):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.data['routeId']}_truck"
        self._name = f"{name} Truck"
        self._icon = "mdi:calendar"

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self.coordinator.data.get("truckIsActiveToday", False)

    @property
    def icon(self):
        return self._icon

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data
        return {
            "latitude": d["truckLatitude"],
            "longitude": d["truckLongitude"],
            "truckIsActiveToday": d["truckIsActiveToday"],
            "truckLocationUpdated": d["truckLocationUpdated"],
            "truckIsOffTrack": d["truckIsOffTrack"],
            "routeID": d["routeId"],
        }


class HemglassDaysUntilSensor(CoordinatorEntity, Entity):

    def __init__(self, coordinator: HemglassCoordinator, name: str):
        super().__init__(coordinator)
        d = coordinator.data
        self._attr_unique_id = f"{DOMAIN}_{name}_{d['stopLat']}_{d['stopLong']}_days_until"
        self._name = f"{name} Days Until"
        self._icon = "mdi:calendar-clock"

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        next_date = self.coordinator.data.get("nextDate", "")
        if not next_date:
            return None
        try:
            visit = date.fromisoformat(next_date.split("T")[0])
            return (visit - date.today()).days
        except ValueError:
            return None

    @property
    def icon(self):
        return self._icon

    @property
    def unit_of_measurement(self):
        return "days"
