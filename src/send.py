"""Automated email sending tool based on the collected weather data."""
import datetime as dt
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from timeit import default_timer as timer

import dominate
import dominate.tags as tags
from dominate.util import text

import data
import get


# Number of hours/days ahead to display data for.
FUTURE_HOURS = 6
FUTURE_DAYS = 3

TEMPERATURE_CLASSES = {
    "hottest": 45, "hotter": 35, "warm": 20,
    "mild": 10, "cool": 5, "colder": -10, "coldest": -100
}
PRECIPITATION_ODDS_CLASSES = {
    "precip-likely": 75, "precip-chance": 25, "precip-unlikely": 0
}
VISIBILITY_CLASSES = {
    "Excellent": "excellent-visibility", "Very Good": "very-good-visibility",
    "Good": "good-visibility", "Moderate": "moderate-visibility",
    "Poor": "poor-visibility", "Very Poor": "very_poor-visibility"
}
UV_CLASSES = {
    "extreme-uv": 11, "very-high-uv": 8, "high-uv": 6,
    "moderate-uv": 3, "low-uv": 0
}
POLLUTION_CLASSES = {
    "very-high-pollution": 10, "high-pollution": 7,
    "moderate-pollution": 4, "low-pollution": 0
}
# Just a guess - can improve on during pollen season when mass data available.
POLLEN_CLASSES = {
    "very-high-pollen": 10, "high-pollen": 7,
    "moderate-pollen": 4, "low-pollen": 0
}
WARNING_CLASSES = {
    "Yellow": "yellow-warning", "Amber": "amber-warning", "Red": "red-warning"
}

# Email sending configuration information.
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
REFRESH_SECONDS = 45
MAX_EMAIL_SEND_ATTEMPTS = 3


def _get_class(value: int, classes: dict[str, int]) -> str:
    # Returns appropriate class based on class, min pairs.
    return next(
        class_ for class_, min_value in classes.items() if value >= min_value)


def get_temperature_class(temperature: int) -> str:
    """Returns the appropriate temperature class for a given temperature."""
    return _get_class(temperature, TEMPERATURE_CLASSES)


def get_precipitation_class(odds: int) -> str:
    """Returns the appropriate preciptation class based on the chance."""
    return _get_class(odds, PRECIPITATION_ODDS_CLASSES)


def get_uv_class(uv: int) -> str:
    """Returns the UV class based on the UV index."""
    return _get_class(uv, UV_CLASSES)


def get_pollution_class(pollution: int) -> str:
    """Returns the pollution class based on the pollution index."""
    return _get_class(pollution, POLLUTION_CLASSES)


def get_pollen_class(pollen: int) -> str:
    """Returns the pollen class based on the pollen index."""
    return _get_class(pollen, POLLEN_CLASSES)


def get_title(location_info: data.LocationInfo) -> str:
    """Returns the title given the location information."""
    location = (
        f"{location_info.name}, {location_info.region}"
        if location_info.name != location_info.region else location_info.name)
    return f"Weather Report for {location}"


def generate_html_email(
    location_id: int, location_info: data.LocationInfo
) -> str:
    """
    Takes the weather data for a given location info and 
    generates a HTML report ready to send as an email.
    """
    document = dominate.document(get_title(location_info))
    # Set report CSS.
    with document.head:
        tags.style(
            r"""
            * {font-family: sans-serif;}
            h1 {font-size: 40px;}
            h2 {font-size: 35px;}
            h3 {font-size: 25px;}
            p {white-space: pre-line;}
            span {white-space: nowrap;}

            .hottest {color: #c21a11;}
            .hotter {color: #f02318;}
            .warm {color: #f07f0e;}
            .mild {color: #17c223;}
            .cool {color: #0ca9f7;}
            .colder {color: #0c86f7;}
            .coldest {color: #267bc9;}

            .extreme-uv {color: violet;}
            .gusts, .precip-likely, .very-poor-visibility,
                .very-high-uv, .very-high-pollution {color: red;}
            .precip-chance, .poor-visibility, .high-uv,
                .high-pollution {color: orange;}
            .moderate-uv, .moderate-pollution {color: #c3eb34;}
            .moderate-visibility, .good-visibility, .low-uv,
                .low-pollution {color: #00cc00;}
            .very-good-visibility, .excellent-visibility {color: #0ca9f7;}

            .yellow-warning {background: yellow;}
            .amber-warning {background: orange;}
            .red-warning {background: red;}
            .yellow-warning, .amber-warning, .red-warning {
                padding: 10px;
                margin: 10px;
            }

            .major-info {font-size: 18px; white-space: pre-line;}
            .minor-info {font-size: 12px; white-space: pre-line;}
            """)
    with document:
        tags.h1(get_title(location_info))
        tags.hr()

        # Any warnings displayed.
        warnings = data.get_future_warnings(location_id)
        if warnings:
            tags.h2("Warnings")
            if len(warnings) == 1:
                tags.p(f"There is currently 1 weather warning in place.")
            else:
                tags.p(
                    f"There are currently {len(warnings)} "
                    "weather warnings in place.")
            for warning in warnings:
                start = warning.start.strftime("%Y-%m-%d at %H:%M")
                end = warning.end.strftime("%Y-%m-%d at %H:%M")
                issued = warning.issued.strftime("%Y-%m-%d at %H:%M")
                with tags.div(cls=WARNING_CLASSES[warning.level]):
                    tags.h3(
                        f"{warning.level} warning "
                        f"for {warning.weather_type} "
                        f"{'(ACTIVE)' if warning.active else ''}")
                    tags.p(f"Start{'ed' if warning.active else 's'}: {start}")
                    tags.p(f"Ends: {end}")
                    with tags.p(__pretty=False):
                        tags.em(warning.description)
                    tags.p(f"Issued: {issued}")
            tags.hr()

        # Hourly forecast.
        tags.h2("The next few hours...")
        hourly_weather = data.get_future_weather(location_id, FUTURE_HOURS)
        for weather_info in hourly_weather:
            # Only show HH:MM, not HH:MM:SS
            tags.h3(f"{weather_info.date_time.time().strftime('%H:%M')}")
            temperature_class = get_temperature_class(weather_info.temperature)
            feels_like_temperature_class = get_temperature_class(
                weather_info.feels_like_temperature)
            precipitation_class = get_precipitation_class(
                weather_info.precipitation_odds)
            visibility_class = VISIBILITY_CLASSES[weather_info.visibility]
            with tags.p(__pretty=False):
                with tags.span(cls="major-info"):
                    text(f"Weather Type: {weather_info.weather_type}\n", False)
                    text("Temperature: ", False)
                    tags.span(
                        f"{weather_info.temperature}°C", cls=temperature_class)
                    text(" (feels like ", False)
                    tags.span(
                        f"{weather_info.feels_like_temperature}°C",
                        cls=feels_like_temperature_class)
                    text(")\n")
                    text("Wind: ")
                    if weather_info.wind_speed >= get.GUSTS_MPH:
                        tags.span(
                            f"{weather_info.wind_speed}mph ", cls="gusts")
                    else:
                        text(f"{weather_info.wind_speed}mph ")
                    text(f"(from {weather_info.wind_direction})\n")
                with tags.span(cls="minor-info"):
                    text(f"Humidity: {weather_info.humidity}%\n")
                    text("Precipitation odds: ")
                    tags.span(
                        f"{weather_info.precipitation_odds}%",
                        cls=precipitation_class)
                    text(f"\nPressure: {weather_info.pressure}mb")
                    text("\nVisibility: ")
                    tags.span(weather_info.visibility, cls=visibility_class)
        tags.hr()

        # Daily forecast.
        tags.h2("The next few days...")
        daily_conditions = data.get_future_conditions(location_id, FUTURE_DAYS)
        for conditions in daily_conditions:
            tags.h3(str(conditions.date))
            max_temperature = conditions.max_temperature
            min_temperature = conditions.min_temperature
            sunrise = conditions.sunrise.strftime("%H:%M")
            sunset = conditions.sunset.strftime("%H:%M")
            max_temperature_class = get_temperature_class(max_temperature)
            min_temperature_class = get_temperature_class(min_temperature)
            uv_class = get_uv_class(conditions.uv)
            with tags.p(__pretty=False).add(tags.div(cls="major-info")):
                text("Max / Min temperature: ")
                tags.span(f"{max_temperature}°C", cls=max_temperature_class)
                text(" / ")
                tags.span(f"{min_temperature}°C", cls=min_temperature_class)
                text(f"\nSunrise / Sunset: {sunrise} / {sunset}")
                text(f"\nUV Index: ")
                tags.span(conditions.uv, cls=uv_class)
                if conditions.pollution is not None:
                    pollution_class = get_pollution_class(conditions.pollution)
                    text(f"\nPollution Index: ")
                    tags.span(conditions.pollution, cls=pollution_class)
                if conditions.pollen is not None:
                    pollen_class = get_pollen_class(conditions.pollen)
                    text(f"\nPollen Index:")
                    tags.span(conditions.pollen, cls=pollen_class)
        tags.hr()

        # Footer information.
        text(f"Data obtained at: {location_info.last_updated}")
        url = f"{get.BBC_WEATHER_BASE_URL}/{location_id}"
        with tags.p(__pretty=False):
            text("Weather Page: ")
            tags.a(url, href=url)

    return document.render()


def get_recipients_string(recipients: list[str]) -> str:
    """Returns an appropriate string displaying the recipients."""
    if len(recipients) == 1:
        return recipients[0]
    if len(recipients) == 2:
        return f"{recipients[0]} and {recipients[1]}"
    if len(recipients) == 3:
        return f"{recipients[0]}, {recipients[1]} and {recipients[2]}"
    return f"{recipients[0]}, {recipients[1]} and {len(recipients) - 2} others"


def send_email(email_info: data.EmailInfo, subject: str, body: str) -> None:
    """Sends the weather report HTML email."""
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = email_info.sender
    # To avoid unnecessary email address leakage, 
    # recipients receive blind carbon copies.
    message["Bcc"] = ", ".join(email_info.recipients)
    message.attach(MIMEText(body, "html"))
    # Attempts email sending multiple times before giving up.
    attempts = MAX_EMAIL_SEND_ATTEMPTS
    while True:
        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(email_info.sender, email_info.password)
                smtp.send_message(message)
                return
        except Exception as e:
            attempts -= 1
            if not attempts:
                raise e
            time.sleep(1)


def main() -> None:
    """Main procedure of the script."""
    data.create_missing_tables()
    last_sent_time = None
    while True:
        current_date_time = dt.datetime.now()
        # Extract current time in HH:MM.
        current_time = current_date_time.time().replace(
            second=0, microsecond=0)
        # Critical - ensure only 1 email sent for a given time (HH:MM) to send.
        if current_time == last_sent_time:
            time.sleep(1)
            continue
        email_infos = data.get_email_infos()
        start = timer()
        for email_info in email_infos:
            if current_time not in email_info.times:
                continue
            location_info = data.get_location_info(email_info.location_id)
            email_body = generate_html_email(
                email_info.location_id, location_info)
            send_email(email_info, get_title(location_info), email_body)
            print(
                f"Successfully sent weather email from {email_info.sender} to "
                f"{get_recipients_string(email_info.recipients)} at "
                f"{current_date_time.strftime('%Y-%m-%d %H:%M')}")
        stop = timer()
        last_sent_time = current_time
        time.sleep(max(0, REFRESH_SECONDS - (stop - start)))


if __name__ == "__main__":
    main()
