# BBC Weather Automation

Staying updated with the weather is always beneficial, especially if you are planning a run, walk, or other outdoor activity. It is simple to load a weather app or site to check, but for the top 1% of laziest people, this proves to be too much! For fun, this project automatically collects weather data from BBC Weather, taking in selected locations by ID. Subsequently, the data is stored in a database and automated emails (including to yourself) can be sent using the data collected. This simple, convenient program has achieved this functionality.

## Feature Overview

If you are interested in this project, before going further, here are the main features that make it more than a trivial script:
- **Download settings** file to set the locations to track, and how often to update the data.
- Backend **SQLite database** to store the obtained weather/location data.
- **Hourly** weather, **daily** conditions and even weather **warnings** are stored.
- Automated **email sending** (Gmail only) for a particular location, with a HTML report generated and sent.

## Guide

### Setup
Obviously, this project uses the simple yet powerful **Python** programming language for its logic.

Project requirements:
- Python **3.10** and above is supported.
- The project has been tested on Windows but whilst it should, it is not guaranteed to work on other operating systems.
- Several third party Python libraries are leveraged:
    - [requests](https://pypi.org/project/requests/) for simple request sending to fetch webpage data.
    - [BeautifulSoup](https://pypi.org/project/beautifulsoup4/) for HTML response parsing.
    - [dominate](https://pypi.org/project/dominate/) for HTML generation (for the output report).

To set up and run the program, assuming the requirements above are considered, follow these steps:
1. Download the code from this repository.
2. Ensure the required libraries are installed as seen in `requirements.txt`. Use pip as usual to install these requirements if needed.
3. Fill in input data and run the top-level `weather.py` script for concurrent data updating and email sending, or `src/get.py` for just data retrieval (see next section).

### Input

-  All configuration files and the database are stored in a folder called `data`.
- There are two JSON configuration files that must be created in the `data` folder serving as the input into the system. Example input files are provided in the `example_data` folder of this project to aid understanding of the expected input. These two files are:
    - `download.json` - specify the locations to download:
        - A JSON dictionary containing two keys, `location_ids` and `refresh_seconds` is expected.
        - `location_ids` - a list of location IDs (integers) to retrieve data from. The ID for a given location is visible in its URL e.g. from https://www.bbc.com/weather/2643743, one can deduce the location ID to be 2643743.
        - `refresh_seconds` - the number of seconds between data retrieval cycles. This is how many seconds to wait before retrieving/updating weather data for each location.
    - `email.json` - specify automated weather emails to send based on this program's data:
        - A JSON list of dictionaries is expected, where each dictionary consists of relevant data for sending emails.
        - `sender` - the email address of the sender. Note, only **Google** emails are supported for now.
        - `password` - the **app password** for the given sender. This is not the account password. Google has details here: https://support.google.com/accounts/answer/185833?hl=en. Be very careful, if you have any security concerns, usage of this overall program is not recommended. Perhaps create a specialised Gmail account you do not mind storing the app password for, and use it as the sender.
        - `recipients` - a list of email addresses to send the report to. These will all be sent using **BCC** (blind carbon copy). These email addresses do not have to be Google emails. To only send to 1 email address, such as yourself, still put it into a list of its own.
        - `location_id` - this is the ID of the location to generate the report based on. For this to work, this location ID must have data inside the database, meaning you need to also add this location ID for data downloading.
        - `times` - these are the times in **HH:MM** format to send an automated email at. These times are based on the time of the computer in use, not bound to a particular time zone.

### Features in depth

Now that the program setup and input have been covered, it is time to explain the features of the program in greater detail. For advanced users, the source code can also be read to understand better how the program works.

As already clear, the program is separated into 2 main parts - the data collection and email sending.

#### Data Collection

Of course, the weather data from BBC Weather needs to be retrieved in the first place. This is achieved by sending a HTTPS request to the relevant BBC Weather page based on location ID. This is attempted multiple times in case of intermittent failure. Upon success, the HTML response is recieved and can then be parsed for the data.

There are three categories of data:
- **Hourly data** - weather information per hour as seen on the website. Includes weather metrics such as weather type, temperature (alongside feels-like temperature), wind speed/direction, humidity, precipitation odds, pressure and visibility.
- **Daily data** - general information on daily conditions, including maximum/minimum temperature, sunrise/sunset time, UV levels, pollution levels and pollen levels.
- **Weather warnings** - the warnings as seen sometimes due to extreme rain, wind, snow and other condtions are also captured by the program. This includes recording the warning level, extreme weather type, start/stop times, and description.

Once data is obtained, it is inserted or updated into the database. Existing records may have data updated due a change in data to the fundamentally same data point (e.g. the data for a given hour for a given location).

The date/time last updated is stored, so that no updating occurs if this has not changed since the last check.

#### Email Sending
The data on its own is pointless, and needs a use. Whilst many other uses are possible, this project focuses on automated email sending based on this data.

Each email has one sender and one or more recipients, alongside a selected location and times to send at. It is viable to send the email to yourself, as the sender can also be a recipient. The location must have data stored in the database in order to be usable for email sending.

Assuming location information is available, the program queries the relevant data and generates a HTML weather report for the given location. Note that this report has a minimalist design - more advanced users may modify the code to improve the aesthetics as desired.

The generated report has the following structure:
- **Title** (location)
- Any weather **warnings** are shown first in descending order of severity.
- The hourly weather for the next **6 hours** is displayed, including weather type, temperature, wind, humidity etc.
- The daily conditions for the next **3 days** (starting from the day after the current day) is displayed, including max/min temperature, sunrise/sunset, UV etc.
- Date/time last updated.
- BBC Weather URL for the location (convenient gateway for full viewage).

In terms of timings, if the current local time in HH:MM matches one of the times in the list of times to send at, the report is generated and the email is sent as BCC to each recipient. Email sending is attempted multiple times in case of intermittent failure.

## Usage/Disclaimer

This project is free to use, and you may do anything as you wish with the source code and program. Note however that there is no liability for any damages caused by using the program. Due to the fact websites change over time, the program may also stop working at any time.

You must use the program responsibly, avoiding scraping BBC Weather too often, otherwise expect possibly being blocked. This is not handled by the program since it is intended for small-scale use (saving data for a few selected locations at reasonable time intervals). Also, the program possibly violates TOS, so use with caution if planning to use it in a non-trivial way.