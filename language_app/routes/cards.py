from flask import Blueprint, request, jsonify, session
from routes.auth import login_required
from services.db import get_client

cards_bp = Blueprint("cards", __name__)


@cards_bp.route("/cards/<card_id>", methods=["PATCH"])
@login_required
def update_card(card_id):
    user_id = session["user_id"]
    data = request.get_json() or {}

    db = get_client()
    # Verify card belongs to user via group ownership
    card_result = db.table("cards").select("group_id").eq("id", card_id).maybe_single().execute()
    card = card_result.data
    if not card:
        return jsonify({"error": "Not found"}), 404

    group_result = db.table("groups").select("id").eq("id", card["group_id"]).eq("user_id", user_id).maybe_single().execute()
    if not group_result.data:
        return jsonify({"error": "Not found"}), 404

    allowed = {"foreign_word", "transcription", "translation_ru", "translation_en", "examples"}
    updates = {k: v for k, v in data.items() if k in allowed}

    if updates:
        db.table("cards").update(updates).eq("id", card_id).execute()

    return jsonify({"success": True})


@cards_bp.route("/cards/<card_id>", methods=["DELETE"])
@login_required
def delete_card(card_id):
    user_id = session["user_id"]
    db = get_client()

    card_result = db.table("cards").select("group_id").eq("id", card_id).maybe_single().execute()
    card = card_result.data
    if card:
        group_result = db.table("groups").select("id").eq("id", card["group_id"]).eq("user_id", user_id).maybe_single().execute()
        if group_result.data:
            db.table("cards").delete().eq("id", card_id).execute()

    return jsonify({"success": True})
