from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255))
    location = db.Column(db.String(100), nullable=True)
    free_uses = db.Column(db.Integer, default=2)
    credits = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    google_id = db.Column(db.String(255), unique=True, nullable=True, index=True)

    # Relationship with ideas
    ideas = db.relationship("Idea", backref="user", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email}>"

    def has_credits(self):
        """Check if the user has credits or free uses available."""
        return self.credits > 0 or self.free_uses > 0

    def consume_credit(self):
        """Consume a credit or free use safely."""
        if self.credits > 0:
            self.credits -= 1
        elif self.free_uses > 0:
            self.free_uses -= 1
        db.session.commit()


class Idea(db.Model):
    __tablename__ = "idea"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    idea_text = db.Column(db.Text, nullable=False)
    analysis = db.Column(db.Text, nullable=True)
    score = db.Column(db.Integer, nullable=True)
    location = db.Column(db.String(100), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Idea {self.id} - User {self.user_id}>"



