import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from models import db
from helpers import get_user_by_email, create_user

# --- Flask setup ---
app = Flask(__name__)
CORS(app)

# Database config (use your own DB URL on Render or .env)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///ideas.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Init db + migrate
db.init_app(app)
migrate = Migrate(app, db)


@app.route("/")
def home():
    return jsonify({"message": "IdeaScanner backend is running with migrations"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
















