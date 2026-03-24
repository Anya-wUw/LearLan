from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from routes.auth import login_required
from services.db import get_client
from services import llm, tts

chat_bp = Blueprint("chat", __name__)


def _update_card_audio(card_id: str, word_url: str, example_urls: list):
    db = get_client()
    db.table("cards").update({
        "audio_word_url": word_url,
        "audio_examples_urls": example_urls,
    }).eq("id", card_id).execute()


@chat_bp.route("/chat")
@login_required
def chat():
    language = request.args.get("language")
    group_id = request.args.get("group_id")
    group = None

    if group_id:
        db = get_client()
        result = db.table("groups").select("*").eq("id", group_id).eq("user_id", session["user_id"]).maybe_single().execute()
        group = result.data
        if group:
            language = group["language"]

    if not language and not group:
        return redirect(url_for("groups.dashboard"))

    return render_template("chat.html", language=language, group=group)


@chat_bp.route("/chat/generate", methods=["POST"])
@login_required
def generate():
    data = request.get_json()
    user_prompt = (data or {}).get("prompt", "").strip()
    language = (data or {}).get("language", "zh")
    n = int((data or {}).get("n", 10))
    existing_words = (data or {}).get("existing_words", [])

    if not user_prompt:
        return jsonify({"error": "Prompt is required"}), 400

    try:
        if existing_words:
            cards = llm.add_more_cards(user_prompt, language, existing_words, n)
        else:
            cards = llm.generate_flashcards(user_prompt, language, n)
        return jsonify({"cards": cards})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/chat/save", methods=["POST"])
@login_required
def save():
    data = request.get_json()
    user_id = session["user_id"]
    language = (data or {}).get("language", "zh")
    group_id = (data or {}).get("group_id") or None
    group_name = (data or {}).get("group_name", "").strip() or "Group"
    cards_data = (data or {}).get("cards", [])

    if not cards_data:
        return jsonify({"error": "No cards to save"}), 400

    db = get_client()

    if not group_id:
        result = db.table("groups").insert({
            "user_id": user_id,
            "name": group_name,
            "language": language,
        }).execute()
        group_id = result.data[0]["id"]

    inserted_cards = []
    for card in cards_data:
        examples = card.get("examples") or []
        result = db.table("cards").insert({
            "group_id": group_id,
            "foreign_word": card.get("foreign_word", ""),
            "transcription": card.get("transcription", ""),
            "translation_ru": card.get("translation_ru", ""),
            "translation_en": card.get("translation_en", ""),
            "examples": examples,
        }).execute()
        row = result.data[0]
        inserted_cards.append({
            "id": row["id"],
            "foreign_word": row["foreign_word"],
            "examples": examples,
        })

    tts.generate_audio_for_group_background(inserted_cards, user_id, language, _update_card_audio)

    return jsonify({"redirect": url_for("groups.view_group", group_id=group_id)})
