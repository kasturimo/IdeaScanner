from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
import stripe
import openai
import os
from datetime import datetime
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///database.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Mail setup
app.config['MAIL_SERVER'] = os.environ.get("MAIL_SERVER")
app.config['MAIL_PORT'] = int(os.environ.get("MAIL_PORT", 587))
app.config['MAIL_USE_TLS'] = os.environ.get("MAIL_USE_TLS") == "True"
app.config['MAIL_USERNAME'] = os.environ.get("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.environ.get("MAIL_PASSWORD")
mail = Mail(app)

# Token generator
s = URLSafeTimedSerializer(app.secret_key)

# CORS
CORS(app, supports_credentials=True)

# OpenAI
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Stripe
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY")

# OAuth setup
oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    access_token_url="https://accounts.google.com/o/oauth2/token",
    access_token_params=None,
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    authorize_params={"prompt": "consent", "access_type": "offline"},
    api_base_url="https://www.googleapis.com/oauth2/v1/",
    userinfo_endpoint="https://www.googleapis.com/oauth2/v1/userinfo",
    client_kwargs={"scope": "openid email profile"},
)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(200))
    location = db.Column(db.String(100))
    is_verified = db.Column(db.Boolean, default=False)
    is_google = db.Column(db.Boolean, default=False)
    analysis_count = db.Column(db.Integer, default=0)

class Idea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    idea_text = db.Column(db.String(500), nullable=False)
    analysis = db.Column(db.String(2000))
    location = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# Utility: send verification email
def send_verification_email(user_email):
    token = s.dumps(user_email, salt="email-verify")
    link = url_for("verify_email", token=token, _external=True)
    msg = Message("Confirm your account", sender=app.config['MAIL_USERNAME'], recipients=[user_email])
    msg.body = f"Click the link to verify your email: {link}"
    mail.send(msg)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        location = request.form.get("location")

        if User.query.filter_by(email=email).first():
            return jsonify({"error": "User already exists!"}), 400

        hashed_pw = generate_password_hash(password)
        new_user = User(email=email, password=hashed_pw, location=location, is_verified=False)
        db.session.add(new_user)
        db.session.commit()
        send_verification_email(email)
        return "Signup successful! Please check your email to verify your account."
    return render_template("signup.html")

@app.route("/verify/<token>")
def verify_email(token):
    try:
        email = s.loads(token, salt="email-verify", max_age=3600)
    except (SignatureExpired, BadSignature):
        return "Verification link expired or invalid."
    user = User.query.filter_by(email=email).first()
    if user:
        user.is_verified = True
        db.session.commit()
        return redirect(url_for("login"))
    return "User not found."

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            if not user.is_verified:
                return "Please verify your email before logging in."
            session["user_id"] = user.id
            return redirect(url_for("dashboard"))
        return jsonify({"error": "Invalid credentials!"}), 401
    return render_template("login.html")

@app.route("/google-login")
def google_login():
    redirect_uri = url_for("google_authorize", _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/google-authorize")
def google_authorize():
    token = google.authorize_access_token()
    resp = google.get("userinfo").json()
    email = resp["email"]

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, is_verified=True, is_google=True)
        db.session.add(user)
        db.session.commit()

    session["user_id"] = user.id
    return redirect(url_for("dashboard"))

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    analysis, score = None, None

    if request.method == "POST":
        if user.analysis_count >= 2:  # enforce freemium
            return redirect(url_for("pricing"))

        idea_text = request.form.get("idea")
        location = request.form.get("location") or user.location
        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a startup idea evaluator."},
                    {"role": "user", "content": f"Analyze this idea in {location}: {idea_text}. Give a viability score (0-100) and reasoning."}
                ],
                max_tokens=300,
            )
            analysis = response.choices[0].message.content.strip()
            score = "".join([c for c in analysis if c.isdigit()])
            score = int(score[:3]) if score else None
        except Exception as e:
            analysis = f"Error analyzing idea: {str(e)}"

        new_idea = Idea(user_id=user.id, idea_text=idea_text, analysis=analysis, location=location)
        db.session.add(new_idea)
        user.analysis_count += 1
        db.session.commit()

    return render_template("dashboard.html", analysis=analysis, score=score)

@app.route("/pricing")
def pricing():
    return render_template("pricing.html", key=PUBLISHABLE_KEY)

@app.route("/checkout", methods=["POST"])
def checkout():
    country = request.form.get("country", "Other")
    prices = {"US": 300, "UK": 300, "EU": 300, "Canada": 300,
              "Australia": 200, "NZ": 200,
              "India": 50, "SE Asia": 50, "Africa": 50,
              "Other": 100}
    amount = prices.get(country, 100)

    session_checkout = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": "Idea Analysis Credits"},
                "unit_amount": amount,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=url_for("dashboard", _external=True),
        cancel_url=url_for("pricing", _external=True),
    )
    return redirect(session_checkout.url, code=303)

@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect(url_for("login"))
    ideas = Idea.query.filter_by(user_id=session["user_id"]).order_by(Idea.created_at.desc()).all()
    return render_template("history.html", ideas=ideas)

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))






