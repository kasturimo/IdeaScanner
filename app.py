from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import openai
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

openai.api_key = os.environ.get("OPENAI_API_KEY")

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///database.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

CORS(app, supports_credentials=True)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Idea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    idea_text = db.Column(db.String(500), nullable=False)
    analysis = db.Column(db.String(1000))

with app.app_context():
    db.create_all()

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        if User.query.filter_by(username=email).first():
            error = "User already exists!"
        else:
            hashed_pw = generate_password_hash(password)
            new_user = User(username=email, password=hashed_pw)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for("login"))
    return render_template("signup.html", error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(username=email).first()
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid credentials!"
    return render_template("login.html", error=error)

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    analysis = None
    score = None

    if request.method == "POST":
        idea_text = request.form.get("idea")
        if idea_text and idea_text.strip() != "":
            try:
                response = openai.Completion.create(
                    model="text-davinci-003",
                    prompt=f"Analyze this idea for feasibility and potential impact:\n\n{idea_text}",
                    max_tokens=150
                )
                analysis = response.choices[0].text.strip()
                score = min(100, max(0, len(analysis) % 101))
            except Exception as e:
                analysis = "Analysis failed."
                score = 0

            new_idea = Idea(user_id=session["user_id"], idea_text=idea_text, analysis=analysis)
            db.session.add(new_idea)
            db.session.commit()

    ideas = Idea.query.filter_by(user_id=session["user_id"]).all()
    return render_template("dashboard.html", ideas=ideas, analysis=analysis, score=score)

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
