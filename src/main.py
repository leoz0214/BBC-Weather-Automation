"""
This script combines the data collection and email sending
by running both scripts in separate threads, terminating
upon failure (error) in either script.
"""
import threading
import time
import sys
from typing import Callable

import get
import send


SEND_START_DELAY = 15


class WeatherAutomation:
    """Class handling the script running, and error handling."""

    def __init__(self) -> None:
        self.exception = None
    
    def start(self) -> None:
        """Starts the dual-script."""
        print("Data collection script started.")
        threading.Thread(
            target=lambda: self._run(get.main), daemon=True).start()
        # Give some time for the get script to begin.
        time.sleep(SEND_START_DELAY)
        print("Email sending script started.")
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
            print(f"Error: {e}")
            self.exception = e


if __name__ == "__main__":
    WeatherAutomation().start()