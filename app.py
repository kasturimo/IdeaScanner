from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///database.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Enable CORS
CORS(app, supports_credentials=True)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(100))

class Idea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    idea_text = db.Column(db.String(500), nullable=False)
    analysis = db.Column(db.String(2000))
    location = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Create tables
with app.app_context():
    db.create_all()

# Routes
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
        new_user = User(email=email, password=hashed_pw, location=location)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            return redirect(url_for("dashboard"))
        return jsonify({"error": "Invalid credentials!"}), 401
    return render_template("login.html")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("No account found with that email.", "danger")
            return redirect(url_for("forgot_password"))

        # Simulated reset link (in production, send email!)
        reset_link = url_for("reset_password", user_id=user.id, _external=True)
        flash(f"Password reset link (simulate email): {reset_link}", "info")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")

@app.route("/reset-password/<int:user_id>", methods=["GET", "POST"])
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        new_password = request.form.get("password")
        user.password = generate_password_hash(new_password)
        db.session.commit()
        flash("Password has been reset. You can now login.", "success")
        return redirect(url_for("login"))
    return render_template("reset_password.html", user=user)

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    analysis, score = None, None
    if request.method == "POST":
        idea_text = request.form.get("idea")
        location = request.form.get("location")

        user = User.query.get(session["user_id"])
        if not location:
            location = user.location

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert startup analyst."},
                    {"role": "user", "content": f"Analyze this startup idea for feasibility and potential impact in {location}:\n\n{idea_text}\n\nGive a viability score (0–100) and short reasoning."}
                ],
                max_tokens=300
            )
            analysis = response.choices[0].message.content.strip()

            score_digits = "".join([c for c in analysis if c.isdigit()])
            if score_digits:
                score = int(score_digits[:3]) if len(score_digits) >= 2 else int(score_digits)
            else:
                score = None

        except Exception as e:
            analysis = f"Error analyzing idea: {str(e)}"

        new_idea = Idea(user_id=session["user_id"], idea_text=idea_text, analysis=analysis, location=location)
        db.session.add(new_idea)
        db.session.commit()

    return render_template("dashboard.html", analysis=analysis, score=score)

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





