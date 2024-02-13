"""Automated email sending tool based on the collected weather data."""
import datetime as dt

import dominate
import dominate.tags as tags
from dominate.util import text

import data
import get


FUTURE_HOURS = 6
FUTURE_DAYS = 2
TEMPERATURE_CLASSES = {
    "hottest": 45, "hotter": 35, "warm": 20,
    "mild": 10, "cool": 5, "colder": -10, "coldest": -100
}
PRECIPITATION_ODDS_CLASSES = {
    "precip_likely": 75, "precip_chance": 25, "precip_unlikely": 0
}
VISIBILITY_CLASSES = {
    get.Visibility.excellent: "excellent_visibility",
    get.Visibility.very_good: "very_good_visibility",
    get.Visibility.good: "good_visibility",
    get.Visibility.moderate: "moderate_visibility",
    get.Visibility.poor: "poor_visibility",
    get.Visibility.very_poor: "very_poor_visibility"
}
UV_CLASSES = {
    "extreme_uv": 11, "very_high_uv": 8, "high_uv": 6,
    "moderate_uv": 3, "low_uv": 0
}
POLLUTION_CLASSES = {
    "very_high_pollution": 10, "high_pollution": 7,
    "moderate_pollution": 4, "low_pollution": 0
}
# Just a guess - can improve on durring pollen season when mass data available.
POLLEN_CLASSES = {
    "very_high_pollen": 10, "high_pollen": 7,
    "moderate_pollen": 4, "low_pollen": 0
}


def _get_class(value: int, classes: dict[str, int]) -> str:
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
                font-size: 40px;
            }
            p {
                white-space: pre-line;
            }
            span {
                white-space: nowrap;
            }

            .hottest {color: #c21a11;}
            .hotter {color: #f02318;}
            .warm {color: #f07f0e;}
            .mild {color: #17c223;}
            .cool {color: #0ca9f7;}
            .colder {color: #0c86f7;}
            .coldest {color: #267bc9;}

            .extreme_uv {color: violet;}
            .gusts, .precip_likely, .very_poor_visibility,
                .very_high_uv, .very_high_pollution {color: red;}
            .precip_chance, .poor_visibility, .high_uv,
                .high_pollution {color: orange;}
            .moderate_uv, .moderate_pollution {color: #c3eb34;}
            .moderate_visibility, .good_visibility, .low_uv,
                .low_pollution {color: #00cc00;}
            .very_good_visibility, .excellent_visibility {color: #0ca9f7;}
            """)
    with document:
        tags.h1(
            f"Weather Report for {location_info.name}, {location_info.region}")
        tags.hr()
        # Hourly forecast.
        tags.h2("The next few hours...")
        hourly_weather = data.get_future_weather(location_id, FUTURE_HOURS)
        for weather_info in hourly_weather:
            # Only show HH:MM, not HH:MM:SS
            tags.h3(f"{weather_info.date_time.time().strftime('%H:%M')}")
            weather_type = get.WEATHER_TYPES[weather_info.weather_type]
            visibility = get.VISIBILITIES_REVERSED[weather_info.visibility]

            temperature_class = get_temperature_class(weather_info.temperature)
            feels_like_temperature_class = get_temperature_class(
                weather_info.feels_like_temperature)
            precipitation_class = get_precipitation_class(
                weather_info.precipitation_odds)
            visibility_class = VISIBILITY_CLASSES[weather_info.visibility]
            with tags.p(__pretty=False):
                text(f"Weather Type: {weather_type}\n", False)
                text(f"Temperature: ", False)
                tags.span(
                    f"{weather_info.temperature}°C", cls=temperature_class)
                text(f" (feels like ", False)
                tags.span(
                    f"{weather_info.feels_like_temperature}°C",
                    cls=feels_like_temperature_class)
                text(")\n")
                text(f"Wind: ")
                if weather_info.wind_speed >= get.GUSTS_MPH:
                    tags.span(f"{weather_info.wind_speed}mph ", cls="gusts")
                else:
                    text(f"{weather_info.wind_speed}mph ")
                text(f"(from {weather_info.wind_direction})\n")
                text(f"Humidity: {weather_info.humidity}%\n")
                text("Precipitation odds: ")
                tags.span(
                    f"{weather_info.precipitation_odds}%",
                    cls=precipitation_class)
                text(f"\nPressure: {weather_info.pressure}mb")
                text("\nVisibility: ")
                tags.span(f"{visibility}", cls=visibility_class)
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
            with tags.p(__pretty=False):
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
