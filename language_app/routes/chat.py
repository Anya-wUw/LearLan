from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from routes.auth import login_required
from services.db import get_client
from services import llm, tts
from services.llm import RateLimitError

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
        result = db.table("groups").select("*").eq("id", group_id).eq("user_id", session["user_id"]).limit(1).execute()
        group = result.data[0] if result.data else None
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
            cards, warnings = llm.add_more_cards(user_prompt, language, existing_words, n)
        else:
            cards, warnings = llm.generate_flashcards(user_prompt, language, n)
        return jsonify({"cards": cards, "warnings": warnings})
    except RateLimitError as e:
        return jsonify({"error": str(e), "rate_limited": True}), 429
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/chat/autosave", methods=["POST"])
@login_required
def autosave():
    """Auto-save generated cards to DB immediately so they survive a page refresh."""
    data = request.get_json()
    user_id = session["user_id"]
    language = (data or {}).get("language", "zh")
    group_id = (data or {}).get("group_id") or None
    prompt = (data or {}).get("prompt", "").strip()
    cards_data = (data or {}).get("cards", [])

    if not cards_data:
        return jsonify({"error": "No cards to save"}), 400

    db = get_client()

    if not group_id:
        group_name = (prompt[:45] + "…") if len(prompt) > 45 else (prompt or "Draft")
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
            "local_index": card.get("local_index"),
        })

    tts.generate_audio_for_group_background(inserted_cards, user_id, language, _update_card_audio)

    return jsonify({"group_id": group_id, "cards": inserted_cards})


@chat_bp.route("/chat/save", methods=["POST"])
@login_required
def save():
    """Finalize save: rename group (if needed) and redirect. Cards already exist from autosave."""
    data = request.get_json()
    user_id = session["user_id"]
    group_id = (data or {}).get("group_id") or None
    group_name = (data or {}).get("group_name", "").strip() or "Group"
    language = (data or {}).get("language", "zh")
    cards_data = (data or {}).get("cards", [])

    if not group_id:
        # Fallback: full save if autosave never ran
        if not cards_data:
            return jsonify({"error": "No cards to save"}), 400
        db = get_client()
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

    db = get_client()

    # Rename group if a name was provided
    db.table("groups").update({"name": group_name}).eq("id", group_id).eq("user_id", user_id).execute()

    # Patch all cards with current values (in case user edited them in preview)
    for card in cards_data:
        card_id = card.get("card_id")
        if card_id:
            allowed = {"foreign_word", "transcription", "translation_ru", "translation_en", "examples"}
            updates = {k: card[k] for k in allowed if k in card}
            if updates:
                db.table("cards").update(updates).eq("id", card_id).execute()

    return jsonify({"redirect": url_for("groups.view_group", group_id=group_id)})
