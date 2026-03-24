from flask import Blueprint, request, jsonify, session
from routes.auth import login_required
from services.db import get_client
from services import tts

cards_bp = Blueprint("cards", __name__)


@cards_bp.route("/cards/<card_id>", methods=["PATCH"])
@login_required
def update_card(card_id):
    user_id = session["user_id"]
    data = request.get_json() or {}

    db = get_client()
    card_result = db.table("cards").select("group_id").eq("id", card_id).limit(1).execute()
    card = card_result.data[0] if card_result.data else None
    if not card:
        return jsonify({"error": "Not found"}), 404

    group_result = db.table("groups").select("id").eq("id", card["group_id"]).eq("user_id", user_id).limit(1).execute()
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

    card_result = db.table("cards").select("group_id").eq("id", card_id).limit(1).execute()
    card = card_result.data[0] if card_result.data else None
    if card:
        group_result = db.table("groups").select("id").eq("id", card["group_id"]).eq("user_id", user_id).limit(1).execute()
        if group_result.data:
            db.table("cards").delete().eq("id", card_id).execute()

    return jsonify({"success": True})


@cards_bp.route("/cards/<card_id>/regenerate-audio", methods=["POST"])
@login_required
def regenerate_audio(card_id):
    user_id = session["user_id"]
    db = get_client()

    card_result = db.table("cards").select("*, groups(language, user_id)").eq("id", card_id).limit(1).execute()
    card = card_result.data[0] if card_result.data else None
    if not card or card["groups"]["user_id"] != user_id:
        return jsonify({"error": "Not found"}), 404

    language = card["groups"]["language"]

    def _update(cid, word_url, example_urls):
        get_client().table("cards").update({
            "audio_word_url": word_url,
            "audio_examples_urls": example_urls,
        }).eq("id", cid).execute()

    tts.generate_audio_for_group_background(
        [{"id": card_id, "foreign_word": card["foreign_word"], "examples": card.get("examples") or []}],
        user_id,
        language,
        _update,
    )

    return jsonify({"success": True})
