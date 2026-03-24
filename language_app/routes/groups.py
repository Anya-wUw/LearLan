from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from routes.auth import login_required
from services.db import get_client

groups_bp = Blueprint("groups", __name__)


@groups_bp.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    db = get_client()

    result = db.table("groups").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    groups = result.data

    for group in groups:
        count_result = db.table("cards").select("*", count="exact").eq("group_id", group["id"]).execute()
        group["card_count"] = count_result.count or 0

    return render_template("dashboard.html", groups=groups)


@groups_bp.route("/groups/<group_id>")
@login_required
def view_group(group_id):
    user_id = session["user_id"]
    db = get_client()

    result = db.table("groups").select("*").eq("id", group_id).eq("user_id", user_id).maybe_single().execute()
    group = result.data
    if not group:
        return redirect(url_for("groups.dashboard"))

    cards_result = db.table("cards").select("*").eq("group_id", group_id).order("created_at").execute()
    cards = cards_result.data

    for card in cards:
        examples = card.get("examples") or []
        audio_urls = card.get("audio_examples_urls") or []
        card["examples_with_audio"] = [
            (ex, audio_urls[i] if i < len(audio_urls) else None)
            for i, ex in enumerate(examples)
        ]

    # Load which cards have dialogues
    if cards:
        card_ids = [str(c["id"]) for c in cards]
        dlg_result = db.table("dialogues").select("card_id").in_("card_id", card_ids).execute()
        cards_with_dialogues = {d["card_id"] for d in (dlg_result.data or [])}
    else:
        cards_with_dialogues = set()

    return render_template("group.html", group=group, cards=cards, cards_with_dialogues=cards_with_dialogues)


@groups_bp.route("/groups/<group_id>", methods=["PUT"])
@login_required
def rename_group(group_id):
    user_id = session["user_id"]
    data = request.get_json()
    new_name = (data or {}).get("name", "").strip()
    if not new_name:
        return jsonify({"error": "Name cannot be empty"}), 400

    db = get_client()
    db.table("groups").update({"name": new_name}).eq("id", group_id).eq("user_id", user_id).execute()
    return jsonify({"success": True})


@groups_bp.route("/groups/<group_id>", methods=["DELETE"])
@login_required
def delete_group(group_id):
    user_id = session["user_id"]
    db = get_client()
    db.table("groups").delete().eq("id", group_id).eq("user_id", user_id).execute()
    return jsonify({"success": True})
