import os

from datetime import datetime

from flask import Flask, request, jsonify

from homelog import database


app = Flask(__name__)

db = database.connect()


@app.before_request
def check_api_key():
    api_key = request.headers.get("x-api-key")
    if api_key != os.getenv("HOMELOG_API_KEY"):
        return jsonify({"error": "Unauthorized"}), 401


@app.route("/api/<model>", methods=["POST"])
def api_model(model):
    data = request.json
    if not data:
        msg = "No JSON data"
        app.logger.error(msg)
        return jsonify({"error": msg}), 400
    app.logger.debug(model)
    app.logger.debug(data)
    table = db.get_table(model)
    created_at = datetime.utcnow()
    try:
        data = {k: float(v) for k, v in data.items()}
    except ValueError as e:
        msg = f"VALUE_NOT_FLOATABLE ({model}, {data}): {e}"
        app.logger.error(msg)
        return jsonify({"error": msg}), 400
    for k, v in data.items():
        table.insert({
            "value": float(v),
            "measurement": str(k),
            "created_at": created_at,
        })
    return jsonify({"error": None}), 201
