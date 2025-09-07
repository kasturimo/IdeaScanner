import os
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
from models import db
from routes.auth import auth_bp
from routes.analyze import analyze_bp
from routes.history import history_bp
from routes.health import health_bp

load_dotenv()

app = Flask(__name__)
CORS(app)

# Config
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "replace_me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///database.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "jwt-secret")

# DB + JWT
db.init_app(app)
jwt = JWTManager(app)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(analyze_bp)
app.register_blueprint(history_bp)
app.register_blueprint(health_bp)

# Create tables
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=(os.environ.get("FLASK_DEBUG","1")=="1"), host="0.0.0.0", port=int(os.environ.get("PORT",5000)))











