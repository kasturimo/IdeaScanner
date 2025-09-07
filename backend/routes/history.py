from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User, Idea, db
from helpers import verify_play_purchase_placeholder

history_bp = Blueprint("history", __name__, url_prefix="/api")

@history_bp.route("/history", methods=["GET"])
@jwt_required()
def api_history():
    user_id = get_jwt_identity()
    ideas = Idea.query.filter_by(user_id=user_id).order_by(Idea.created_at.desc()).all()
    out = [{"id":i.id,"idea_text":i.idea_text,"analysis":i.analysis,"score":i.score,"location":i.location,"created_at":i.created_at.isoformat()} for i in ideas]
    return jsonify({"ok":True,"ideas":out})

@history_bp.route("/add_credits", methods=["POST"])
@jwt_required()
def api_add_credits():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.get_json() or {}
    package_name = data.get("packageName")
    product_id = data.get("productId")
    purchase_token = data.get("purchaseToken")
    credits = int(data.get("creditsAmount", 1))

    if not (package_name and product_id and purchase_token):
        return jsonify({"error":"packageName, productId and purchaseToken required"}), 400

    ok_verified = verify_play_purchase_placeholder(package_name, product_id, purchase_token)
    if not ok_verified:
        return jsonify({"error":"purchase_not_verified"}), 400

    user.credits += credits
    db.session.commit()
    return jsonify({"ok":True,"credits":user.credits})
