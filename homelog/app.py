import base64
import os

from datetime import datetime
from io import BytesIO

import pandas as pd

from flask import Flask, request, jsonify, render_template, abort, Response, g
from matplotlib.figure import Figure
from werkzeug.datastructures import MultiDict

from homelog import database
from homelog.models import Measurement


app = Flask(__name__)


@app.before_request
def connect_db():
    if not g.get("db"):
        g.db = database.connect()


@app.template_filter("datetime")
def format_datetime(value: datetime):
    return value.strftime("%Y-%m-%d %H:%M")


def compute_filters(request_args: MultiDict, columns: list) -> dict:
    """Filters in args like `measurement=value`, `created_at__gt=value`..."""
    filters = {}
    for k, v in request_args.items(multi=True):
        if not any(k.startswith(c) for c in columns):
            pass
        if len(splitted := k.split("__")) > 1:
            if splitted[0] in filters:
                filters[splitted[0]][splitted[1]] = v
            else:
                filters[splitted[0]] = {splitted[1]: v}
        else:
            if k in filters:
                filters[k]["in"].append(v)
            else:
                filters[k] = {"in": [v]}
    app.logger.debug(f"filters: {filters}")
    return filters


@app.route("/<model>/table")
def model_table(model):
    if model not in g.db.tables:
        abort(404)
    table = g.db.get_table(model)
    filters = compute_filters(request.args, table.columns)
    records = table.find(**filters, order_by="-created_at")
    return render_template("table.html.j2", records=records)


@app.route("/<model>/plot")
def model_plot(model):
    if model not in g.db.tables:
        abort(404)
    table = g.db.get_table(model)
    filters = compute_filters(request.args, table.columns)
    records = table.find(**filters, order_by="-created_at")
    df = pd.DataFrame(records)
    fig = Figure()
    ax = fig.subplots()
    df.set_index("created_at").groupby("measurement")["value"].plot(
        title=f"{model}({filters})", legend=True, ax=ax, figsize=(10, 5)
    )
    buf = BytesIO()
    fig.savefig(buf, format="png")
    data = base64.b64encode(buf.getbuffer()).decode("ascii")
    return f"<img src='data:image/png;base64,{data}'/>"


@app.route("/<model>/csv")
def model_csv(model):
    if model not in g.db.tables:
        abort(404)
    table = g.db.get_table(model)
    filters = compute_filters(request.args, table.columns)
    records = table.find(**filters, order_by="-created_at")

    def iter_csv(records):
        yield "created_at,measurement,value\n"
        for r in records:
            yield f"{r['created_at']},{r['measurement']},{r['value']}\n"

    response = Response(iter_csv(records), mimetype="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={model}.csv"
    return response


@app.before_request
def check_api_key():
    """
    WARNING: only protects endpoint methods starting with `api_`
    """
    if not request.endpoint:
        return
    elif request.endpoint.startswith("api_"):
        api_key = request.headers.get("x-api-key")
        if api_key != os.getenv("HOMELOG_API_KEY"):
            return jsonify({"error": "Unauthorized"}), 401


@app.route("/api/status")
def unprotected_api_status():
    return jsonify({"status": "ok"})


@app.route("/api/<model>", methods=["POST"])
def api_model(model):
    data = request.json
    if not data:
        msg = "No JSON data"
        app.logger.error(msg)
        return jsonify({"error": msg}), 400
    app.logger.debug(model)
    app.logger.debug(data)
    table = g.db.get_table(model)
    created_at = datetime.utcnow()
    try:
        data = {k: float(v) for k, v in data.items()}
    except ValueError as e:
        msg = f"VALUE_NOT_FLOATABLE ({model}, {data}): {e}"
        app.logger.error(msg)
        return jsonify({"error": msg}), 400
    for k, v in data.items():
        measurement = Measurement(**{
            "value": v,
            "measurement": k,
            "created_at": created_at,
        })
        table.insert(measurement.dict())
    return jsonify({"error": None}), 201
