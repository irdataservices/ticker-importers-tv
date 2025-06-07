import os
import json
import requests
from datetime import datetime
import argparse
import re
from dotenv import load_dotenv
from db_operations import upsert_channel, insert_new_media_items, get_latest_media_item_date

# Load environment variables from .env file
load_dotenv()

# --- Better Stack (Logtail) logging setup ---
BETTERSTACK_TOKEN = os.getenv('BETTERSTACK_SOURCE_TOKEN')
BETTERSTACK_HOST = os.getenv('BETTERSTACK_INGEST_HOST')
BETTERSTACK_SOURCE_ID = os.getenv('BETTERSTACK_SOURCE_ID')

if not (BETTERSTACK_TOKEN and BETTERSTACK_HOST and BETTERSTACK_SOURCE_ID):
    print("WARNING: One or more Better Stack env vars are not set. Logging to Better Stack will not work.")
    BETTERSTACK_LOGGING_ENABLED = False
else:
    BETTERSTACK_LOGGING_ENABLED = True
    BETTERSTACK_URL = f"https://{BETTERSTACK_HOST}/{BETTERSTACK_SOURCE_ID}"

def log_to_betterstack(level, message, context=None):
    if not BETTERSTACK_LOGGING_ENABLED:
        return
    log_message = {
        'dt': None,  # Let Logtail set the timestamp
        'level': level,
        'message': message,
        'context': context or {}
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {BETTERSTACK_TOKEN}'
    }
    try:
        requests.post(BETTERSTACK_URL, headers=headers, data=json.dumps(log_message), timeout=3)
    except Exception as e:
        print(f"Failed to send log to Better Stack: {e}")

# YouTube API key should be stored as an environment variable
API_KEY = os.environ.get('YOUTUBE_API_KEY')

def load_config(config_path):
    """Load the channel configuration file."""
    with open(config_path, 'r') as f:
        return json.load(f)

def parse_human_readable_duration_to_seconds(hr_duration_str):
    """Convert human-readable duration string (e.g., "1h 2m 3s", "45s") to total seconds."""
    if not hr_duration_str:
        return 0
    
    total_seconds = 0
    hours = 0
    minutes = 0
    seconds = 0

    h_match = re.search(r'(\d+)h', hr_duration_str)
    if h_match:
        hours = int(h_match.group(1))
    
    m_match = re.search(r'(\d+)m', hr_duration_str)
    if m_match:
        minutes = int(m_match.group(1))

    # Ensure 's' is not preceded by 'm' or 'h' if it's part of 'maxres' or similar in other contexts,
    # though for "Xh Ym Zs" format, it's usually fine.
    # A simple search for '(\\d+)s' should work for the output of format_duration.
    s_match = re.search(r'(\d+)s', hr_duration_str)
    if s_match:
        # Check if the 's' found is part of a 'Xs' unit and not, for example, 'maxres'
        # This check is a bit naive; assumes 's' with digits before it is seconds.
        # Given format_duration, this should be safe.
        full_match_str = s_match.group(0)
        if hr_duration_str.endswith(full_match_str) or " " + full_match_str in hr_duration_str :
             seconds = int(s_match.group(1))
        
    total_seconds = (hours * 3600) + (minutes * 60) + seconds
    return total_seconds

def parse_duration_to_seconds(duration_str):
    """Convert YouTube API duration format (ISO 8601 PT...S) to total seconds."""
    if not duration_str or not duration_str.startswith('PT'):
        return 0

    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return 0

    hours, minutes, seconds = match.groups()

    total_seconds = 0
    if hours:
        total_seconds += int(hours) * 3600
    if minutes:
        total_seconds += int(minutes) * 60
    if seconds:
        total_seconds += int(seconds)
        
    return total_seconds

def format_duration(duration_str):
    """Convert YouTube API duration format to human-readable format."""
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        if duration_str == "PT": return "0s" # Handle empty PT case
        return "" # Or handle other invalid formats as needed

    hours, minutes, seconds = match.groups()
    
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds: # Append seconds if present, even if 0 and other parts exist (e.g. PT1M0S -> 1m 0s)
        parts.append(f"{seconds}s")
    
    if not parts:
        if duration_str == "PT0S": return "0s"
        return "0s" # Default for unexpected empty like just "PT"
        
    return " ".join(parts)

def get_channel_id(username):
    """Get channel ID from username."""
    url = f"https://www.googleapis.com/youtube/v3/channels?part=id&forUsername={username}&key={API_KEY}"
    print(f"Attempting to get channel ID for \'{username}\' via username/handle URL: {url}") # Retained basic log
    response = requests.get(url)
    try:
        response.raise_for_status() # Check for HTTP errors
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error when fetching channel by username: {e}")
        print(f"Response content: {response.text}") # Keep response text on error
        return None
    data = response.json()
    
    if 'items' in data and data['items']:
        return data['items'][0]['id']
    
    # If not found by username, try searching by custom URL
    # This is a workaround as the API doesn't directly support @ handles
    print(f"Channel not found by username: {username}. Trying alternative search method...")
    
    search_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={username}&type=channel&key={API_KEY}"
    print(f"Attempting to search for channel \'{username}\' via general search URL: {search_url}") # Retained basic log
    search_response = requests.get(search_url)
    try:
        search_response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error when searching for channel: {e}")
        print(f"Response content: {search_response.text}") # Keep response text on error
        return None
        
    search_data = search_response.json()
    
    if 'items' in search_data and search_data['items']:
        for item in search_data['items']:
            if item['snippet']['title'].lower() == username.lower() or username.lower() in item['snippet']['channelTitle'].lower():
                return item['snippet']['channelId']
        
        # If no exact match, return the first result
        return search_data['items'][0]['snippet']['channelId']
    
    return None

def get_channel_videos(channel_id):
    """Fetch videos from a YouTube channel."""
    # Get the uploads playlist ID
    channel_url = f"https://www.googleapis.com/youtube/v3/channels?part=contentDetails&id={channel_id}&key={API_KEY}"
    print(f"Fetching channel contentDetails from: {channel_url}") # Retained
    response = requests.get(channel_url)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error when fetching channel details for {channel_id}: {e}")
        print(f"Response content: {response.text}") # Keep response text on error
        return []
    channel_data = response.json()
    
    if 'items' not in channel_data or not channel_data['items']:
        print(f"No channel 'items' found or 'items' is empty in contentDetails for ID: {channel_id}")
        return []
    
    uploads_playlist_id = channel_data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    
    # Now get the videos from the uploads playlist
    videos = []
    next_page_token = None
    
    while True:
        playlist_url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=50&playlistId={uploads_playlist_id}&key={API_KEY}"
        if next_page_token:
            playlist_url += f"&pageToken={next_page_token}"
        
        print(f"Fetching playlist items from: {playlist_url}") # Retained
        response = requests.get(playlist_url)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"HTTP error when fetching playlist items for playlist {uploads_playlist_id}: {e}")
            print(f"Response content: {response.text}") # Keep response text on error
            break 
        playlist_data = response.json()
        
        if 'items' not in playlist_data:
            print(f"No 'items' in playlist_data for playlist {uploads_playlist_id}. Breaking loop.")
            break
        
        video_ids = [item['snippet']['resourceId']['videoId'] for item in playlist_data['items'] if item.get('snippet') and item['snippet'].get('resourceId')]
        
        if not video_ids:
            print(f"No video IDs extracted from playlist items for playlist {uploads_playlist_id}. Breaking loop.")
            break

        # Get detailed video information
        video_details_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails&id={','.join(video_ids)}&key={API_KEY}"
        print(f"Fetching video details from: {video_details_url}") # Retained
        video_details_response = requests.get(video_details_url)
        try:
            video_details_response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"HTTP error when fetching video details for video IDs {' ,'.join(video_ids)}: {e}")
            print(f"Response content: {video_details_response.text}") # Keep response text on error
            next_page_token = playlist_data.get('nextPageToken')
            if not next_page_token:
                break
            else:
                continue 
        video_details_data = video_details_response.json()
        
        for video in video_details_data.get('items', []):
            video_id = video['id']
            title = video['snippet']['title']
            description = video['snippet']['description']
            published_at = video['snippet']['publishedAt']
            
            duration_iso = video['contentDetails']['duration']
            duration_seconds_val = parse_duration_to_seconds(duration_iso)
            
            # Filter videos shorter than 2 minutes (120 seconds)
            if duration_seconds_val < 120:
                human_readable_duration = format_duration(duration_iso)
                print(f"Skipping short video {video_id} ({human_readable_duration if human_readable_duration else 'N/A'}): {title}")
                continue

            duration = format_duration(duration_iso)
            
            # Get thumbnail URLs
            thumbnails = video['snippet']['thumbnails']
            thumbnail_urls = {
                'default': thumbnails.get('default', {}).get('url', ''),
                'medium': thumbnails.get('medium', {}).get('url', ''),
                'high': thumbnails.get('high', {}).get('url', ''),
                'standard': thumbnails.get('standard', {}).get('url', ''),
                'maxres': thumbnails.get('maxres', {}).get('url', '')
            }
            
            # Convert published_at to YYYY-MM-DD format
            date = datetime.fromisoformat(published_at.replace('Z', '+00:00')).strftime('%Y-%m-%d')
            
            videos.append({
                "id": video_id,
                "title": title,
                "date": date,
                "contentType": "podcast",  # Assuming all videos are podcasts
                "links": [
                    {
                        "type": "video",
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "platform": "YouTube"
                    }
                ],
                "duration": duration,
                "duration_iso": duration_iso,
                "description": description,
                "thumbnails": thumbnail_urls
            })
        
        next_page_token = playlist_data.get('nextPageToken')
        if not next_page_token:
            break
    
    return videos

def main():
    parser = argparse.ArgumentParser(description='Fetch YouTube videos from configured channels')
    parser.add_argument('--config', default='channels-config.json', help='Path to channel configuration file')
    args = parser.parse_args()
    
    # Load channel configuration
    channels = load_config(args.config)
    
    for channel in channels:
        print(f"\nProcessing channel: {channel['name']}")
        
        # Get channel ID if not provided
        channel_id = channel.get('youtubeId')
        if not channel_id and channel.get('youtubeUsername'):
            channel_id = get_channel_id(channel['youtubeUsername'])
            if not channel_id:
                print(f"Could not find channel ID for {channel['name']}")
                log_to_betterstack('error', f"Could not find channel ID for {channel['name']}")
                continue

        # Get the latest date for this channel from the DB
        latest_date = get_latest_media_item_date(channel['slug'])
        if latest_date:
            print(f"Latest date in DB for {channel['slug']}: {latest_date}")
        else:
            print(f"No existing media_items for {channel['slug']} in DB.")
        
        # Fetch all videos from YouTube
        videos = get_channel_videos(channel_id)
        if not videos:
            print(f"No videos found for channel {channel['name']}")
            log_to_betterstack('info', f"No videos found for channel {channel['name']}")
            continue
        print(f"Found {len(videos)} videos for {channel['name']}")
        
        # Filter videos to only those with date >= latest_date (if any)
        if latest_date:
            videos_to_process = [v for v in videos if v['date'] >= latest_date]
        else:
            videos_to_process = videos
        print(f"Processing {len(videos_to_process)} new or potentially missing videos for {channel['name']}")

        # Print only the videos that will actually be processed
        for video in videos_to_process:
            print(f"Processing video {video['id']} with date {video['date']}")
        
        # Upsert channel to database
        upsert_channel(channel)
        
        # Insert only new media items to database, with logging for each video
        from supabase_config import get_supabase_client
        supabase = get_supabase_client()
        existing = supabase.table('media_items').select('id').eq('channel_slug', channel['slug']).execute()
        existing_ids = {item['id'] for item in (existing.data or [])}
        new_count = 0
        for video in videos_to_process:
            if video['id'] in existing_ids:
                continue
            try:
                record = {
                    'id': video['id'],
                    'title': video['title'],
                    'date': video['date'],
                    'content_type': video.get('contentType', 'podcast'),
                    'duration': video.get('duration'),
                    'description': video.get('description'),
                    'youtube_id': video['id'],
                    'image': video.get('thumbnails', {}).get('high') or video.get('thumbnails', {}).get('default'),
                    'channel_slug': channel['slug'],
                    'youtube_url': f"https://www.youtube.com/watch?v={video['id']}"
                }
                supabase.table('media_items').insert(record).execute()
                log_to_betterstack('info', f"Added video {video['id']} ({video['title']}) to channel {channel['slug']}")
                new_count += 1
            except Exception as e:
                log_to_betterstack('error', f"Failed to add video {video['id']} ({video['title']}) to channel {channel['slug']}: {e}")
        log_to_betterstack('info', f"Channel processed: {channel['name']} (slug: {channel['slug']}), new videos added: {new_count}")
        print(f"Successfully processed {len(videos_to_process)} videos for {channel['name']} (new: {new_count})")

    # NOTE: This script is safe to re-run. It will only insert missing items, and always re-processes the most recent date to handle partial failures or backfilling.

if __name__ == '__main__':
    main()

    # Standalone test for Logtail logging
    BETTERSTACK_TOKEN = os.environ.get('BETTERSTACK_SOURCE_TOKEN')
    print(f"Logtail token loaded: {BETTERSTACK_TOKEN}")
    if BETTERSTACK_TOKEN:
        log_to_betterstack('info', "Standalone Logtail test log: handler initialised and token loaded.")
        print("Sent test log to Better Stack.")
    else:
        print("WARNING: BETTERSTACK_SOURCE_TOKEN is not set. Logging to Better Stack will not work.") 