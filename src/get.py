"""
This is the script to run the repeated scraping process - by
sending requests to the corresponding location URLs at fixed
intervals and updating the database to account for changed
or new data.
"""
import calendar
import datetime as dt
import enum
import json
import time
from timeit import default_timer as timer

import lxml
import requests as rq
from bs4 import BeautifulSoup

import data


class Visibility(enum.Enum):
    """Visibility level of the human eye."""
    very_poor = 0
    poor = 1
    moderate = 2
    good = 3
    very_good = 4
    excellent = 5


class WeatherType(enum.Enum):
    """Various possible weather types."""
    clear_sky = 0
    sunny = 1
    partly_cloudy = 2
    sunny_intervals = 3
    mist = 5
    fog = 6
    light_cloud = 7
    thick_cloud = 8
    light_rain_showers_night = 9
    light_rain_showers = 10
    drizzle = 11
    light_rain = 12
    heavy_rain_showers_night = 13
    heavy_rain_showers = 14
    heavy_rain = 15
    sleet_showers_night = 16
    sleet_showers = 17
    sleet = 18
    hail_showers_night = 19
    hail_showers = 20
    hail = 21
    light_snow_showers_night = 22
    light_snow_showers = 23
    light_snow = 24
    heavy_snow_showers_night = 25
    heavy_snow_showers = 26
    heavy_snow = 27
    thundery_showers_night = 28
    thundery_showers = 29
    thunder = 30


class WarningLevel(enum.Enum):
    """Severity of extreme weather conditions."""
    yellow = 0
    amber = 1
    red = 2


BBC_WEATHER_BASE_URL = "https://www.bbc.com/weather"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
GUSTS_MPH = 40
VISIBILITIES = {
    "Very Poor": Visibility.very_poor, "Poor": Visibility.poor,
    "Moderate": Visibility.moderate, "Good": Visibility.good,
    "Very Good": Visibility.very_good, "Excellent": Visibility.excellent
}
VISIBILITIES_REVERSED = {value: key for key, value in VISIBILITIES.items()}
WEATHER_TYPES = {
    WeatherType.clear_sky: "Clear Sky", WeatherType.sunny: "Sunshine",
    WeatherType.partly_cloudy: "Partly Cloudy",
    WeatherType.sunny_intervals: "Sunny Intervals",
    WeatherType.mist: "Mist", WeatherType.fog: "Fog",
    WeatherType.light_cloud: "Light Cloud",
    WeatherType.thick_cloud: "Thick Cloud",
    WeatherType.light_rain_showers_night: "Light Rain Showers",
    WeatherType.light_rain_showers: "Light Rain Showers",
    WeatherType.drizzle: "Drizzle", WeatherType.light_rain: "Light Rain",
    WeatherType.heavy_rain_showers_night: "Heavy Rain Showers",
    WeatherType.heavy_rain_showers: "Heavy Rain Showers",
    WeatherType.heavy_rain: "Heavy Rain",
    WeatherType.sleet_showers_night: "Sleet Showers Night",
    WeatherType.sleet_showers: "Sleet Showers", WeatherType.sleet: "Sleet",
    WeatherType.hail_showers_night: "Hail Showers",
    WeatherType.hail_showers: "Hail Showers",
    WeatherType.hail: "Hail",
    WeatherType.light_snow_showers_night: "Light Snow Showers",
    WeatherType.light_snow_showers: "Light Snow Showers",
    WeatherType.light_snow: "Light Snow",
    WeatherType.heavy_snow_showers_night: "Heavy Snow Showers",
    WeatherType.heavy_snow_showers: "Heavy Snow Showers",
    WeatherType.heavy_snow: "Heavy Snow",
    WeatherType.thundery_showers_night: "Thundery Showers",
    WeatherType.thundery_showers: "Thundery Showers",
    WeatherType.thunder: "Thunder"
}
WARNING_LEVELS = {
    "Yellow": WarningLevel.yellow, "Amber": WarningLevel.amber,
    "Red": WarningLevel.red
}
# To save storage space (smaller integers).
PRESSURE_OFFSET = 1013
# Month literals.
MONTHS = tuple(calendar.month_name)[1:]
MAX_REQUEST_ATTEMPTS = 3


def add_location_if_missing(location_info: dict) -> None:
    """Adds location info to the locations table if needed."""
    record = (
        location_info["id"], location_info["name"], location_info["container"],
        location_info["latitude"], location_info["longitude"])
    data.insert_or_replace(data.LOCATION_TABLE, record)


def process_json_data(location_id: int, json_data: dict) -> None:
    """Inserts and updates weather/conditions records from the JSON data."""
    weather_time_records = []
    daily_conditions_records = []
    time_zone_offset = dt.datetime.fromisoformat(
        json_data["issueDate"]).utcoffset()
    time_zone_offset_seconds = (
        time_zone_offset.days * 86400 + time_zone_offset.seconds)
    for i, forecast in enumerate(json_data["forecasts"]):
        # Hourly data
        for report in forecast["detailed"]["reports"]:
            timestamp = dt.datetime.strptime(
                f"{report['localDate']} {report['timeslot']}",
                "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp()
            wind_speed = (
                report["windSpeedMph"] if report["gustSpeedMph"] < GUSTS_MPH
                else report["gustSpeedMph"]) 
            record = (
                location_id, timestamp, time_zone_offset_seconds,
                report["temperatureC"], report["feelsLikeTemperatureC"],
                wind_speed, report["windDirection"],
                report["humidity"],
                report["precipitationProbabilityInPercent"],
                report["pressure"] - PRESSURE_OFFSET,
                VISIBILITIES[report["visibility"]].value,
                report["weatherType"])
            weather_time_records.append(record)
        # Daily data.
        if i == 0:
            # Current day's forecast - do not capture day conditions
            # as it may not be reflective of the entire day.
            # If captured at night, UV will display as low - misleading.
            continue
        day = forecast["summary"]["report"]
        day_timestamp = dt.datetime.strptime(
            day["localDate"], "%Y-%m-%d"
        ).replace(tzinfo=dt.timezone.utc).timestamp()
        record = (
            location_id, day_timestamp, time_zone_offset_seconds,
            day["maxTempC"], day["minTempC"], day["sunrise"], day["sunset"], 
            day["uvIndex"], day["pollutionIndex"], day["pollenIndex"])
        daily_conditions_records.append(record)
    data.insert_or_replace_many(data.TIME_TABLE, weather_time_records)
    data.insert_or_replace_many(data.DAY_TABLE, daily_conditions_records)


def extract_warning_text_date(text: str) -> dt.datetime:
    """Returns the date as seen in one of the weather warnings texts."""
    parts = text.split()
    hour = None
    minute = None
    month = None
    day = None
    for i, part in enumerate(parts):
        if ":" in part and part.replace(":", "").isdigit():
            hour, minute = map(int, part.split(":"))
        if part in MONTHS:
            month = MONTHS.index(part) + 1
            day = int(parts[i-1])
    # Year not given, but use common sense to deduce it
    # (timezones don't matter).
    current_date = dt.date.today()
    current_year = current_date.year
    if (current_date - dt.date(current_year, month, day)).days > 180:
        year = current_year + 1
    else:
        year = current_year
    return dt.datetime(year, month, day, hour, minute)


def add_weather_warnings(location_id: int, soup: BeautifulSoup) -> None:
    """
    Searches the webpage for any weather warnings and inserts them
    into the database as required.
    """
    warning_records = []
    for warning_div in soup.find_all("div", class_="wr-c-weather-warning"):
        level, weather_type = warning_div.find("h3").text.split(" warning of ")
        level = WARNING_LEVELS[level].value
        issued_at_text = warning_div.find(
            "p", class_="wr-c-weather-warning__issued-at-date").text
        start_text, end_text = [
            p.text for p in warning_div.find(
                "div", class_="wr-c-weather-warning__warning-period"
            ).find_all("p") if "wr-o-active" not in p["class"]]
        issued = extract_warning_text_date(issued_at_text)
        start = extract_warning_text_date(start_text)
        end = extract_warning_text_date(end_text)
        description = warning_div.find(
            "p", class_="wr-c-weather-warning__warning-text").text.strip()

        record = (
            location_id, level, weather_type, issued, start, end, description)
        warning_records.append(record)
    data.insert_or_replace_many(data.WARNING_TABLE, warning_records)
        

def main() -> None:
    """Main procedure of the program."""
    data.create_missing_tables()
    while True:
        print(f"Obtaining data at {dt.datetime.now().replace(microsecond=0)}")
        start = timer()
        download_settings = data.get_download_settings()
        for location_id in download_settings.location_ids:
            url = f"{BBC_WEATHER_BASE_URL}/{location_id}"
            # Attempts the request multiple times for improved robustness.
            attempts = MAX_REQUEST_ATTEMPTS
            while True:
                try:
                    response = rq.get(url, headers=HEADERS)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, "lxml")
                        break
                except Exception as e:
                    attempts -= 1
                    if not attempts:
                        raise e
                    time.sleep(1)     
            json_data = json.loads(
                soup.find("script", {"data-state-id": "forecast"}).text
            )["data"]
            add_location_if_missing(json_data["location"])
            last_updated = json_data["lastUpdated"]
            if data.last_updated_changed(location_id, last_updated):
                print(f"{location_id}: Data updated.")
                process_json_data(location_id, json_data)
                add_weather_warnings(location_id, soup)
            else:
                print(f"{location_id}: No data update.")
        stop = timer()
        time.sleep(max(0, download_settings.refresh_seconds - (stop - start)))


if __name__ == "__main__":
    main()
