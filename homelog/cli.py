from minicli import cli, run

from homelog import database
from homelog.notify import send

db = database.connect()


@cli
def notify_temp_cross():
    """Notify when outside temperature crosses inside's when going down"""
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
    if last_salon["value"] >= last_patio["value"] and before_last_salon["value"] < before_last_patio["value"]:
        send("T° salon dépasse la température extérieure", f"{last_salon['value']} vs {last_patio['value']}")

    # crosses chambre and first cross
    if last_chambre["value"] >= last_patio["value"] and before_last_chambre["value"] < before_last_patio["value"]:
        send("T° chambre dépasse la température extérieure", f"{last_chambre['value']} vs {last_patio['value']}")


if __name__ == "__main__":
    run()
