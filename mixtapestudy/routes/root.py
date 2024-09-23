from flask import jsonify, request, render_template, Blueprint

root = Blueprint("root", __name__)


@root.route("/")
def home() -> str:
    return render_template("login.html.j2")


@root.route("/info")
def info():
    resp = {
        "connecting_ip": request.headers["X-Real-IP"],
        "proxy_ip": request.headers["X-Forwarded-For"],
        "host": request.headers["Host"],
        "user-agent": request.headers["User-Agent"],
    }

    return jsonify(resp)


@root.route("/flask-health-check")
def flask_health_check():
    return "success"
