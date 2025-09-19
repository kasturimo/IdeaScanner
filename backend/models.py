from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(255))
    location = db.Column(db.String(100), nullable=True)
    free_uses = db.Column(db.Integer, default=2)
    credits = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    google_id = db.Column(db.String(255), unique=True, index=True, nullable=True)

    # Relationships
    ideas = db.relationship("Idea", backref="user", lazy=True)
    purchases = db.relationship("Purchase", backref="user", lazy=True)


class Idea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    idea_text = db.Column(db.Text, nullable=False)
    analysis = db.Column(db.Text, nullable=True)
    score = db.Column(db.Integer, nullable=True)
    location = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product_id = db.Column(db.String(100), nullable=False)
    purchase_token = db.Column(db.String(500), unique=True, nullable=False)
    status = db.Column(db.String(50), default="pending")  # pending/success/failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


