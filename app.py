from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from authlib.integrations.flask_client import OAuth
import openai
import stripe
import os
from datetime import datetime
from dotenv import load_dotenv

# Load env variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# --- OpenAI ---
openai.api_key = os.environ.get("OPENAI_API_KEY")

# --- Database ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///database.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- CORS ---
CORS(app, supports_credentials=True)

# --- Mail setup ---
app.config['MAIL_SERVER'] = "smtp.gmail.com"
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get("EMAIL_USER")
app.config['MAIL_PASSWORD'] = os.environ.get("EMAIL_PASS")
mail = Mail(app)

# --- Token serializer ---
s = URLSafeTimedSerializer(app.secret_key)

# --- Stripe setup ---
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
YOUR_DOMAIN = os.environ.get("DOMAIN", "http://localhost:5000")

# --- OAuth (Google) ---
oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    access_token_url="https://accounts.google.com/o/oauth2/token",
    access_token_params=None,
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    authorize_params=None,
    api_base_url="https://www.googleapis.com/oauth2/v1/",
    client_kwargs={"scope": "openid email profile"},
)

# --- Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200))
    location = db.Column(db.String(100))
    is_verified = db.Column(db.Boolean, default=False)
    analysis_count = db.Column(db.Integer, default=0)
    stripe_customer_id = db.Column(db.String(200))

class Idea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    idea_text = db.Column(db.String(500), nullable=False)
    analysis = db.Column(db.String(2000))
    location = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")

# --- Register with email ---
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        location = request.form.get("location")

        if User.query.filter_by(email=email).first():
            flash("User already exists", "danger")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password)
        new_user = User(email=email, password=hashed_pw, location=location)
        db.session.add(new_user)
        db.session.commit()

        token = s.dumps(email, salt="email-confirm")
        link = url_for("verify_email", token=token, _external=True)
        msg = Message("Confirm your account", sender=os.environ.get("EMAIL_USER"), recipients=[email])
        msg.body = f"Click the link to verify your account: {link}"
        mail.send(msg)

        flash("Check your email to verify your account.", "info")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/verify/<token>")
def verify_email(token):
    try:
        email = s.loads(token, salt="email-confirm", max_age=3600)
    except (SignatureExpired, BadSignature):
        flash("Verification link expired or invalid.", "danger")
        return redirect(url_for("login"))

    user = User.query.filter_by(email=email).first()
    if user:
        user.is_verified = True
        db.session.commit()
        flash("Your account is verified!", "success")
    return redirect(url_for("login"))

# --- Login with email ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, password):
            flash("Invalid credentials", "danger")
            return redirect(url_for("login"))

        if not user.is_verified:
            flash("Please verify your email first.", "warning")
            return redirect(url_for("login"))

        session["user_id"] = user.id
        return redirect(url_for("dashboard"))
    return render_template("login.html")

# --- Google login ---
@app.route("/login/google")
def login_google():
    redirect_uri = url_for("authorize_google", _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/authorize/google")
def authorize_google():
    token = google.authorize_access_token()
    resp = google.get("userinfo")
    user_info = resp.json()
    email = user_info["email"]

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, is_verified=True)  # Google auto-verified
        db.session.add(user)
        db.session.commit()

    session["user_id"] = user.id
    return redirect(url_for("dashboard"))

# --- Dashboard with freemium ---
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    analysis, score = None, None

    if request.method == "POST":
        if user.analysis_count >= 2 and not user.stripe_customer_id:
            return redirect(url_for("pricing"))

        idea_text = request.form.get("idea")
        location = request.form.get("location") or user.location

        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an idea analysis assistant."},
                    {"role": "user", "content": f"Analyze this startup idea for {location}: {idea_text}. Give viability score (0–100) and reasoning."}
                ],
                max_tokens=250,
            )
            analysis = response.choices[0].message["content"].strip()
            score = "".join([c for c in analysis if c.isdigit()])
            score = int(score[:3]) if score else None
        except Exception as e:
            analysis = f"Error analyzing idea: {str(e)}"

        new_idea = Idea(user_id=user.id, idea_text=idea_text, analysis=analysis, location=location)
        db.session.add(new_idea)
        user.analysis_count += 1
        db.session.commit()

    return render_template("dashboard.html", analysis=analysis, score=score)

# --- Pricing ---
@app.route("/pricing")
def pricing():
    return render_template("pricing.html")

# --- Stripe Checkout ---
@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    user = User.query.get(session["user_id"])
    country = user.location or "Other"

    prices = {
        "US": 300, "UK": 300, "EU": 300, "Canada": 300,
        "Australia": 200, "NZ": 200,
        "India": 50, "SE Asia": 50, "Africa": 50,
        "Other": 100,
    }
    amount = prices.get(country, 100)

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{"price_data": {"currency": "usd", "product_data": {"name": "Idea Analysis Subscription"}, "unit_amount": amount}, "quantity": 1}],
        mode="payment",
        success_url=YOUR_DOMAIN + "/success",
        cancel_url=YOUR_DOMAIN + "/cancel",
    )

    return redirect(checkout_session.url, code=303)

@app.route("/success")
def success():
    user = User.query.get(session["user_id"])
    user.stripe_customer_id = "paid"
    db.session.commit()
    return render_template("success.html")

@app.route("/cancel")
def cancel():
    return render_template("cancel.html")

# --- History ---
@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect(url_for("login"))
    ideas = Idea.query.filter_by(user_id=session["user_id"]).order_by(Idea.created_at.desc()).all()
    return render_template("history.html", ideas=ideas)

# --- Logout ---
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)








