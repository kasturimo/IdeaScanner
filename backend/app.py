import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime

app = Flask(__name__)

# 🔹 Config
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "supersecret")

db = SQLAlchemy(app)
jwt = JWTManager(app)

# 🔹 Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    credits = db.Column(db.Integer, default=2)  # freemium: 2 free analysis
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 🔹 Google Play API setup
SERVICE_ACCOUNT_FILE = "google_play_service_account.json"  # upload this to Render
SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]

try:
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build("androidpublisher", "v3", credentials=credentials)
except Exception as e:
    service = None
    print(f"⚠️ Google Play API not initialized: {e}")

PACKAGE_NAME = "com.ideascanner"


# ================= AUTH =================
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email required"}), 400

    user = User.query.filter_by(email=email).first()
    if user:
        return jsonify({"error": "User already exists"}), 400

    new_user = User(email=email)
    db.session.add(new_user)
    db.session.commit()

    access_token = create_access_token(identity=new_user.id)
    return jsonify({"msg": "Registered", "access_token": access_token}), 201


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    access_token = create_access_token(identity=user.id)
    return jsonify({"msg": "Login successful", "access_token": access_token})


# ================= PURCHASE VERIFICATION =================
@app.route("/verify_purchase", methods=["POST"])
@jwt_required()
def verify_purchase():
    if not service:
        return jsonify({"error": "Google Play API not configured"}), 500

    data = request.json
    purchase_token = data.get("purchase_token")
    product_id = data.get("product_id")

    if not purchase_token or not product_id:
        return jsonify({"error": "Missing purchase_token or product_id"}), 400

    try:
        result = service.purchases().products().get(
            packageName=PACKAGE_NAME,
            productId=product_id,
            token=purchase_token
        ).execute()

        if result.get("purchaseState") == 0:  # ✅ purchased
            user_id = get_jwt_identity()
            user = User.query.get(user_id)

            # 🎯 Credit analysis to user (e.g., +5 per purchase)
            user.credits += 5
            db.session.commit()

            return jsonify({
                "status": "success",
                "message": "Purchase verified",
                "credits": user.credits
            })

        else:
            return jsonify({"status": "failed", "message": "Purchase not valid"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ================= DASHBOARD =================
@app.route("/dashboard", methods=["POST"])
@jwt_required()
def dashboard():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if user.credits <= 0:
        return jsonify({"error": "No credits left. Please purchase."}), 402

    data = request.json
    idea = data.get("idea")

    if not idea:
        return jsonify({"error": "Idea text is required"}), 400

    # Deduct credit
    user.credits -= 1
    db.session.commit()

    return jsonify({
        "msg": "Idea analyzed successfully",
        "remaining_credits": user.credits,
        "analysis": f"Your idea '{idea}' looks promising!"
    })


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)












