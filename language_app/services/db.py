import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()


def get_client():
    return create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_KEY"),
    )
