from flask import (
    Blueprint,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    session,
)

root = Blueprint("root", __name__)


@root.route("/")
def home() -> str | Response:
    if session.get("id"):
        return redirect("/search")
    return render_template("login.html.j2")


@root.route("/info")
def info() -> Response:
    resp = {
        "connecting_ip": request.headers["X-Real-IP"],
        "proxy_ip": request.headers["X-Forwarded-For"],
        "host": request.headers["Host"],
        "user-agent": request.headers["User-Agent"],
    }

    return jsonify(resp)


@root.route("/flask-health-check")
def flask_health_check() -> str:
    return "success"
