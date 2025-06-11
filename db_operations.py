from datetime import datetime
from typing import List, Dict, Any, Optional
from supabase_config import get_supabase_client, CHANNELS_TABLE, VIDEOS_TABLE

def upsert_channel(channel_data: Dict[str, Any]) -> None:
    """Upsert a channel record into the 'channels' table."""
    supabase = get_supabase_client()
    channel_record = {
        'slug': channel_data['slug'],
        'name': channel_data['name'],
        'youtube_id': channel_data.get('youtubeId'),
        # 'created_at' is handled by the database default
    }
    supabase.table(CHANNELS_TABLE).upsert(channel_record).execute()

def insert_new_media_items(channel_slug: str, videos: List[Dict[str, Any]]) -> None:
    """Insert only new media_items for a channel, skipping existing ones (by id)."""
    supabase = get_supabase_client()
    # Get all existing ids for this channel
    existing = supabase.table(VIDEOS_TABLE).select('id').eq('channel_slug', channel_slug).execute()
    existing_ids = {item['id'] for item in (existing.data or [])}

    new_records = []
    for video in videos:
        if video['id'] in existing_ids:
            continue  # Skip existing
        # Prepare media_item record
        record = {
            'id': video['id'],
            'title': video['title'],
            'date': video['date'],
            'content_type': video.get('contentType', 'podcast'),
            'duration': video.get('duration'),
            'description': video.get('description'),
            'youtube_id': video['id'],
            'image': video.get('thumbnails', {}).get('high') or video.get('thumbnails', {}).get('default'),
            'channel_slug': channel_slug,
            'youtube_url': f"https://www.youtube.com/watch?v={video['id']}",
            # 'apple_podcasts_url': ... # Add if available in your data
            # 'created_at' is handled by the database default
        }
        new_records.append(record)
    if new_records:
        supabase.table(VIDEOS_TABLE).insert(new_records).execute()

def get_channel_media_items(channel_slug: str) -> List[Dict[str, Any]]:
    """Get all media_items for a channel."""
    supabase = get_supabase_client()
    response = supabase.table(VIDEOS_TABLE).select('*').eq('channel_slug', channel_slug).execute()
    return response.data

def get_all_channels() -> List[Dict[str, Any]]:
    """Get all channels."""
    supabase = get_supabase_client()
    response = supabase.table(CHANNELS_TABLE).select('*').execute()
    return response.data

def get_latest_media_item_date(channel_slug: str) -> Optional[str]:
    """Get the latest (most recent) date for a channel's media_items. Returns ISO date string or None."""
    supabase = get_supabase_client()
    response = supabase.table(VIDEOS_TABLE)\
        .select('date')\
        .eq('channel_slug', channel_slug)\
        .order('date', desc=True)\
        .limit(1)\
        .execute()
    if response.data and response.data[0].get('date'):
        return response.data[0]['date']
    return None 