"""Automated email sending tool based on the collected weather data."""
import datetime as dt

import dominate
import dominate.tags as tags

import data
import get


FUTURE_HOURS = 6


def generate_html_email(
    location_id: int, location_info: data.LocationInfo
) -> str:
    """
    Takes the weather data for a given location info and 
    generates a HTML report ready to send as an email.
    """
    document = dominate.document(
        title=f"Weather Report for {location_info.name}, {location_info.region}")
    # Set report CSS.
    with document.head:
        tags.style(
            r"""
            * {
                font-family: sans-serif;
            }
            h1 {
                font-size: 50px;
            }
            p {
                white-space: pre-line;
            }
            """)
    with document:
        tags.h1(
            f"Weather Report for {location_info.name}, {location_info.region}")
        tags.h2("The next few hours...")
        hourly_weather = data.get_future_weather(location_id, FUTURE_HOURS)
        for weather_info in hourly_weather:
            # Only show HH:MM, not HH:MM:SS
            tags.h3(
                f"{weather_info.date_time.time().strftime('%H:%M')}")
            weather_type = get.WEATHER_TYPES[weather_info.weather_type]
            visibility = get.VISIBILITIES_REVERSED[weather_info.visibility]
            tags.p(
                f"Weather Type: {weather_type}\n"
                f"Temperature: {weather_info.temperature}°C\n"
                f"Feels like: {weather_info.feels_like_temperature}°C\n"
                f"Wind: {weather_info.wind_speed}mph "
                f"(from {weather_info.wind_direction})\n"
                f"Humidity: {weather_info.humidity}%\n"
                f"Precipitation odds: {weather_info.precipitation_odds}%\n"
                f"Visibility: {visibility}")

    return str(document)


def main() -> None:
    """Main procedure of the script."""
    data.create_missing_tables()
    while True:
        current_time = dt.datetime.now().time().replace(
            second=0, microsecond=0)
        email_infos = data.get_email_infos()
        for email_info in email_infos:
            if not any(
                send_time == current_time for send_time in email_info.times
            ):
                continue
            print(
                f"Sending weather email from {email_info.sender} to "
                f"{email_info.recipient} at {current_time.strftime('%H:%M')}")
            location_info = data.get_location_info(email_info.location_id)
            email_body = generate_html_email(
                email_info.location_id, location_info)


if __name__ == "__main__":
    main()
