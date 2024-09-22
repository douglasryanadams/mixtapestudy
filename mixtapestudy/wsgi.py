from app import app
import os

if __name__ == "__main__":
    app.run(
        host="0.0.0.0", port=int(os.environ.get("FLASK_SERVER_PORT", 5000)), debug=True
    )
