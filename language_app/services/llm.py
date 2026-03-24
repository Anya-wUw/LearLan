import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

LANGUAGE_NAMES = {
    "zh": "Chinese (Mandarin)",
    "pl": "Polish",
    "en": "English",
}

TRANSCRIPTION_NOTES = {
    "zh": (
        "Include both Pinyin with tone marks (e.g. nǐ hǎo) "
        "AND tone numbers (e.g. ni3 hao3) separated by ' / '"
    ),
    "pl": (
        "Include simplified phonetic transcription that a Russian speaker can read "
        "(e.g. [честь] style), not strict IPA"
    ),
    "en": (
        "Include IPA transcription (e.g. /ˈwɔːtər/) "
        "AND a simplified phonetic reading a Russian speaker can use (e.g. [уо́тэр])"
    ),
}

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

OPENROUTER_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "google/gemma-3-27b-it:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "google/gemma-3-12b-it:free",
]

# Fallback names per language if the model returns identical speaker names
_FALLBACK_NAMES = {
    "zh": ["明明", "小华", "芳芳", "大伟", "小丽", "小强", "阿静", "小磊"],
    "pl": ["Anna", "Piotr", "Kasia", "Marek", "Agnieszka", "Tomek", "Ola", "Bartek"],
    "en": ["Alex", "Sam", "Jordan", "Morgan", "Taylor", "Casey", "Riley", "Jamie"],
}


class RateLimitError(Exception):
    pass


def _is_rate_limit(err: Exception) -> bool:
    msg = str(err).lower()
    return any(k in msg for k in ("429", "rate limit", "rate-limit", "quota", "temporarily", "too many", "resource_exhausted"))


def _short_model(model: str) -> str:
    """Return a short display name for a model string."""
    return model.split("/")[-1] if "/" in model else model


def _build_prompt(user_prompt: str, language: str, n: int, existing_words=None) -> str:
    lang_name = LANGUAGE_NAMES.get(language, language)
    transcription_note = TRANSCRIPTION_NOTES.get(language, "")
    exclude_note = ""
    if existing_words:
        exclude_note = f"\nDo NOT include these already-existing words: {', '.join(existing_words)}\n"

    if language == "zh":
        examples_format = (
            '      {{"sentence_foreign": "<example sentence>", '
            '"sentence_pinyin": "<Pinyin with tone marks>", '
            '"sentence_ru": "<Russian translation>"}},\n'
            '      {{"sentence_foreign": "<example sentence>", '
            '"sentence_pinyin": "<Pinyin with tone marks>", '
            '"sentence_ru": "<Russian translation>"}},\n'
            '      {{"sentence_foreign": "<example sentence>", '
            '"sentence_pinyin": "<Pinyin with tone marks>", '
            '"sentence_ru": "<Russian translation>"}}'
        )
    else:
        examples_format = (
            '      {{"sentence_foreign": "<example sentence>", "sentence_ru": "<Russian translation>"}},\n'
            '      {{"sentence_foreign": "<example sentence>", "sentence_ru": "<Russian translation>"}},\n'
            '      {{"sentence_foreign": "<example sentence>", "sentence_ru": "<Russian translation>"}}'
        )

    return f"""You are a language learning assistant. Generate exactly {n} flashcards for learning {lang_name} for a Russian-speaking user.

User's request: "{user_prompt}"
{exclude_note}
Transcription note: {transcription_note}

Return a valid JSON array (no markdown fences, no explanation, just the raw JSON array):
[
  {{
    "foreign_word": "<word in target language>",
    "transcription": "<transcription per note above>",
    "translation_ru": "<Russian translation>",
    "translation_en": "<English translation>",
    "examples": [
{examples_format}
    ]
  }}
]"""


def _parse_response(text: str) -> list:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    return json.loads(text.strip())


def _parse_obj(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    return json.loads(text.strip())


def _call_gemini(prompt: str, warnings: list) -> list:
    from google import genai
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    last_err = None
    for model in GEMINI_MODELS:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            if warnings:
                # already notified about some failures — note the successful model
                warnings.append(f"✓ Switched to {_short_model(model)} successfully.")
            return _parse_response(response.text)
        except Exception as e:
            last_err = e
            short = _short_model(model)
            if _is_rate_limit(e):
                msg = f"⚡ {short} rate-limited — trying next model…"
            else:
                msg = f"✗ {short} failed — trying next model…"
            print(f"[llm] {msg} | {e}")
            warnings.append(msg)
    raise last_err


def _call_openrouter(prompt: str, warnings: list) -> list:
    from openai import OpenAI
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    last_err = None
    for model in OPENROUTER_MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            warnings.append(f"✓ Switched to {_short_model(model)} successfully.")
            return _parse_response(response.choices[0].message.content)
        except Exception as e:
            last_err = e
            short = _short_model(model)
            if _is_rate_limit(e):
                msg = f"⚡ {short} rate-limited — trying next model…"
            else:
                msg = f"✗ {short} failed — trying next model…"
            print(f"[llm] {msg} | {e}")
            warnings.append(msg)
    raise last_err


def _call_gemini_obj(prompt: str, warnings: list) -> dict:
    from google import genai
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    last_err = None
    for model in GEMINI_MODELS:
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            if warnings:
                warnings.append(f"✓ Switched to {_short_model(model)} successfully.")
            return _parse_obj(response.text)
        except Exception as e:
            last_err = e
            short = _short_model(model)
            if _is_rate_limit(e):
                msg = f"⚡ {short} rate-limited — trying next model…"
            else:
                msg = f"✗ {short} failed — trying next model…"
            print(f"[llm] {msg} | {e}")
            warnings.append(msg)
    raise last_err


def _call_openrouter_obj(prompt: str, warnings: list) -> dict:
    from openai import OpenAI
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    last_err = None
    for model in OPENROUTER_MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            warnings.append(f"✓ Switched to {_short_model(model)} successfully.")
            return _parse_obj(response.choices[0].message.content)
        except Exception as e:
            last_err = e
            short = _short_model(model)
            if _is_rate_limit(e):
                msg = f"⚡ {short} rate-limited — trying next model…"
            else:
                msg = f"✗ {short} failed — trying next model…"
            print(f"[llm] {msg} | {e}")
            warnings.append(msg)
    raise last_err


def _generate_with_fallback(prompt: str, warnings: list) -> list:
    gemini_err = None
    try:
        return _call_gemini(prompt, warnings)
    except Exception as e:
        gemini_err = e
        warnings.append("⚠ All Gemini models failed — switching to OpenRouter…")
        print(f"[llm] All Gemini models failed: {e}")

    try:
        return _call_openrouter(prompt, warnings)
    except Exception as e:
        if _is_rate_limit(e) or _is_rate_limit(gemini_err):
            raise RateLimitError("All models are currently rate-limited. Please try again in a moment.")
        raise RuntimeError(f"All models failed. Gemini: {gemini_err}. OpenRouter: {e}")


def _generate_obj_with_fallback(prompt: str, warnings: list) -> dict:
    gemini_err = None
    try:
        return _call_gemini_obj(prompt, warnings)
    except Exception as e:
        gemini_err = e
        warnings.append("⚠ All Gemini models failed — switching to OpenRouter…")
        print(f"[llm] All Gemini models failed: {e}")

    try:
        return _call_openrouter_obj(prompt, warnings)
    except Exception as e:
        if _is_rate_limit(e) or _is_rate_limit(gemini_err):
            raise RateLimitError("All models are currently rate-limited. Please try again in a moment.")
        raise RuntimeError(f"All models failed. Gemini: {gemini_err}. OpenRouter: {e}")


def _normalize_dialogue(dialogue_data: dict, language: str) -> dict:
    """
    Fix two common model errors:
    1. speaker field contains the actual name instead of 'A'/'B'
       (e.g. OpenRouter returns {"speaker": "Ben", ...} instead of {"speaker": "B", ...})
    2. Both speakers have the same name, or only one speaker appears in lines.
    """
    fallbacks = _FALLBACK_NAMES.get(language, _FALLBACK_NAMES["en"])

    # ── Fix names ─────────────────────────────────────────────────────────────
    a_name = (dialogue_data.get("speaker_a_name") or "").strip()
    b_name = (dialogue_data.get("speaker_b_name") or "").strip()

    if not a_name:
        a_name = fallbacks[0]
        dialogue_data["speaker_a_name"] = a_name
    if not b_name or b_name.lower() == a_name.lower():
        for name in fallbacks:
            if name.lower() != a_name.lower():
                b_name = name
                dialogue_data["speaker_b_name"] = b_name
                break

    # ── Normalize speaker field in lines ──────────────────────────────────────
    lines = dialogue_data.get("lines") or []
    a_lower = a_name.lower()
    b_lower = b_name.lower()

    for line in lines:
        raw = (line.get("speaker") or "").strip()
        raw_lower = raw.lower()
        if raw_lower in ("a", a_lower):
            line["speaker"] = "A"
        elif raw_lower in ("b", b_lower):
            line["speaker"] = "B"
        # else: unknown value — handled below

    # ── Ensure both A and B are present ───────────────────────────────────────
    present = {line.get("speaker") for line in lines}
    if "A" not in present or "B" not in present:
        # Force strict alternation: even index → A, odd → B
        for i, line in enumerate(lines):
            line["speaker"] = "A" if i % 2 == 0 else "B"

    return dialogue_data


# ── public API ─────────────────────────────────────────────────────────────────

def generate_flashcards(user_prompt: str, language: str, n: int = 10) -> tuple:
    """Returns (cards_list, warnings_list)."""
    n = min(max(n, 1), 30)
    warnings = []
    prompt = _build_prompt(user_prompt, language, n)
    cards = _generate_with_fallback(prompt, warnings)
    return cards, warnings


def add_more_cards(user_prompt: str, language: str, existing_words: list, n: int = 10) -> tuple:
    """Returns (cards_list, warnings_list)."""
    n = min(max(n, 1), 30)
    warnings = []
    prompt = _build_prompt(user_prompt, language, n, existing_words)
    cards = _generate_with_fallback(prompt, warnings)
    return cards, warnings


def generate_dialogue(foreign_word: str, translation_ru: str, translation_en: str, language: str) -> tuple:
    """Returns (dialogue_dict, warnings_list)."""
    lang_name = LANGUAGE_NAMES.get(language, language)
    pinyin_note = ""
    if language == "zh":
        pinyin_note = '\n      "text_pinyin": "<Pinyin with tone marks for this line>",'

    prompt = f"""Generate a natural, context-rich dialogue (10–14 lines) between TWO DIFFERENT people in {lang_name}.

IMPORTANT: speaker_a_name and speaker_b_name MUST be different names.

The dialogue must:
- Naturally use or reference the word/phrase: "{foreign_word}" ({translation_ru} / {translation_en})
- Be set in a specific realistic situation (e.g. café, workplace, phone call, shopping) — establish context in the first lines
- Show HOW and WHEN this word is used in real life (use it more than once if natural)
- Feel like a real native conversation — lively, with emotion, reactions, follow-up questions
- Assign two distinct realistic first names (one for A, a completely different one for B)

Return ONLY a valid JSON object, no markdown:
{{
  "speaker_a_name": "<first name>",
  "speaker_b_name": "<different first name>",
  "lines": [
    {{
      "speaker": "A",
      "text_foreign": "...",{pinyin_note}
      "text_ru": "..."
    }}
  ]
}}"""

    warnings = []
    dialogue_data = _generate_obj_with_fallback(prompt, warnings)
    dialogue_data = _normalize_dialogue(dialogue_data, language)
    return dialogue_data, warnings
