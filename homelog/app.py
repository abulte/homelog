from flask import Flask, request


app = Flask(__name__)


@app.route("/api/temperature", methods=["POST"])
def api_temperature():
    data = request.json
    print(data)
    return "ok", 201
