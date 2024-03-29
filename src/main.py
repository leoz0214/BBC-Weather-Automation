"""
This script combines the data collection and email sending
by running both scripts in separate threads, terminating
upon failure (error) in either script.
"""
import data
import logging
import threading
import time
import sys
from typing import Callable

import get
import send


# Allow some time for the get script to begin and update any data.
SEND_START_DELAY = 15


class WeatherAutomation:
    """Class handling the script running, and error handling."""

    def __init__(self) -> None:
        self.exception = None
    
    def start(self) -> None:
        """Starts the dual-script."""
        logging.info("Data collection script started.")
        threading.Thread(
            target=lambda: self._run(get.main), daemon=True).start()
        time.sleep(SEND_START_DELAY)
        logging.info("Email sending script started.")
        threading.Thread(
            target=lambda: self._run(send.main), daemon=True).start()
        # Busy waiting, waiting for an exception otherwise keep running.
        while True:
            if self.exception is not None:
                sys.exit(-1)
            time.sleep(0.25)
    
    def _run(self, function: Callable) -> None:
        try:
            function()
        except Exception as e:
            # Error occurred - terminate overall script.
            logging.critical(f"Fatal Error: {e}")
            self.exception = e


def main() -> None:
    """Main procedure of the script."""
    logging.basicConfig(
        handlers=(logging.FileHandler(data.LOG_FILE), logging.StreamHandler()),
        encoding="utf8", level=logging.INFO,
        format= "%(asctime)s: %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")
    WeatherAutomation().start()


if __name__ == "__main__":
    main()
