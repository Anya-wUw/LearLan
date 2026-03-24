# LearLan

A web-based language learning flashcard app for studying **Chinese (Mandarin)**, **Polish**, and **English** — designed for Russian speakers. AI-powered, free-tier only.

## Features

- **AI flashcard generation** — describe what you want to learn, get instant flashcards
- **Flip cards** — front shows the word + transcription/pinyin, back shows translations + example sentences
- **Audio pronunciation** — every word and example sentence is read aloud (TTS)
- **Dialogue mode** — generate a natural two-person conversation using any word, with audio for each line
- **Language tabs** — filter your cards and dialogues by language
- **Inline editing** — edit any card directly in the browser

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.9+, Flask 3 |
| Frontend | Bootstrap 5, Jinja2 |
| LLM | Google Gemini 2.5 Flash (free tier) |
| TTS | `edge-tts` (Microsoft Edge, free) |
| Database | Supabase (free tier, PostgreSQL) |
| Audio storage | Supabase Storage |

## Setup

### 1. Clone and create virtual environment

```bash
git clone <repo-url>
cd LearLan
python3 -m venv venv
source venv/bin/activate
pip install -r language_app/requirements.txt
```

### 2. Configure environment variables

Create `language_app/.env`:

```
FLASK_SECRET_KEY=your_secret_key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
GEMINI_API_KEY=your_gemini_api_key
OPENROUTER_API_KEY=your_openrouter_api_key  # optional fallback
```

### 3. Set up Supabase

Run the following SQL in your Supabase SQL Editor:

```sql
CREATE TABLE users (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  email TEXT UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE groups (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL DEFAULT 'Group',
  language TEXT NOT NULL CHECK (language IN ('zh', 'pl', 'en')),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE cards (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
  foreign_word TEXT NOT NULL,
  transcription TEXT,
  translation_ru TEXT,
  translation_en TEXT,
  examples JSONB,
  audio_word_url TEXT,
  audio_examples_urls TEXT[],
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE chat_history (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  group_id UUID REFERENCES groups(id) ON DELETE SET NULL,
  role TEXT CHECK (role IN ('user', 'assistant')),
  content TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE dialogues (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  card_id UUID REFERENCES cards(id) ON DELETE CASCADE,
  speaker_a_name TEXT,
  speaker_b_name TEXT,
  lines JSONB,
  audio_lines_urls TEXT[],
  created_at TIMESTAMPTZ DEFAULT now()
);
```

Create a Supabase Storage bucket named `audio` and add this RLS policy:

```sql
CREATE POLICY "Allow all on audio bucket" ON storage.objects
FOR ALL USING (bucket_id = 'audio') WITH CHECK (bucket_id = 'audio');
```

### 4. Run

```bash
source venv/bin/activate
cd language_app
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Languages

| Language | Flag | TTS Voice |
|---|---|---|
| Chinese (Mandarin) | 🇨🇳 | zh-CN-XiaoxiaoNeural |
| Polish | 🇵🇱 | pl-PL-ZofiaNeural |
| English | 🇬🇧 | en-US-JennyNeural |
