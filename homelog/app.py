import base64
import os

from datetime import datetime, date, timedelta
from io import BytesIO
from zoneinfo import ZoneInfo

import pandas as pd
import sentry_sdk

from flask import Flask, request, jsonify, render_template, abort, Response, redirect, url_for
from matplotlib.figure import Figure
from sentry_sdk.integrations.flask import FlaskIntegration
from werkzeug.datastructures import MultiDict

from homelog import database
from homelog.models import Measurement


if sentry_dsn := os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[
            FlaskIntegration(),
        ],
    )

app = Flask(__name__)


@app.template_filter("local_datetime")
def to_local_datetime(value: datetime):
    # NB: utc timezone is attached to date in Measurement model
    tzinfo = ZoneInfo(os.getenv("HOMELOG_TZ"))
    return value.astimezone(tzinfo).strftime("%Y-%m-%d %H:%M")


@app.context_processor
def inject_globals():
    return dict(utcnow=datetime.utcnow)


def compute_filters(request_args: MultiDict, columns: list) -> dict:
    """Filters in args like `measurement=value`, `created_at__gt=value`..."""
    filters = {}
    for k, v in request_args.items(multi=True):
        if not any(k.startswith(c) for c in columns):
            continue
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
    db = database.get()
    if model not in db.tables:
        abort(404)
    # apply a default filter for created_at > today if none given
    if not any(arg.startswith("created_at") for arg in request.args.keys()):
        created_at = date.today()
        return redirect(url_for("model_table", model=model, created_at__gt=created_at, **request.args))
    table = db.get_table(model)
    filters = compute_filters(request.args, table.columns)
    records = Measurement.query(model, **filters, order_by="-created_at")
    return render_template("table.html.j2", records=records, model=model, dates={
        "today": date.today().isoformat(),
        "last_week": (date.today() - timedelta(days=7)).isoformat(),
        "last_month": (date.today() - timedelta(days=30)).isoformat(),
    })


@app.route("/<model>/plot")
def model_plot(model):
    db = database.get()
    if model not in db.tables:
        abort(404)
    table = db.get_table(model)

    plot_kind = request.args.get("_kind", "line")
    resample_freq = request.args.get("_resample")

    filters = compute_filters(request.args, table.columns)
    records = Measurement.query(model, **filters, order_by="-created_at")

    df = pd.DataFrame([r.dict() for r in records])
    df = df.set_index("created_at")
    df.index = df.index.tz_convert(os.getenv("HOMELOG_TZ"))
    if df.empty:
        return "No data", 404

    fig = Figure()
    ax = fig.subplots()
    if resample_freq:
        df_resampled = df.groupby("measurement").resample(resample_freq).mean()
        df_resampled.unstack(level=0).plot(kind="bar", ax=ax, figsize=(10, 5))
    else:
        df.groupby("measurement")["value"].plot(
            title=f"{model}({filters})", legend=True, ax=ax, figsize=(10, 5), kind=plot_kind,
        )
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    data = base64.b64encode(buf.getbuffer()).decode("ascii")

    return f"<img src='data:image/png;base64,{data}'/>"


@app.route("/<model>/csv")
def model_csv(model):
    db = database.get()
    if model not in db.tables:
        abort(404)
    table = db.get_table(model)
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
    db = database.get()
    data = request.json
    if not data:
        msg = "No JSON data"
        app.logger.error(msg)
        return jsonify({"error": msg}), 400
    app.logger.debug(model)
    app.logger.debug(data)
    table = db.get_table(model)
    if created_at := data.pop("created_at", None):
        created_at = datetime.fromisoformat(created_at)
    else:
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
