import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.environ.get('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')  # Using service role key for admin operations

def get_supabase_client() -> Client:
    """Get a Supabase client instance."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Supabase URL and service role key must be set in environment variables")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Table names
VIDEOS_TABLE = 'videos'
CHANNELS_TABLE = 'channels' 