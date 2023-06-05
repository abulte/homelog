import os

from datetime import datetime

from flask import Flask, request, jsonify, render_template, abort
from werkzeug.datastructures import MultiDict

from homelog import database


app = Flask(__name__)

db = database.connect()


@app.template_filter("datetime")
def format_datetime(value: datetime):
    return value.strftime("%Y-%m-%d %H:%M")


def compute_filters(request_args: MultiDict, columns: list) -> dict:
    """Filters in args like `measurement=value`, `created_at__gt=value`..."""
    filters = {}
    for k, v in request_args.items():
        if not any(k.startswith(c) for c in columns):
            pass
        if len(splitted := k.split("__")) > 1:
            if splitted[0] in filters:
                filters[splitted[0]][splitted[1]] = v
            else:
                filters[splitted[0]] = {splitted[1]: v}
        else:
            filters[k] = v
    app.logger.debug(f"filters: {filters}")
    return filters


@app.route("/<model>/table")
def model_table(model):
    if model not in db.tables:
        abort(404)
    table = db.get_table(model)
    filters = compute_filters(request.args, table.columns)
    records = table.find(**filters, order_by="-created_at")
    return render_template("table.html.j2", records=records)


@app.before_request
def check_api_key():
    if not request.endpoint:
        return
    elif request.endpoint.startswith("api_"):
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
