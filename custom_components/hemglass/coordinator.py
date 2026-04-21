"""Hemglass data coordinator."""
import logging
from datetime import date, datetime, timedelta
from pytz import timezone

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)
STOCKHOLM = timezone("Europe/Stockholm")
DOMAIN = "hemglass"
UPDATE_INTERVAL = timedelta(minutes=5)


def replace_nulls_with_empty_string(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if value is None:
                obj[key] = ""
            else:
                replace_nulls_with_empty_string(value)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if item is None:
                obj[i] = ""
            else:
                replace_nulls_with_empty_string(item)
    return obj


async def _get_nearest_stop(session, latitude, longitude):
    r = 10 * 0.008999
    url = (
        f"https://iceman-prod.azurewebsites.net/api/tracker/getNearestStops"
        f"?minLong={longitude - r}&minLat={latitude - r}"
        f"&maxLong={longitude + r}&maxLat={latitude + r}&limit=1"
    )
    async with session.get(url) as resp:
        data = await resp.json()
        return replace_nulls_with_empty_string(data["data"][0])


async def _get_sales_info(session, stop_id):
    url = f"https://iceman-prod.azurewebsites.net/api/tracker/getSalesInfoByStop?stopId={stop_id}"
    async with session.get(url) as resp:
        data = await resp.json()
        return replace_nulls_with_empty_string(data["data"])


async def _get_eta(session, stop_id, route_id):
    url = f"https://iceman-prod.azurewebsites.net/api/tracker/stopsEta?stopId={stop_id}&routeId={route_id}"
    async with session.get(url) as resp:
        data = await resp.json()
        if data["data"] != "":
            date_string = f"{datetime.now().strftime('%Y-%m-%d')} {data['data']} +0000"
            dt = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S %z")
            return dt.astimezone(STOCKHOLM)
        return ""


async def _get_live_route_info(session, route_id):
    url = f"https://iceman-prod.azurewebsites.net/api/tracker/liverouteinfo/{route_id}"
    async with session.get(url) as resp:
        data = await resp.json()
        if data["statusCode"] == 200:
            date_string = f"{datetime.now().strftime('%Y-%m-%d')} {data['data']['indices'][0]['time']} +0000"
            dt = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S %z").astimezone(STOCKHOLM)
            data["data"]["indices"][0]["time"] = dt.strftime("%H:%M:%S")
            return replace_nulls_with_empty_string(data["data"])
        return None


async def _get_next_times(session, stop_id, from_date, limit=20):
    url = (
        f"https://iceman-prod.azurewebsites.net/api/tracker/getnexttimes"
        f"?stopId={stop_id}&fromTime={from_date}&limit={limit}"
    )
    async with session.get(url) as resp:
        data = await resp.json()
        if data["statusCode"] == 200:
            return [entry["nextDate"] for entry in data["data"]]
        return []


async def _get_route_forecast(session, route_id):
    url = f"https://iceman-prod.azurewebsites.net/api/tracker/routeforecast/{route_id}"
    async with session.get(url) as resp:
        data = await resp.json()
        if data["statusCode"] == 200:
            return replace_nulls_with_empty_string(data["data"])
        return None


class HemglassCoordinator(DataUpdateCoordinator):

    def __init__(self, hass, latitude: float, longitude: float):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self._latitude = latitude
        self._longitude = longitude

    async def _async_update_data(self) -> dict:
        session = async_get_clientsession(self.hass)

        try:
            stop = await _get_nearest_stop(session, self._latitude, self._longitude)
        except Exception as err:
            raise UpdateFailed(f"Error fetching stop data: {err}") from err

        stop_id = stop["stopId"]
        route_id = stop["routeId"]

        result = {
            "stopId": stop_id,
            "stopLat": stop["latitude"],
            "stopLong": stop["longitude"],
            "nextDate": stop["nextDate"],
            "nextTime": stop["nextTime"],
            "routeId": route_id,
        }

        try:
            sales = await _get_sales_info(session, stop_id)
            result.update({
                "salesMan": sales["salesmanName"],
                "phoneNumber": sales["phoneNumber"],
                "depotName": sales["depotName"].capitalize(),
                "depotEmail": sales["depotEmail"],
                "streetAddress": sales["streetAddress"].capitalize(),
                "city": sales["city"].capitalize(),
                "comment": sales["comment"],
                "cancelled": sales["cancelled"],
                "cancelledMessage": sales["cancelledMessage"] or "",
            })
        except Exception:
            result.update({
                "salesMan": "", "phoneNumber": "", "depotName": "", "depotEmail": "",
                "streetAddress": "", "city": "", "comment": "", "cancelled": False, "cancelledMessage": "",
            })

        try:
            result["eta"] = await _get_eta(session, stop_id, route_id)
        except Exception:
            result["eta"] = ""

        try:
            result["futureDates"] = await _get_next_times(session, stop_id, date.today().isoformat())
        except Exception:
            result["futureDates"] = []

        try:
            live = await _get_live_route_info(session, route_id)
        except Exception:
            live = None

        if live is not None:
            result["truckIsActiveToday"] = True
            result["truckLocationUpdated"] = live["indices"][0]["time"]
            result["truckIsOffTrack"] = live.get("isOffTrack", "")
            try:
                forecast = await _get_route_forecast(session, route_id)
                cords = forecast[int(live["indices"][0]["index"]) - 1].split(",")
                result["truckLatitude"] = cords[0]
                result["truckLongitude"] = cords[1]
            except Exception:
                result["truckLatitude"] = ""
                result["truckLongitude"] = ""
        else:
            result.update({
                "truckIsActiveToday": False,
                "truckLatitude": "", "truckLongitude": "",
                "truckLocationUpdated": "", "truckIsOffTrack": "",
            })

        return result
