import csv
import os

from io import StringIO
from datetime import datetime

import httpx
import sentry_sdk

from minicli import cli, run

from homelog import database
from homelog.models import Measurement


if sentry_dsn := os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=sentry_dsn,
    )


@cli
def sync_weather():
    db = database.get()
    created_at = datetime.utcnow()

    attrs = [
        "temp_c", "condition.code", "wind_kph", "wind_degree", "pressure_mb", "precip_mm",
        "humidity", "cloud", "feelslike_c", "vis_km", "uv", "gust_kph",
        "air_quality.co", "air_quality.no2", "air_quality.o3", "air_quality.so2", "air_quality.pm2_5",
        "air_quality.pm10", "air_quality.us-epa-index", "air_quality.gb-defra-index",
    ]

    url = f"http://api.weatherapi.com/v1/current.json?key={os.getenv('WEATHERAPI_KEY')}&q=Poissy, France&aqi=yes"
    r = httpx.get(url)
    r.raise_for_status()

    table = db.get_table("weather")

    r_data = r.json()["current"]
    for attr in attrs:
        if len(splitted := attr.split(".")) > 1:
            value = r_data.get(splitted[0], {}).get(splitted[1])
        else:
            value = r_data.get(attr)
        if value is None:
            print(f"Missing value for {attr}")
        else:
            table.insert(Measurement(value=value, measurement=attr, created_at=created_at).dict())


@cli
def import_data(table, remote="https://homelog.app.france.sh"):
    """Import remote table to local through CSV"""
    url = f"{remote}/{table}/csv"
    r = httpx.get(url)
    r.raise_for_status()
    data = StringIO(r.text)
    reader = csv.DictReader(data)

    db = database.get()
    if table in db.tables:
        db[table].drop()

    for row in reader:
        db[table].insert(row)


if __name__ == "__main__":
    run()
