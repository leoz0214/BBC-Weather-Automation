"""
This is the script to run the repeated scraping process - by
sending requests to the corresponding location URLs at fixed
intervals and updating the database to account for changed
or new data.
"""
import calendar
import datetime as dt
import json
import time
from timeit import default_timer as timer

import lxml
import requests as rq
from bs4 import BeautifulSoup

import data


BBC_WEATHER_BASE_URL = "https://www.bbc.com/weather"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
# Same as BBC Weather.
# Minimum significant gust speed to display instead of the actual wind speed.
GUSTS_MPH = 40
VISIBILITIES = {
    "Very Poor": 0, "Poor": 1, "Moderate": 2,
    "Good": 3, "Very Good": 4, "Excellent": 5
}
VISIBILITIES_REVERSED = {value: key for key, value in VISIBILITIES.items()}
# From https://www.metoffice.gov.uk/services/data/datapoint/code-definitions
WEATHER_TYPES = {
    0: "Clear Sky", 1: "Sunshine", 2: "Partly Cloudy", 3: "Sunny Intervals",
    5: "Mist", 6: "Fog", 7: "Light Cloud", 8: "Thick Cloud",
    9: "Light Rain Showers", 10: "Light Rain Showers",
    11: "Drizzle", 12: "Light Rain", 13: "Heavy Rain Showers",
    14: "Heavy Rain Showers", 15: "Heavy Rain",
    16: "Sleet Showers Night", 17: "Sleet Showers", 18: "Sleet",
    19: "Hail Showers", 20: "Hail Showers", 21: "Hail",
    22: "Light Snow Showers", 23: "Light Snow Showers", 24: "Light Snow",
    25: "Heavy Snow Showers", 26: "Heavy Snow Showers", 27: "Heavy Snow",
    28: "Thundery Showers", 29: "Thundery Showers", 30: "Thunder"
}
WARNING_LEVELS = {"Yellow": 0, "Amber": 1, "Red": 2}
WARNINGS_REVERSED = {value: key for key, value in WARNING_LEVELS.items()}
# Month literals.
MONTHS = tuple(calendar.month_name)[1:]
MAX_REQUEST_ATTEMPTS = 3


def add_location_if_missing(location_info: dict) -> None:
    """Adds location info to the locations table if needed."""
    data.update_location(
        location_info["id"], location_info["name"], location_info["container"],
        location_info["latitude"], location_info["longitude"])


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
                wind_speed, report["windDirection"], report["humidity"],
                report["precipitationProbabilityInPercent"],
                report["pressure"], VISIBILITIES[report["visibility"]],
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


def extract_warning_text_timestamp(text: str) -> int:
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
    # Year not given, but use common sense to deduce it (timezones irrelevant).
    current_date = dt.date.today()
    current_year = current_date.year
    if (current_date - dt.date(current_year, month, day)).days > 180:
        year = current_year + 1
    else:
        year = current_year
    return dt.datetime(year, month, day, hour, minute).replace(
        tzinfo=dt.timezone.utc).timestamp()


def add_weather_warnings(location_id: int, soup: BeautifulSoup) -> None:
    """
    Searches the HTML page for any weather warnings and inserts them
    into the database as required.
    """
    warning_records = []
    for warning_div in soup.find_all("div", class_="wr-c-weather-warning"):
        level, weather_type = warning_div.find("h3").text.split(" warning of ")
        level = WARNING_LEVELS[level]
        issued_at_text = warning_div.find(
            "p", class_="wr-c-weather-warning__issued-at-date").text
        start_text, end_text = [
            p.text for p in warning_div.find(
                "div", class_="wr-c-weather-warning__warning-period"
            ).find_all("p") if "wr-o-active" not in p["class"]]
        issued = extract_warning_text_timestamp(issued_at_text)
        start = extract_warning_text_timestamp(start_text)
        end = extract_warning_text_timestamp(end_text)
        description = warning_div.find(
            "p", class_="wr-c-weather-warning__warning-text").text.strip()
        # BST (UTC+1) or GMT (UTC).
        time_zone_offset = 0 if "GMT" in issued_at_text else 3600
        record = (
            location_id, level, weather_type,
            issued, start, end, time_zone_offset, description)
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
