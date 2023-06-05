import os

from flask import Flask, request


app = Flask(__name__)


@app.before_request
def check_api_key():
    api_key = request.headers.get("x-api-key")
    if api_key != os.getenv("HOMELOG_API_KEY"):
        return "Unauthorized", 401


@app.route("/api/temperature", methods=["POST"])
def api_temperature():
    data = request.json
    print(data)
    return "ok", 201
