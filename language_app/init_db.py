"""Run this script once to create the database tables in Supabase.

Also manually create a public 'audio' bucket in the Supabase Dashboard:
  Storage → New Bucket → Name: audio → Public: ON
"""

from services.db import get_connection

SQL = """
CREATE TABLE IF NOT EXISTS users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS groups (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT 'Group',
    language TEXT NOT NULL CHECK (language IN ('zh', 'pl')),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cards (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
    foreign_word TEXT NOT NULL,
    transcription TEXT,
    translation_ru TEXT,
    translation_en TEXT,
    examples JSONB DEFAULT '[]',
    audio_word_url TEXT,
    audio_examples_urls JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    group_id UUID REFERENCES groups(id) ON DELETE SET NULL,
    role TEXT CHECK (role IN ('user', 'assistant')),
    content TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
"""

if __name__ == "__main__":
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(SQL)
        conn.commit()
        print("Database tables created successfully.")
    finally:
        conn.close()
