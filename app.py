# backend/app.py
import os
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
import openai

load_dotenv()

app = Flask(__name__)
CORS(app)

# Config
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "replace_me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///database.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "jwt-secret")

db = SQLAlchemy(app)
jwt = JWTManager(app)

# OpenAI config
openai.api_key = os.environ.get("OPENAI_API_KEY")

# -------------------------------------------------
# Models
# -------------------------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))  # nullable if Google-only account
    location = db.Column(db.String(100), nullable=True)
    free_uses = db.Column(db.Integer, default=2)
    credits = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    google_id = db.Column(db.String(255), unique=True, nullable=True)

class Idea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    idea_text = db.Column(db.Text, nullable=False)
    analysis = db.Column(db.Text, nullable=True)
    score = db.Column(db.Integer, nullable=True)
    location = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def get_user_by_email(email):
    return User.query.filter_by(email=email).first()

def create_user(email, password=None, location=None, google_id=None):
    u = User(email=email, location=location)
    if password:
        u.password_hash = generate_password_hash(password)
    if google_id:
        u.google_id = google_id
    db.session.add(u)
    db.session.commit()
    return u

# For play verification placeholder
def verify_play_purchase_placeholder(package_name, product_id, purchase_token):
    """
    PLACEHOLDER. Replace with real Google Play Developer API verification.
    For dev, you can enable ALLOW_FAKE_PURCHASES=1 in env to bypass.
    """
    if os.environ.get("ALLOW_FAKE_PURCHASES") == "1":
        return True
    return False

# -------------------------------------------------
# Routes
# -------------------------------------------------

@app.route("/api/register", methods=["POST"])
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
    access_token = create_access_token(identity=user.id, expires_delta=timedelta(days=30))
    return jsonify({"ok":True, "access_token":access_token, "user": {"email":user.email, "location":user.location}})

@app.route("/api/login", methods=["POST"])
def api_login():
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

@app.route("/api/google_login", methods=["POST"])
def api_google_login():
    """
    Mobile client can POST { email, google_id, location(optional) } after successful client-side Google Sign-In.
    Server will create or return user. (No secret used server-side.)
    """
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

# Protected analyze endpoint
@app.route("/api/analyze", methods=["POST"])
@jwt_required()
def api_analyze():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error":"User not found"}), 404

    data = request.get_json() or {}
    idea_text = data.get("idea")
    location = data.get("location") or user.location or "global"
    if not idea_text:
        return jsonify({"error":"idea required"}), 400

    # Check allowance
    used_free = user.free_uses <= 0
    if user.free_uses > 0:
        user.free_uses -= 1
        db.session.commit()
    elif user.credits and user.credits > 0:
        user.credits -= 1
        db.session.commit()
    else:
        # Payment required
        price_map = {
            "US/UK/EU/Canada": 300,
            "Australia/NZ": 200,
            "India/SE Asia/Africa": 50,
            "Other": 100
        }
        # approximate classification
        return jsonify({"error":"payment_required", "message":"No free uses or credits left"}), 402

    # Call OpenAI (Chat)
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role":"system","content":"You are a startup idea evaluator."},
                {"role":"user","content":f"Analyze this idea for feasibility and potential impact in {location}:\n\n{idea_text}\n\nGive a viability score (0-100) and short reasoning."}
            ],
            max_tokens=300,
        )
        analysis = resp.choices[0].message.content.strip()
        digits = "".join([c for c in analysis if c.isdigit()])
        score = int(digits[:3]) if digits else None
    except Exception as e:
        # revert consumption on failure
        if user.free_uses < 2:
            user.free_uses += 1
            db.session.commit()
        else:
            user.credits += 1
            db.session.commit()
        return jsonify({"error":"openai_error", "details": str(e)}), 500

    idea = Idea(user_id=user.id, idea_text=idea_text, analysis=analysis, score=score, location=location)
    db.session.add(idea)
    db.session.commit()

    return jsonify({"ok":True, "analysis":analysis, "score":score, "free_uses":user.free_uses, "credits":user.credits})

@app.route("/api/history", methods=["GET"])
@jwt_required()
def api_history():
    user_id = get_jwt_identity()
    ideas = Idea.query.filter_by(user_id=user_id).order_by(Idea.created_at.desc()).all()
    out = [{"id":i.id,"idea_text":i.idea_text,"analysis":i.analysis,"score":i.score,"location":i.location,"created_at":i.created_at.isoformat()} for i in ideas]
    return jsonify({"ok":True, "ideas":out})

@app.route("/api/add_credits", methods=["POST"])
@jwt_required()
def api_add_credits():
    """
    Called by Android client after a Play Billing purchase.
    Body: { packageName, productId, purchaseToken, creditsAmount }
    NOTE: This endpoint currently uses a placeholder verification. Replace with real verification.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.get_json() or {}
    package_name = data.get("packageName")
    product_id = data.get("productId")
    purchase_token = data.get("purchaseToken")
    credits = int(data.get("creditsAmount", 1))

    if not (package_name and product_id and purchase_token):
        return jsonify({"error":"packageName, productId and purchaseToken required"}), 400

    # verify with Play Developer API (placeholder)
    ok_verified = verify_play_purchase_placeholder(package_name, product_id, purchase_token)
    if not ok_verified:
        return jsonify({"error":"purchase_not_verified"}), 400

    user.credits += credits
    db.session.commit()
    return jsonify({"ok":True, "credits": user.credits})

# Health
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok":True, "time": datetime.utcnow().isoformat()})

if __name__ == "__main__":
    app.run(debug=(os.environ.get("FLASK_DEBUG","1")=="1"), host="0.0.0.0", port=int(os.environ.get("PORT",5000)))










