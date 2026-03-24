import os
import re
import asyncio
import tempfile
import threading
import time
from dotenv import load_dotenv

load_dotenv()

VOICES = {
    "zh": "zh-CN-XiaoxiaoNeural",
    "pl": "pl-PL-ZofiaNeural",
    "en": "en-US-JennyNeural",
}


def _clean_text(text: str) -> str:
    """Strip brackets, extra punctuation, and whitespace that confuse TTS."""
    text = text.strip()
    # Remove content inside parentheses/brackets (e.g. tone numbers, IPA)
    text = re.sub(r"\(.*?\)|\[.*?\]", "", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def _save_audio(text: str, voice: str, path: str):
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(path)


def _generate_audio_bytes(text: str, language: str) -> bytes:
    text = _clean_text(text)
    if not text:
        raise ValueError("Empty text after cleaning")

    voice = VOICES.get(language, "zh-CN-XiaoxiaoNeural")
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        for attempt in range(3):
            try:
                asyncio.run(_save_audio(text, voice, tmp_path))
                break
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(1)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _upload_to_supabase(audio_bytes: bytes, storage_path: str) -> str:
    from supabase import create_client

    client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_KEY"),
    )
    try:
        client.storage.from_("audio").upload(
            storage_path,
            audio_bytes,
            {"content-type": "audio/mpeg", "upsert": "true"},
        )
    except Exception as e:
        print(f"Supabase upload error for {storage_path}: {e}")
    return client.storage.from_("audio").get_public_url(storage_path)


def _generate_card_audio(card_id: str, user_id: str, foreign_word: str, examples: list, language: str):
    """Returns (word_url, example_urls_list)."""
    word_audio = _generate_audio_bytes(foreign_word, language)
    word_url = _upload_to_supabase(word_audio, f"user_{user_id}/{card_id}_word.mp3")

    example_urls = []
    for i, ex in enumerate(examples):
        sentence = ex.get("sentence_foreign", "")
        if sentence:
            audio = _generate_audio_bytes(sentence, language)
            url = _upload_to_supabase(audio, f"user_{user_id}/{card_id}_ex{i}.mp3")
            example_urls.append(url)
        else:
            example_urls.append(None)

    return word_url, example_urls


def generate_audio_for_group_background(cards: list, user_id: str, language: str, db_update_fn):
    """Kick off background thread for bulk audio generation."""

    def _run():
        for card in cards:
            try:
                word_url, example_urls = _generate_card_audio(
                    str(card["id"]),
                    user_id,
                    card["foreign_word"],
                    card.get("examples") or [],
                    language,
                )
                db_update_fn(str(card["id"]), word_url, example_urls)
            except Exception as e:
                print(f"Audio generation failed for card {card['id']}: {e}")

    threading.Thread(target=_run, daemon=True).start()


DIALOGUE_VOICES = {
    "zh": {"A": "zh-CN-XiaoxiaoNeural", "B": "zh-CN-YunxiNeural"},
    "pl": {"A": "pl-PL-ZofiaNeural", "B": "pl-PL-MarekNeural"},
    "en": {"A": "en-US-JennyNeural", "B": "en-US-GuyNeural"},
}


def _generate_audio_bytes_with_voice(text: str, voice: str) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        for attempt in range(3):
            try:
                asyncio.run(_save_audio(text, voice, tmp_path))
                break
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(1)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def generate_dialogue_audio_background(dialogue_id: str, lines: list, language: str, db_update_fn):
    """Generate one audio file per dialogue line in a background thread."""

    def _run():
        voices = DIALOGUE_VOICES.get(language, DIALOGUE_VOICES["zh"])
        audio_urls = []
        for i, line in enumerate(lines):
            try:
                speaker = line.get("speaker", "A")
                voice = voices.get(speaker, voices["A"])
                text = _clean_text(line.get("text_foreign", ""))
                if not text:
                    audio_urls.append(None)
                    continue
                audio_bytes = _generate_audio_bytes_with_voice(text, voice)
                path = f"dialogues/{dialogue_id}/line_{i}.mp3"
                url = _upload_to_supabase(audio_bytes, path)
                audio_urls.append(url)
            except Exception as e:
                print(f"Dialogue audio failed for line {i}: {e}")
                audio_urls.append(None)
        db_update_fn(dialogue_id, audio_urls)

    threading.Thread(target=_run, daemon=True).start()
