import os

from datetime import datetime

import httpx

from minicli import cli, run

from homelog import database
from homelog.models import Measurement
from homelog.notify import send


@cli
def notify_temp_cross():
    """Notify when outside temperature crosses inside's when going down"""
    db = database.connect()
    table = db.get_table("temperature")

    last_salon = table.find_one(measurement="salon", _limit=1, _offset=0, order_by="-created_at")
    last_chambre = table.find_one(measurement="chambre", _limit=1, _offset=0, order_by="-created_at")
    last_patio = table.find_one(measurement="patio", _limit=1, _offset=0, order_by="-created_at")

    before_last_salon = table.find_one(measurement="salon", _limit=1, _offset=1, order_by="-created_at")
    before_last_chambre = table.find_one(measurement="chambre", _limit=1, _offset=1, order_by="-created_at")
    before_last_patio = table.find_one(measurement="patio", _limit=1, _offset=1, order_by="-created_at")

    # going up?
    if not before_last_patio["value"] >= last_patio["value"]:
        return

    # crosses salon and first cross
    if last_salon["value"] >= last_patio["value"] and before_last_salon["value"] <= before_last_patio["value"]:
        send("T° salon dépasse la température extérieure", f"{last_salon['value']} vs {last_patio['value']}")

    # crosses chambre and first cross
    if last_chambre["value"] >= last_patio["value"] and before_last_chambre["value"] <= before_last_patio["value"]:
        send("T° chambre dépasse la température extérieure", f"{last_chambre['value']} vs {last_patio['value']}")


@cli
def sync_weather():
    db = database.connect()
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


if __name__ == "__main__":
    run()
