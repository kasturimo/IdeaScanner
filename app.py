import os
import smtplib
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Secret key & DB setup
app.secret_key = os.environ.get("SECRET_KEY", "fallback_secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///users.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Email credentials
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")

# ---------------- MODELS ---------------- #
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(100), nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(100), nullable=True)

class IdeaHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    idea = db.Column(db.Text, nullable=False)
    analysis = db.Column(db.Text, nullable=False)
    score = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(100), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

# ---------------- EMAIL HELPER ---------------- #
def send_verification_email(user_email, token):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_USER
        msg["To"] = user_email
        msg["Subject"] = "Verify your IdeaScanner account"

        verify_url = f"{request.url_root}verify/{token}"
        body = f"Hi,\n\nPlease verify your email by clicking the link below:\n{verify_url}\n\nThanks,\nIdeaScanner Team"
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, user_email, msg.as_string())
    except Exception as e:
        print("Error sending email:", e)

# ---------------- ROUTES ---------------- #
@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        location = request.form.get("location")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already exists. Please log in.", "danger")
            return redirect(url_for("login"))

        hashed_pw = generate_password_hash(password, method="sha256")
        token = secrets.token_urlsafe(16)

        new_user = User(email=email, password=hashed_pw, location=location,
                        is_verified=False, verification_token=token)
        db.session.add(new_user)
        db.session.commit()

        send_verification_email(email, token)
        flash("Signup successful! Please check your email to verify your account.", "info")
        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/verify/<token>")
def verify(token):
    user = User.query.filter_by(verification_token=token).first()
    if user:
        user.is_verified = True
        user.verification_token = None
        db.session.commit()
        flash("Email verified! You can now log in.", "success")
        return redirect(url_for("login"))
    else:
        flash("Invalid or expired verification link.", "danger")
        return redirect(url_for("signup"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            if not user.is_verified:
                flash("Please verify your email before logging in.", "warning")
                return redirect(url_for("login"))

            session["user_id"] = user.id
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")

    return render_template("login.html")

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    analysis, score = None, None

    if request.method == "POST":
        idea = request.form["idea"]
        location = request.form.get("location")

        # TODO: Replace this with OpenAI analysis
        analysis = f"Your idea '{idea}' seems promising in {location or user.location or 'your region'}."
        score = 75  # Dummy score

        new_history = IdeaHistory(idea=idea, analysis=analysis, score=score,
                                  location=location or user.location, user_id=user.id)
        db.session.add(new_history)
        db.session.commit()

    return render_template("dashboard.html", analysis=analysis, score=score)

@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    history_items = IdeaHistory.query.filter_by(user_id=user_id).all()
    return render_template("history.html", history=history_items)

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))

# ---------------- RUN ---------------- #
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)


