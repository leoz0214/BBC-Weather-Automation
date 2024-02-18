"""Absolute top-level script for running the weather automation."""
import pathlib
import sys


sys.path.append(str(pathlib.Path(__file__).parent / "src"))


import main


if __name__ == "__main__":
    main.main()
