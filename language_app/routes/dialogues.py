from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from routes.auth import login_required
from services.db import get_client
from services import llm, tts

dialogues_bp = Blueprint("dialogues", __name__)


def _update_dialogue_audio(dialogue_id: str, audio_urls: list):
    db = get_client()
    db.table("dialogues").update({"audio_lines_urls": audio_urls}).eq("id", dialogue_id).execute()


@dialogues_bp.route("/dialogues")
@login_required
def list_dialogues():
    user_id = session["user_id"]
    db = get_client()
    result = db.table("dialogues").select("*, cards(foreign_word, group_id, groups(language))").eq("user_id", user_id).order("created_at", desc=True).execute()
    dialogues = result.data or []
    return render_template("dialogues.html", dialogues=dialogues)


@dialogues_bp.route("/dialogues/<dialogue_id>")
@login_required
def view_dialogue(dialogue_id):
    user_id = session["user_id"]
    db = get_client()
    result = db.table("dialogues").select("*, cards(foreign_word, group_id, groups(language))").eq("id", dialogue_id).eq("user_id", user_id).limit(1).execute()
    dialogue = result.data[0] if result.data else None
    if not dialogue:
        return redirect(url_for("dialogues.list_dialogues"))
    return render_template("dialogue.html", dialogue=dialogue)


@dialogues_bp.route("/cards/<card_id>/dialogue", methods=["POST"])
@login_required
def generate_dialogue(card_id):
    user_id = session["user_id"]
    db = get_client()

    # Verify card belongs to user
    card_result = db.table("cards").select("*, groups(language, user_id)").eq("id", card_id).limit(1).execute()
    card = card_result.data[0] if card_result.data else None
    if not card or card["groups"]["user_id"] != user_id:
        return jsonify({"error": "Not found"}), 404

    language = card["groups"]["language"]

    # Check if dialogue already exists
    existing = db.table("dialogues").select("*").eq("card_id", card_id).limit(1).execute()
    if existing.data:
        return jsonify({"dialogue": existing.data[0]})

    # Generate dialogue text
    try:
        dialogue_data = llm.generate_dialogue(
            card["foreign_word"],
            card.get("translation_ru", ""),
            card.get("translation_en", ""),
            language,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Save to DB
    result = db.table("dialogues").insert({
        "card_id": card_id,
        "user_id": user_id,
        "speaker_a_name": dialogue_data.get("speaker_a_name", "A"),
        "speaker_b_name": dialogue_data.get("speaker_b_name", "B"),
        "lines": dialogue_data.get("lines", []),
        "audio_lines_urls": [],
    }).execute()
    dialogue = result.data[0]

    # Generate audio in background
    tts.generate_dialogue_audio_background(
        dialogue["id"],
        dialogue_data.get("lines", []),
        language,
        _update_dialogue_audio,
    )

    return jsonify({"dialogue": dialogue})


@dialogues_bp.route("/dialogues/<dialogue_id>", methods=["DELETE"])
@login_required
def delete_dialogue(dialogue_id):
    user_id = session["user_id"]
    db = get_client()
    db.table("dialogues").delete().eq("id", dialogue_id).eq("user_id", user_id).execute()
    return jsonify({"success": True})
