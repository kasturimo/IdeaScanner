import os
import stripe
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash
from flask_dance.contrib.google import make_google_blueprint, google
from datetime import datetime
from openai import OpenAI

app = Flask(__name__)

# Secret keys
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# Database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///ideas.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Mail setup
app.config.update(
    MAIL_SERVER="smtp.gmail.com",
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.environ.get("MAIL_USERNAME"),
    MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD"),
)
mail = Mail(app)

# Token generator for email verification
s = URLSafeTimedSerializer(app.secret_key)

# Stripe setup
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
YOUR_DOMAIN = os.environ.get("YOUR_DOMAIN", "http://localhost:5000")

# OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Google login (Authlib)
google_bp = make_google_blueprint(
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    redirect_to="google_login",
    scope=["profile", "email"],
)
app.register_blueprint(google_bp, url_prefix="/login")

# =============================
# MODELS
# =============================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password = db.Column(db.String(200))
    verified = db.Column(db.Boolean, default=False)
    google_id = db.Column(db.String(200), unique=True, nullable=True)
    free_analyses = db.Column(db.Integer, default=0)

class Idea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    idea_text = db.Column(db.Text, nullable=False)
    analysis = db.Column(db.Text)
    viability_score = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

# =============================
# AUTH ROUTES
# =============================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])
        if User.query.filter_by(email=email).first():
            flash("Email already registered.")
            return redirect(url_for("register"))
        user = User(email=email, password=password)
        db.session.add(user)
        db.session.commit()
        # Send verification email
        token = s.dumps(email, salt="email-confirm")
        link = url_for("confirm_email", token=token, _external=True)
        msg = Message("Confirm Your Email", sender=app.config["MAIL_USERNAME"], recipients=[email])
        msg.body = f"Click the link to verify your account: {link}"
        mail.send(msg)
        flash("Check your email for a verification link.")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/confirm/<token>")
def confirm_email(token):
    try:
        email = s.loads(token, salt="email-confirm", max_age=3600)
    except SignatureExpired:
        return "The verification link expired."
    user = User.query.filter_by(email=email).first_or_404()
    user.verified = True
    db.session.commit()
    flash("Email verified! Please log in.")
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            if not user.verified:
                flash("Please verify your email first.")
                return redirect(url_for("login"))
            session["user_id"] = user.id
            return redirect(url_for("index"))
        flash("Invalid credentials.")
    return render_template("login.html")

@app.route("/google-login")
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login"))
    resp = google.get("/oauth2/v2/userinfo")
    info = resp.json()
    google_id = info["id"]
    email = info.get("email")

    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User(email=email, google_id=google_id, verified=True)
        db.session.add(user)
        db.session.commit()
    session["user_id"] = user.id
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# =============================
# STRIPE CHECKOUT
# =============================
def get_price_for_country(country):
    if country in ["US", "UK", "CA", "DE", "FR", "EU"]:
        return 300
    elif country in ["AU", "NZ"]:
        return 200
    elif country in ["IN", "SG", "ID", "PH", "MY", "TH", "NG", "ZA"]:
        return 50
    else:
        return 100

@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    country = request.form.get("country", "OTHER")
    price = get_price_for_country(country)
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[{"price_data": {"currency": "usd","product_data": {"name": "Premium Access"},"unit_amount": price},"quantity": 1}],
            mode="payment",
            success_url=YOUR_DOMAIN + "/success",
            cancel_url=YOUR_DOMAIN + "/cancel",
        )
    except Exception as e:
        return str(e)
    return redirect(checkout_session.url, code=303)

@app.route("/success")
def success():
    return render_template("success.html")

@app.route("/cancel")
def cancel():
    return render_template("cancel.html")

# =============================
# MAIN APP
# =============================
@app.route("/", methods=["GET", "POST"])
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if request.method == "POST":
        if user.free_analyses >= 2:
            flash("Free limit reached! Please upgrade.")
            return redirect(url_for("profile"))

        idea_text = request.form["idea"]
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "You are an idea evaluator."},
                          {"role": "user", "content": idea_text}],
                max_tokens=300,
            )
            analysis = response.choices[0].message.content
            viability_score = 70  # dummy score
            idea = Idea(idea_text=idea_text, analysis=analysis, viability_score=viability_score, user_id=user.id)
            db.session.add(idea)
            db.session.commit()
            user.free_analyses += 1
            db.session.commit()
            flash("Idea analyzed successfully!")
        except Exception as e:
            flash(f"Error analyzing idea: {str(e)}")
    ideas = Idea.query.filter_by(user_id=user.id).all()
    return render_template("index.html", ideas=ideas)

@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = User.query.get(session["user_id"])
    return render_template("profile.html", user=user)

if __name__ == "__main__":
    app.run(debug=True)







