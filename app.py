from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
import openai, os
from datetime import datetime
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

# OAuth (Google Login)
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params={'prompt': 'consent'},
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://www.googleapis.com/oauth2/v1/userinfo',
    client_kwargs={'scope': 'openid email profile'},
)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200))
    location = db.Column(db.String(100))
    is_verified = db.Column(db.Boolean, default=False)
    free_uses = db.Column(db.Integer, default=2)
    credits = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Idea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    idea_text = db.Column(db.String(500), nullable=False)
    analysis = db.Column(db.String(1000))
    location = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
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
        # Email verification can be added here if needed
        return redirect(url_for("login"))
    return render_template("register.html")

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

@app.route("/login/google")
def google_login():
    redirect_uri = url_for("google_authorize", _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/authorize/google")
def google_authorize():
    token = google.authorize_access_token()
    resp = google.get("userinfo")
    user_info = resp.json()
    email = user_info["email"]
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, is_verified=True)
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
        idea_text = request.form.get("idea")
        location = request.form.get("location") or user.location or "Other"

        # Check free uses or credits
        if user.free_uses <= 0 and user.credits <= 0:
            return jsonify({"error": "Payment required via Google Play"}), 402
        if user.free_uses > 0:
            user.free_uses -= 1
        else:
            user.credits -= 1

        # OpenAI analysis
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": f"Analyze this startup idea for feasibility in {location}: {idea_text}"}],
                max_tokens=200
            )
            analysis = response.choices[0].message['content'].strip()
            score = "".join([c for c in analysis if c.isdigit()])
            if score:
                score = int(score[:3])
            else:
                score = None
        except Exception as e:
            analysis = f"Error analyzing idea: {str(e)}"

        new_idea = Idea(user_id=user.id, idea_text=idea_text, analysis=analysis, location=location)
        db.session.add(new_idea)
        db.session.commit()

    ideas = Idea.query.filter_by(user_id=user.id).order_by(Idea.created_at.desc()).all()
    return render_template("dashboard.html", user=user, ideas=ideas, analysis=analysis, score=score)

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









