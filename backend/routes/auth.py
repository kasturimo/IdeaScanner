from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from datetime import timedelta
from models import User, db
from helpers import get_user_by_email, create_user

auth_bp = Blueprint("auth", __name__, url_prefix="/api")

@auth_bp.route("/register", methods=["POST"])
def api_register():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    location = data.get("location")
    if not email or not password:
        return jsonify({"error":"email and password required"}), 400
    if get_user_by_email(email):
        return jsonify({"error":"User already exists"}), 400
    user = create_user(email=email, password=password, location=location)
    token = create_access_token(identity=user.id, expires_delta=timedelta(days=30))
    return jsonify({"ok":True, "access_token":token, "user": {"email":user.email, "location":user.location}})

@auth_bp.route("/login", methods=["POST"])
def api_login():
    from werkzeug.security import check_password_hash
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return jsonify({"error":"email and password required"}), 400
    user = get_user_by_email(email)
    if not user or not user.password_hash or not check_password_hash(user.password_hash, password):
        return jsonify({"error":"Invalid credentials"}), 401
    token = create_access_token(identity=user.id, expires_delta=timedelta(days=30))
    return jsonify({"ok":True, "access_token":token, "user":{"email":user.email, "location":user.location}})

@auth_bp.route("/google_login", methods=["POST"])
def api_google_login():
    data = request.get_json() or {}
    email = data.get("email")
    google_id = data.get("google_id")
    location = data.get("location")
    if not email or not google_id:
        return jsonify({"error":"email and google_id required"}), 400
    user = get_user_by_email(email)
    if not user:
        user = create_user(email=email, google_id=google_id, location=location)
    else:
        if not user.google_id:
            user.google_id = google_id
            db.session.commit()
    token = create_access_token(identity=user.id, expires_delta=timedelta(days=30))
    return jsonify({"ok":True, "access_token":token, "user":{"email":user.email, "location":user.location}})
