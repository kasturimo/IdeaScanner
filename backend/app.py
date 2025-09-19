import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import check_password_hash

from helpers import create_user, get_user_by_email, verify_play_purchase
from models import db, User

app = Flask(__name__)
CORS(app)

# Config
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///ideascanner.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "super-secret-key")

db.init_app(app)
jwt = JWTManager(app)


@app.route("/")
def home():
    return jsonify({"message": "IdeaScanner backend is running"})


# --------------------------
# Auth endpoints
# --------------------------

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    location = data.get("location")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if get_user_by_email(email):
        return jsonify({"error": "User already exists"}), 400

    user = create_user(email=email, password=password, location=location)
    return jsonify({"message": "User registered successfully", "user_id": user.id})


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = get_user_by_email(email)
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid credentials"}), 401

    access_token = create_access_token(identity=user.id)
    return jsonify({"access_token": access_token, "user_id": user.id})


@app.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    return jsonify({"id": user.id, "email": user.email, "location": user.location})


# --------------------------
# Purchase verification
# --------------------------

@app.route("/verify_purchase", methods=["POST"])
@jwt_required()  # require login to verify purchases
def verify_purchase():
    data = request.json
    purchase_token = data.get("purchase_token")
    product_id = data.get("product_id")

    if not purchase_token or not product_id:
        return jsonify({"error": "Missing purchase_token or product_id"}), 400

    try:
        ok = verify_play_purchase("com.ideascanner", product_id, purchase_token)
        if ok:
            return jsonify({"status": "success", "message": "Purchase verified"})
        else:
            return jsonify({"status": "failed", "message": "Purchase not valid"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# --------------------------
# Init
# --------------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)















