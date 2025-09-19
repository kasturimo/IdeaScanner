import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)
CORS(app)

# Google Play config
PACKAGE_NAME = "com.ideascanner"  # Replace with your actual package name
SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]

# Load credentials from environment variable (Render-friendly)
try:
    service_account_info = json.loads(os.environ["GOOGLE_PLAY_CREDENTIALS"])
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    service = build("androidpublisher", "v3", credentials=credentials)
except Exception as e:
    service = None
    print("⚠️ Google Play API not initialized:", e)


@app.route("/")
def home():
    return jsonify({"message": "IdeaScanner backend is running"})


@app.route("/verify_purchase", methods=["POST"])
def verify_purchase():
    """
    Verifies a Google Play in-app purchase or subscription with the purchaseToken.
    Request JSON:
    {
        "purchase_token": "...",
        "product_id": "...",
        "type": "product" | "subscription"
    }
    """
    if not service:
        return jsonify({"error": "Google Play API not initialized"}), 500

    data = request.json
    purchase_token = data.get("purchase_token")
    product_id = data.get("product_id")
    purchase_type = data.get("type", "product")  # default = product

    if not purchase_token or not product_id:
        return jsonify({"error": "Missing purchase_token or product_id"}), 400

    try:
        if purchase_type == "subscription":
            request_obj = (
                service.purchases()
                .subscriptions()
                .get(
                    packageName=PACKAGE_NAME,
                    subscriptionId=product_id,
                    token=purchase_token,
                )
            )
        else:  # default to product
            request_obj = (
                service.purchases()
                .products()
                .get(
                    packageName=PACKAGE_NAME,
                    productId=product_id,
                    token=purchase_token,
                )
            )

        result = request_obj.execute()

        # Extract useful fields only
        purchase_data = {
            "purchaseState": result.get("purchaseState"),  # 0 = purchased
            "consumptionState": result.get("consumptionState"),
            "orderId": result.get("orderId"),
            "purchaseTimeMillis": result.get("purchaseTimeMillis"),
            "expiryTimeMillis": result.get("expiryTimeMillis"),  # only for subs
            "acknowledgementState": result.get("acknowledgementState"),
        }

        if purchase_data.get("purchaseState") == 0:
            return jsonify(
                {"status": "success", "message": "Purchase verified", "data": purchase_data}
            )
        else:
            return jsonify(
                {"status": "failed", "message": "Purchase not valid", "data": purchase_data}
            )

    except Exception as e:
        print("Google Play verification error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)














