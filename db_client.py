"""
db_client.py
-------------------------------------------------------------------
This is the ONLY file in the whole project that should know how to
connect to Supabase directly. Every other script asks this file for
a ready-to-use connection ("client") instead of connecting itself.

Why this matters: if we ever change database providers, or how we
authenticate to Supabase, we fix it here once -- nothing else in the
project needs to change.

Usage from any other script:
    from db_client import get_client
    supabase = get_client()
    result = supabase.table("sectors").select("*").execute()
-------------------------------------------------------------------
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Loads the SUPABASE_URL and SUPABASE_SECRET_KEY values from the .env
# file sitting next to this script. The .env file is never uploaded
# to GitHub (see .gitignore) -- this is how the secret key stays secret.
load_dotenv()

_client: Client | None = None


def get_client() -> Client:
    """Returns a ready-to-use Supabase connection, reusing the same
    one across the whole program instead of reconnecting every time."""
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SECRET_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_SECRET_KEY not found. "
                "Make sure a .env file exists next to this script with both values set."
            )
        _client = create_client(url, key)
    return _client
