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
            '"sentence_ru": "<Russian translation>"}}'
        )
    else:
        examples_format = (
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


def _call_gemini(prompt: str) -> list:
    from google import genai

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    for model in ("gemini-2.5-flash", "gemini-2.0-flash"):
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            return _parse_response(response.text)
        except Exception as e:
            print(f"Gemini model {model} failed ({e}), trying next…")
    raise RuntimeError("All Gemini models failed")


def _call_openrouter(prompt: str) -> list:
    from openai import OpenAI

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )
    response = client.chat.completions.create(
        model="meta-llama/llama-3.3-70b-instruct:free",
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_response(response.choices[0].message.content)


def generate_flashcards(user_prompt: str, language: str, n: int = 10) -> list:
    n = min(max(n, 1), 30)
    prompt = _build_prompt(user_prompt, language, n)
    try:
        return _call_gemini(prompt)
    except Exception as e:
        print(f"Gemini failed ({e}), falling back to OpenRouter")
        return _call_openrouter(prompt)


def add_more_cards(user_prompt: str, language: str, existing_words: list, n: int = 10) -> list:
    n = min(max(n, 1), 30)
    prompt = _build_prompt(user_prompt, language, n, existing_words)
    try:
        return _call_gemini(prompt)
    except Exception as e:
        print(f"Gemini failed ({e}), falling back to OpenRouter")
        return _call_openrouter(prompt)


def generate_dialogue(foreign_word: str, translation_ru: str, translation_en: str, language: str) -> dict:
    """Generate a short natural dialogue using the given word."""
    lang_name = LANGUAGE_NAMES.get(language, language)
    pinyin_note = ""
    if language == "zh":
        pinyin_note = '\n      "text_pinyin": "<Pinyin with tone marks for this line>",'

    prompt = f"""Generate a short, natural dialogue (6–8 lines) between two people in {lang_name}.
The dialogue must naturally use or reference the word/phrase: "{foreign_word}" ({translation_ru}).
Make it feel like a real casual conversation between native speakers — lively, not textbook-style.
Assign random realistic first names to the two speakers (consistent throughout).

Return ONLY a valid JSON object, no markdown:
{{
  "speaker_a_name": "...",
  "speaker_b_name": "...",
  "lines": [
    {{
      "speaker": "A",
      "text_foreign": "...",{pinyin_note}
      "text_ru": "..."
    }}
  ]
}}"""

    try:
        from google import genai
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        for model in ("gemini-2.5-flash", "gemini-2.0-flash"):
            try:
                response = client.models.generate_content(model=model, contents=prompt)
                text = response.text.strip()
                text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
                text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
                return json.loads(text.strip())
            except Exception as e:
                print(f"Gemini {model} dialogue failed: {e}")
    except Exception as e:
        print(f"Gemini dialogue failed: {e}")

    # OpenRouter fallback
    from openai import OpenAI
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_API_KEY"))
    response = client.chat.completions.create(
        model="meta-llama/llama-3.3-70b-instruct:free",
        messages=[{"role": "user", "content": prompt}]
    )
    text = response.choices[0].message.content.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    return json.loads(text.strip())
