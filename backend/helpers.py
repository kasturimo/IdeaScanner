import os
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User
from google.oauth2 import service_account
from googleapiclient.discovery import build


# --- Google Play Config ---
PACKAGE_NAME = "com.ideascanner"
SERVICE_ACCOUNT_FILE = "google_play_service_account.json"  # must exist in backend root
SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]

service = None
try:
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build("androidpublisher", "v3", credentials=credentials)
except Exception as e:
    print("⚠️ Google Play API not initialized in helpers.py:", e)


# --- User helpers ---
def get_user_by_email(email):
    return User.query.filter_by(email=email).first()


def get_user_by_google_id(google_id):
    return User.query.filter_by(google_id=google_id).first()


def create_user(email, password=None, location=None, google_id=None):
    if email and get_user_by_email(email):
        raise ValueError("User with this email already exists")
    if google_id and get_user_by_google_id(google_id):
        raise ValueError("User with this Google account already exists")

    u = User(email=email, location=location)
    if password:
        u.password_hash = generate_password_hash(password)
    if google_id:
        u.google_id = google_id

    db.session.add(u)
    db.session.commit()
    return u


def verify_password(user, password):
    """Check hashed password"""
    return check_password_hash(user.password_hash, password)


# --- Purchase verification ---
def verify_play_purchase(package_name, product_id, purchase_token):
    """
    Real purchase verification with Google Play.
    If ALLOW_FAKE_PURCHASES=1 in .env, always succeeds.
    """
    if os.environ.get("ALLOW_FAKE_PURCHASES") == "1":
        return True

    if not service:
        raise RuntimeError("Google Play API not initialized")

    result = (
        service.purchases()
        .products()
        .get(packageName=package_name, productId=product_id, token=purchase_token)
        .execute()
    )

    return result.get("purchaseState") == 0

