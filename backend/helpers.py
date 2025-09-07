import os
from werkzeug.security import generate_password_hash
from models import db, User

def get_user_by_email(email):
    return User.query.filter_by(email=email).first()

def create_user(email, password=None, location=None, google_id=None):
    u = User(email=email, location=location)
    if password:
        u.password_hash = generate_password_hash(password)
    if google_id:
        u.google_id = google_id
    db.session.add(u)
    db.session.commit()
    return u

def verify_play_purchase_placeholder(package_name, product_id, purchase_token):
    """
    PLACEHOLDER. Replace with real Google Play Developer API verification.
    For dev, enable ALLOW_FAKE_PURCHASES=1 in .env to bypass.
    """
    if os.environ.get("ALLOW_FAKE_PURCHASES") == "1":
        return True
    return False
