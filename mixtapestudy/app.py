from pathlib import Path

from flask import Flask, request, jsonify, render_template, Response, send_from_directory

app = Flask(__name__)


@app.route("/")
def login() -> str:
    return render_template("login.html.j2")


@app.route("/info")
def info():
    resp = {
        "connecting_ip": request.headers["X-Real-IP"],
        "proxy_ip": request.headers["X-Forwarded-For"],
        "host": request.headers["Host"],
        "user-agent": request.headers["User-Agent"],
    }

    return jsonify(resp)


@app.route("/flask-health-check")
def flask_health_check():
    return "success"
