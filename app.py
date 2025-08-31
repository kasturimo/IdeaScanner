# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import openai
import os
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer

# Load environment variables locally
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# OpenAI API key
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///database.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Enable CORS
CORS(app, supports_credentials=True)

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get("EMAIL_USER")
app.config['MAIL_PASSWORD'] = os.environ.get("EMAIL_PASS")
mail = Mail(app)

# Serializer for email verification
s = URLSafeTimedSerializer(app.secret_key)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    country = db.Column(db.String(50))
    is_verified = db.Column(db.Boolean, default=False)

class Idea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    idea_text = db.Column(db.String(500), nullable=False)
    analysis = db.Column(db.String(1000))  # store OpenAI analysis result

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
        country = request.form.get("country")

        if User.query.filter_by(username=email).first():
            return jsonify({"error": "User already exists!"}), 400

        hashed_pw = generate_password_hash(password)
        new_user = User(username=email, password=hashed_pw, country=country)
        db.session.add(new_user)
        db.session.commit()

        # Send verification email
        token = s.dumps(email, salt='email-confirm')
        confirm_url = url_for('confirm_email', token=token, _external=True)
        msg = Message('Confirm Your Email', sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f'Click to confirm your account: {confirm_url}'
        mail.send(msg)

        return "Signup successful! Please check your email to confirm your account."
    return render_template("signup.html")

@app.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = s.loads(token, salt='email-confirm', max_age=3600)  # 1 hour expiry
        user = User.query.filter_by(username=email).first()
        if user:
            user.is_verified = True
            db.session.commit()
            return "Email confirmed! You can now log in."
    except:
        return "The confirmation link is invalid or expired."

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(username=email).first()
        if user and check_password_hash(user.password, password):
            if not user.is_verified:
                return "Please verify your email first."
            session["user_id"] = user.id
            return redirect(url_for("dashboard"))
        return jsonify({"error": "Invalid credentials!"}), 401
    return render_template("login.html")

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        idea_text = request.form.get("idea")
        try:
            response = openai.Completion.create(
                model="text-davinci-003",
                prompt=f"Analyze this idea for feasibility and potential impact:\n\n{idea_text}",
                max_tokens=150
            )
            analysis = response.choices[0].text.strip()
        except Exception as e:
            analysis = f"Error analyzing idea: {str(e)}"

        new_idea = Idea(user_id=session["user_id"], idea_text=idea_text, analysis=analysis)
        db.session.add(new_idea)
        db.session.commit()
        return redirect(url_for("dashboard"))

    current_user = User.query.get(session["user_id"])
    ideas = Idea.query.filter_by(user_id=current_user.id).all()
    return render_template("dashboard.html", ideas=ideas)

@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect(url_for("login"))
    current_user = User.query.get(session["user_id"])
    ideas = Idea.query.filter_by(user_id=current_user.id).all()
    return render_template("history.html", ideas=ideas)

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("index"))

# Run app locally
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

