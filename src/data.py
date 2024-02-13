"""Module handling file/database input and output code."""
import datetime as dt
import json
import pathlib
import sqlite3
import time
from dataclasses import dataclass

import get


@dataclass
class DownloadSettings:
    """Download location IDs and refresh rate."""
    location_ids: list[int]
    refresh_seconds: int | float


@dataclass
class EmailInfo:
    """Sender email, recipient email, location ID and times to send at."""
    sender: str
    recipient: str
    location_id: int
    times: list[dt.time]


@dataclass
class LocationInfo:
    """Overall location details, including last updated date/time."""
    name: str
    region: str
    latitude: float
    longitude: float
    last_updated: str | None


@dataclass
class WeatherInfo:
    """Hourly weather information."""
    date_time: dt.datetime
    temperature: int
    feels_like_temperature: int
    wind_speed: int
    wind_direction: str
    humidity: int
    precipitation_odds: int
    pressure: int
    visibility: get.Visibility
    weather_type: get.WeatherType


@dataclass
class ConditionsInfo:
    """Daily conditions information."""
    date: dt.date
    max_temperature: int
    min_temperature: int
    sunrise: dt.time
    sunset: dt.time
    uv: int
    pollution: int | None
    pollen: int | None


DATA_FOLDER = pathlib.Path(__file__).parent.parent / "data"
DOWNLOAD_SETTINGS_FILE = DATA_FOLDER / "download.json"
EMAIL_SETTINGS_FILE = DATA_FOLDER / "email.json"
DATABASE = DATA_FOLDER / "database.db"
# Database tables.
LOCATION_TABLE = "locations"
TIME_TABLE = "weather_times"
DAY_TABLE = "daily_conditions"
WARNING_TABLE = "warnings"
LAST_UPDATED_TABLE = "last_updated"


class Database:
    """Sqlite3 database wrapper."""

    def __enter__(self) -> sqlite3.Cursor:
        """Start of database processing context manager."""
        self.connection = sqlite3.connect(DATABASE)
        cursor = self.connection.cursor()
        # Ensure foreign keys are enabled for integrity.
        cursor.execute("PRAGMA foreign_keys = ON")
        return cursor
    
    def __exit__(self, exception: Exception | None, *_) -> None:
        """Context manager exited - commit if no error occurred."""
        if exception is None:
            self.connection.commit()
        self.connection.close()
        self.connection = None


def get_download_settings() -> DownloadSettings:
    """Reads the download settings JSON file."""
    with DOWNLOAD_SETTINGS_FILE.open("r", encoding="utf8") as f:
        json_data = json.load(f)
    return DownloadSettings(
        json_data["location_ids"], json_data["refresh_seconds"])


def get_email_infos() -> list[EmailInfo]:
    """Returns information on all the emails to send."""
    with EMAIL_SETTINGS_FILE.open("r", encoding="utf8") as f:
        json_data = json.load(f)
    return [
        EmailInfo(
            record["sender"], record["recipient"], record["location_id"],
            [dt.time(*map(int, time_.split(":", maxsplit=1)))
                for time_ in record["times"]]
        ) for record in json_data]


def create_missing_tables() -> None:
    """Creates all required tables if they do not already exist."""
    with Database() as cursor:
        # The Location table stores information about each location
        # by location ID.
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {LOCATION_TABLE}(
                location_id INTEGER PRIMARY KEY,
                name TEXT, region TEXT,
                latitude REAL, longitude REAL)""")
        # The Time table stores the weather information at fixed
        # times, usually at hourly intervals.
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TIME_TABLE}(
                location_id INTEGER,
                timestamp TIMESTAMP, time_zone_offset INTEGER,
                temperature INTEGER, feels_like_temperature INTEGER,
                wind_speed INTEGER, wind_direction TEXT,
                humidity INTEGER, precipitation_odds INTEGER,
                pressure INTEGER, visibility INTEGER,
                weather_type INTEGER,
                PRIMARY KEY(location_id, timestamp),
                FOREIGN KEY(location_id)
                    REFERENCES {LOCATION_TABLE}(location_id))""")
        # The Day table stores the general conditions information
        # that is provided each day, such as UV/pollution/dawn/dusk.
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {DAY_TABLE}(
                location_id INTEGER,
                timestamp TIMESTAMP, time_zone_offset INTEGER,
                max_temperature INTEGER, min_temperature INTEGER,
                sunrise TIME, sunset TIME, uv INTEGER, pollution INTEGER,
                pollen INTEGER,
                PRIMARY KEY(location_id, timestamp),
                FOREIGN KEY(location_id)
                    REFERENCES {LOCATION_TABLE}(location_id))""")
        # The Warnings table stores weather warnings information.
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {WARNING_TABLE}(
                location_id INTEGER, level INTEGER, weather_type TEXT,
                issued DATETIME, start DATETIME, end DATETIME,
                description TEXT,
                PRIMARY KEY(location_id, weather_type, issued),
                FOREIGN KEY(location_id)
                    REFERENCES {LOCATION_TABLE}(location_id))""")
        # The last updated table simply stores the last updated
        # date/time for each location ID.
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {LAST_UPDATED_TABLE}(
                location_id INTEGER PRIMARY KEY, last_updated DATETIME,
                FOREIGN KEY(location_id)
                    REFERENCES {LOCATION_TABLE}(location_id))""")
        

def insert_or_replace(table: str, values: tuple) -> None:
    """
    Inserts a given record into a table.
    Replace if a record with the same primary key already exists.
    """
    with Database() as cursor:
        cursor.execute(
            f"INSERT OR REPLACE INTO {table} "
            f"VALUES({','.join('?' * len(values))})",
            values)


def insert_or_replace_many(table: str, records: list[tuple]) -> None:
    """
    Inserts given records into a table.
    Replace if a record with the same primary key already exists.
    """
    with Database() as cursor:
        for values in records:
            cursor.execute(
                f"INSERT OR REPLACE INTO {table} "
                f"VALUES({','.join('?' * len(values))})", values)


def last_updated_changed(location_id: int, last_updated: str) -> bool:
    """
    Returns True if the last updated date/time for a given location ID has
    changed, also updates the last updated date/time if a change has indeed
    occurred.
    """
    with Database() as cursor:
        previous_last_updated = cursor.execute(
            f"""
            SELECT last_updated FROM {LAST_UPDATED_TABLE}
            WHERE location_id=?""", (location_id,)).fetchone()
    changed = (
        previous_last_updated is None # First time.
        or last_updated != previous_last_updated[0])
    if changed:
        insert_or_replace(LAST_UPDATED_TABLE, (location_id, last_updated))
    return changed


def get_location_info(location_id: int) -> LocationInfo:
    """Returns the location information by location ID."""
    with Database() as cursor:
        name, region, latitude, longitude = cursor.execute(
            f"""
            SELECT name, region, latitude, longitude
            FROM {LOCATION_TABLE} WHERE location_id=?""", (location_id,)
        ).fetchone()
        last_updated = cursor.execute(
            f"""
            SELECT last_updated FROM {LAST_UPDATED_TABLE}
            WHERE location_id=?""", (location_id,)).fetchone()
        if last_updated is not None:
            last_updated = last_updated[0]
    return LocationInfo(name, region, latitude, longitude, last_updated)


def get_future_weather(location_id: int, hours: int) -> list[WeatherInfo]:
    """Returns weather conditions for the next N hours, as available."""
    current_timestamp = time.time()
    with Database() as cursor:
        records = cursor.execute(
            f"""
            SELECT timestamp, temperature, feels_like_temperature, wind_speed,
                wind_direction, humidity, precipitation_odds, pressure,
                visibility, weather_type FROM {TIME_TABLE}
            WHERE location_id=? AND timestamp - time_zone_offset > ?
            ORDER BY timestamp ASC LIMIT ?
            """, (location_id, current_timestamp, hours)).fetchall()
    weather_infos = [
        WeatherInfo(
            dt.datetime.utcfromtimestamp(record[0]), record[1], record[2],
            record[3], record[4], record[5], record[6],
            record[7] + get.PRESSURE_OFFSET, get.Visibility(record[8]),
            get.WeatherType(record[9]))
        for record in records]
    return weather_infos


def get_future_conditions(location_id: int, days: int) -> list[ConditionsInfo]:
    """Returns daily conditions for the next N available days."""
    current_timestamp = time.time()
    with Database() as cursor:
        records = cursor.execute(
            f"""
            SELECT timestamp, max_temperature, min_temperature,
                sunrise, sunset, uv, pollution, pollen FROM {DAY_TABLE}
            WHERE location_id=? AND timestamp - time_zone_offset > ?
            ORDER BY timestamp ASC LIMIT ?
            """, (location_id, current_timestamp, days)).fetchall()
    conditions_infos = [
        ConditionsInfo(
            dt.datetime.utcfromtimestamp(record[0]).date(),
            record[1], record[2], dt.time(*map(int, record[3].split(":"))),
            dt.time(*map(int, record[4].split(":"))), record[5], record[6],
            record[7]) for record in records]
    return conditions_infos
