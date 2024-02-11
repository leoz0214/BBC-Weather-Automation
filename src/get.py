"""
This is the script to run the repeated scraping process - by
sending requests to the corresponding location URLs at fixed
intervals and updating the database to account for changed
or new data.
"""
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


def main() -> None:
    """Main procedure of the program."""
    data.create_missing_tables()
    while True:
        print(f"Obtaining data at {dt.datetime.now().replace(microsecond=0)}")
        start = timer()
        download_settings = data.get_download_settings()
        for location_id in download_settings.location_ids:
            url = f"{BBC_WEATHER_BASE_URL}/{location_id}"
            response = rq.get(url, headers=HEADERS).text
            soup = BeautifulSoup(response, "lxml")
            json_data = json.loads(
                soup.find("script", {"data-state-id": "forecast"}).text
            )["data"]
            data.add_location_if_missing(json_data["location"])
            last_updated = json_data["lastUpdated"]
        stop = timer()
        time.sleep(max(0, download_settings.refresh_seconds - (stop - start)))


if __name__ == "__main__":
    main()
