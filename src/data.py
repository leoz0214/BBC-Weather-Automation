"""Module handling file/database input/output and querying."""
import datetime as dt
import json
import pathlib
import re
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
    """Sender email, recipient emails, location ID and times to send at."""
    sender: str
    password: str
    recipients: list[str]
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
    visibility: str
    weather_type: str


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


@dataclass
class WarningInfo:
    """Weather warning information."""
    level: str
    weather_type: str
    issued: dt.datetime
    start: dt.datetime
    end: dt.datetime
    description: str
    active: bool


# Hard-coded file/folder paths relevant to the program.
DATA_FOLDER = pathlib.Path(__file__).parent.parent / "data"
DOWNLOAD_SETTINGS_FILE = DATA_FOLDER / "download.json"
EMAIL_SETTINGS_FILE = DATA_FOLDER / "email.json"
DATABASE = DATA_FOLDER / "database.db"
LOG_FILE = DATA_FOLDER / "log.log"
# Database tables.
LOCATION_TABLE = "locations"
TIME_TABLE = "weather_times"
DAY_TABLE = "daily_conditions"
WARNING_TABLE = "warnings"
# Simple email regex as a sanity check for user input.
BASIC_EMAIL_VALIDATION_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")


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


def _remove_duplicates(array: list) -> list:
    # Deletes duplicates from the array, maintaining order.
    seen = set()
    uniques = []
    for value in array:
        if value in seen:
            continue
        uniques.append(value)
        seen.add(value)
    return uniques


def get_download_settings() -> DownloadSettings:
    """Reads and validates the download settings JSON file."""
    with DOWNLOAD_SETTINGS_FILE.open("r", encoding="utf8") as f:
        json_data = json.load(f)
    location_ids = json_data["location_ids"]
    if not isinstance(location_ids, list):
        raise TypeError("Location IDs must be a list.")
    if not location_ids:
        raise ValueError("Location IDs list must not be empty.")
    if any(
        (not isinstance(location_id, int) or location_id <= 0
            for location_id in location_ids)
    ):
        raise ValueError("Location IDs must be positive integers.")
    location_ids = _remove_duplicates(location_ids)
    refresh_seconds = json_data["refresh_seconds"]
    if not isinstance(refresh_seconds, (int, float)) or refresh_seconds < 0:
        raise ValueError("Invalid refresh seconds.")
    return DownloadSettings(location_ids, refresh_seconds)


def _basic_valid_email_address(email: str) -> bool:
    # Returns True if the email address is valid to a basic extent.
    return bool(re.match(BASIC_EMAIL_VALIDATION_REGEX, email))


def get_email_infos() -> list[EmailInfo]:
    """Validates and returns information on all the emails to send."""
    with EMAIL_SETTINGS_FILE.open("r", encoding="utf8") as f:
        json_data = json.load(f)
    email_infos = []
    for record in json_data:
        sender = record["sender"]
        if (
            (not isinstance(sender, str))
            or (not _basic_valid_email_address(sender))
        ):
            raise ValueError("Invalid sender email found.")
        password = record["password"]
        if not isinstance(password, str):
            raise TypeError("Password must be a string.")
        recipients = record["recipients"]
        if not isinstance(recipients, list):
            raise TypeError("Recipients must be a list.")
        if not recipients:
            raise ValueError("No email recipients added.")
        if any(
            (not isinstance(recipient, str))
            or not _basic_valid_email_address(recipient)
                for recipient in recipients
        ):
            raise ValueError("Invalid recipient email found.")
        recipients = _remove_duplicates(recipients)
        location_id = record["location_id"]
        if (not isinstance(location_id, int)) or location_id < 0:
            raise ValueError("Invalid location ID.")
        times = record["times"]
        if not isinstance(times, list):
            raise TypeError("Times must be a list.")
        if not times:
            raise ValueError("No email send times added.")
        try:
            times = _remove_duplicates(
                [dt.time(*map(int, time_.split(":", maxsplit=1)))
                    for time_ in record["times"]])
        except Exception:
            raise ValueError("Invalid list of times (HH:MM).")
        email_info = EmailInfo(
            sender, password, recipients, location_id, times)
        email_infos.append(email_info)
    return email_infos


def create_missing_tables() -> None:
    """
    Creates all required tables if they do not already exist.
    Store data as compactly as possible using integers mapped
    to corresponding values in the program.
    """
    with Database() as cursor:
        # The Location table stores information about each location by ID.
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {LOCATION_TABLE}(
                location_id INTEGER PRIMARY KEY,
                name TEXT, region TEXT, latitude REAL, longitude REAL,
                last_updated DATETIME)""")
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
                pressure INTEGER, visibility INTEGER, weather_type INTEGER,
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
                issued TIMESTAMP, start TIMESTAMP, end TIMESTAMP,
                time_zone_offset INTEGER, description TEXT,
                PRIMARY KEY(location_id, weather_type, issued),
                FOREIGN KEY(location_id)
                    REFERENCES {LOCATION_TABLE}(location_id))""")
        

def insert_or_replace(table: str, values: tuple) -> None:
    """
    Inserts a given whole record into a table.
    Replace if a record with the same primary key already exists.
    """
    with Database() as cursor:
        cursor.execute(
            f"INSERT OR REPLACE INTO {table} "
            f"VALUES({','.join('?' * len(values))})", values)


def insert_or_replace_many(table: str, records: list[tuple]) -> None:
    """
    Inserts given whole records into a table.
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
    changed, also updates the last updated date/time if a change has occurred.
    """
    with Database() as cursor:
        previous_last_updated = cursor.execute(
            f"SELECT last_updated FROM {LOCATION_TABLE} WHERE location_id=?",
                (location_id,)).fetchone()[0]
        changed = last_updated != previous_last_updated
        if changed:
            cursor.execute(
                f"""
                UPDATE {LOCATION_TABLE} SET last_updated=? WHERE location_id=?
                """, (last_updated, location_id))
    return changed


def get_location_info(location_id: int) -> LocationInfo:
    """Returns the location information by location ID."""
    with Database() as cursor:
        _, name, region, latitude, longitude, last_updated = cursor.execute(
            f"SELECT * FROM {LOCATION_TABLE} WHERE location_id=?",
            (location_id,)).fetchone()
    return LocationInfo(name, region, latitude, longitude, last_updated)


def update_location(
    location_id: int, name: str, region: str, latitude: float, longitude: float
) -> None:
    """
    Updates a given location, except last updated time.
    Create a new record if none with the given location ID exists.
    """
    # Check if there is existing data for the given location.
    with Database() as cursor:
        exists = cursor.execute(
            f"""
            SELECT EXISTS (SELECT * FROM {LOCATION_TABLE} WHERE location_id=?)
            """, (location_id,)).fetchone()[0]
    if not exists:
        record = (location_id, name, region, latitude, longitude, None)
        insert_or_replace(LOCATION_TABLE, record)
        return
    with Database() as cursor:
        cursor.execute(
            f"""
            UPDATE {LOCATION_TABLE}
            SET name=?, region=?, latitude=?, longitude=? WHERE location_id=?
            """, (name, region, latitude, longitude, location_id))


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
            record[3], record[4], record[5], record[6], record[7],
            get.VISIBILITIES_REVERSED[record[8]], get.WEATHER_TYPES[record[9]])
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


def get_future_warnings(location_id: int) -> list[WarningInfo]:
    """Returns a list of all the warnings in place for a given location."""
    current_timestamp = time.time()
    with Database() as cursor:
        # Only display warnings that have not finished (in the past).
        records = cursor.execute(
            f"""
            SELECT level, weather_type, issued, start, end, description,
                time_zone_offset FROM {WARNING_TABLE}
            WHERE location_id=? AND end - time_zone_offset > ?
            ORDER BY level DESC, issued ASC
            """, (location_id, current_timestamp)).fetchall()
    warnings = [
        WarningInfo(
            get.WARNINGS_REVERSED[record[0]], record[1],
            *map(dt.datetime.utcfromtimestamp, record[2:5]), record[5],
            current_timestamp >= record[3] - record[6])
        for record in records]
    return warnings
