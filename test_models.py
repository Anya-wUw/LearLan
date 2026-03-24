#!/usr/bin/env python3
"""Quick test: check which Gemini and OpenRouter models respond successfully."""

import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "language_app"))

from dotenv import load_dotenv
load_dotenv("language_app/.env")

PROMPT = 'Return ONLY valid JSON: [{"word":"hello","ok":true}]'

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

GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def tag(ok, label):
    if ok is True:   return f"{GREEN}✓ OK{RESET}     {label}"
    if ok == "rate": return f"{YELLOW}⚡ RATE{RESET}   {label}"
    return               f"{RED}✗ FAIL{RESET}   {label}"

def is_rate(err):
    msg = str(err).lower()
    return any(k in msg for k in ("429", "rate limit", "rate-limit", "quota", "temporarily", "too many"))

# ── Gemini ────────────────────────────────────────────────────────────────────
print(f"\n{BOLD}=== Gemini models ==={RESET}")
gemini_key = os.getenv("GEMINI_API_KEY")
if not gemini_key:
    print(f"{RED}GEMINI_API_KEY not set — skipping{RESET}")
else:
    try:
        from google import genai
        gclient = genai.Client(api_key=gemini_key)
        for model in GEMINI_MODELS:
            t0 = time.time()
            try:
                r = gclient.models.generate_content(model=model, contents=PROMPT)
                elapsed = time.time() - t0
                snippet = (r.text or "")[:60].replace("\n", " ")
                print(f"  {tag(True, model)}  ({elapsed:.1f}s)  → {snippet}")
            except Exception as e:
                elapsed = time.time() - t0
                status = "rate" if is_rate(e) else False
                print(f"  {tag(status, model)}  ({elapsed:.1f}s)  → {str(e)[:80]}")
    except ImportError:
        print(f"{RED}google-genai not installed{RESET}")

# ── OpenRouter ────────────────────────────────────────────────────────────────
print(f"\n{BOLD}=== OpenRouter free models ==={RESET}")
or_key = os.getenv("OPENROUTER_API_KEY")
if not or_key:
    print(f"{YELLOW}OPENROUTER_API_KEY not set — skipping{RESET}")
else:
    try:
        from openai import OpenAI
        orclient = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=or_key)
        for model in OPENROUTER_MODELS:
            t0 = time.time()
            try:
                r = orclient.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": PROMPT}],
                    timeout=30,
                )
                elapsed = time.time() - t0
                snippet = (r.choices[0].message.content or "")[:60].replace("\n", " ")
                print(f"  {tag(True, model)}  ({elapsed:.1f}s)  → {snippet}")
            except Exception as e:
                elapsed = time.time() - t0
                status = "rate" if is_rate(e) else False
                print(f"  {tag(status, model)}  ({elapsed:.1f}s)  → {str(e)[:80]}")
    except ImportError:
        print(f"{RED}openai not installed{RESET}")

print()
