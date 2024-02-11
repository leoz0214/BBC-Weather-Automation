"""Module handling file/database input and output code."""
import json
import pathlib
import sqlite3
from contextlib import suppress
from dataclasses import dataclass


@dataclass
class DownloadSettings:
    """Download location IDs and refresh rate."""
    location_ids: list[str]
    refresh_seconds: int | float


DATA_FOLDER = pathlib.Path(__file__).parent.parent / "data"
DOWNLOAD_SETTINGS_FILE = DATA_FOLDER / "download.json"
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


def create_missing_tables() -> None:
    """Creates all required tables if they do not already exist."""
    with Database() as cursor:
        # The Location table stores information about each location
        # by location ID.
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {LOCATION_TABLE}(
                location_id TEXT PRIMARY KEY,
                name TEXT, region TEXT,
                latitude REAL, longitude REAL)""")
        # The Time table stores the weather information at fixed
        # times, usually at hourly intervals.
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TIME_TABLE}(
                location_id TEXT, date_time DATETIME,
                temperature INTEGER, feels_like_temperature INTEGER,
                wind_speed INTEGER, wind_direction TEXT,
                humidity INTEGER, precipitation_odds INTEGER,
                pressure INTEGER, visibility INTEGER,
                weather_type INTEGER,
                PRIMARY KEY(location_id, date_time),
                FOREIGN KEY(location_id)
                    REFERENCES {LOCATION_TABLE}(location_id))""")
        # The Day table stores the general conditions information
        # that is provided each day, such as UV/pollution/dawn/dusk.
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {DAY_TABLE}(
                location_id TEXT, date DATE,
                max_temperature INTEGER, min_temperature INTEGER,
                sunrise TIME, sunset TIME, uv INTEGER, pollution INTEGER,
                weather_type INTEGER,
                PRIMARY KEY(location_id, date),
                FOREIGN KEY(location_id)
                    REFERENCES {LOCATION_TABLE}(location_id))""")
        # The Warnings table stores weather warnings information.
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {WARNING_TABLE}(
                location_id TEXT, level INTEGER, weather_type TEXT,
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
                location_id TEXT PRIMARY KEY, last_updated DATETIME,
                FOREIGN KEY(location_id)
                    REFERENCES {LOCATION_TABLE}(location_id))""")
        

def insert(table: str, values: tuple) -> None:
    """Inserts a given record into a table."""
    with Database() as cursor:
        cursor.execute(
            f"INSERT INTO {table} VALUES({','.join('?' * len(values))})",
            values)


def add_location_if_missing(location_info: dict) -> None:
    """Adds location info to the locations table if needed."""
    record = (
        location_info["id"], location_info["name"], location_info["container"],
        location_info["latitude"], location_info["longitude"])
    # Ignore if location data already exists.
    with suppress(sqlite3.IntegrityError):
        insert(LOCATION_TABLE, record)
