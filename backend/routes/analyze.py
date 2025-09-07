from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User, Idea, db
import openai
from helpers import verify_play_purchase_placeholder

analyze_bp = Blueprint("analyze", __name__, url_prefix="/api")

openai.api_key = os.environ.get("OPENAI_API_KEY")

@analyze_bp.route("/analyze", methods=["POST"])
@jwt_required()
def api_analyze():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error":"User not found"}), 404

    data = request.get_json() or {}
    idea_text = data.get("idea")
    location = data.get("location") or user.location or "global"
    if not idea_text:
        return jsonify({"error":"idea required"}), 400

    # Allowance check
    used_free = user.free_uses <= 0
    if user.free_uses > 0:
        user.free_uses -= 1
        db.session.commit()
    elif user.credits and user.credits > 0:
        user.credits -= 1
        db.session.commit()
    else:
        return jsonify({"error":"payment_required","message":"No free uses or credits left"}), 402

    # OpenAI call
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role":"system","content":"You are a startup idea evaluator."},
                {"role":"user","content":f"Analyze this idea for feasibility and potential impact in {location}:\n\n{idea_text}\n\nGive a viability score (0-100) and short reasoning."}
            ],
            max_tokens=300
        )
        analysis = resp.choices[0].message.content.strip()
        digits = "".join([c for c in analysis if c.isdigit()])
        score = int(digits[:3]) if digits else None
    except Exception as e:
        # revert consumption
        if user.free_uses < 2:
            user.free_uses += 1
        else:
            user.credits += 1
        db.session.commit()
        return jsonify({"error":"openai_error","details":str(e)}), 500

    idea = Idea(user_id=user.id, idea_text=idea_text, analysis=analysis, score=score, location=location)
    db.session.add(idea)
    db.session.commit()

    return jsonify({"ok":True,"analysis":analysis,"score":score,"free_uses":user.free_uses,"credits":user.credits})
