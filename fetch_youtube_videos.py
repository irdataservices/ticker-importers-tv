import os
import json
import requests
from datetime import datetime
import argparse
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
            print(f"Processing video {video_id} with date {date}")
            
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

def update_channel_json(channel, videos):
    """Update the JSON file for a channel with new videos."""
    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)
    
    json_path = f"data/{channel['slug']}.json"
    existing_videos_from_file = []
    
    print("\n==================================================")
    print(f"Processing {channel['name']}:")
    print(f"Found {len(videos)} videos from YouTube API (after filtering shorts)")
    
    # Load existing videos if the file exists
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r') as f:
                existing_videos_from_file = json.load(f)
            
            videos_to_keep = []
            removed_short_video_ids = []
            print(f"Checking {len(existing_videos_from_file)} existing videos in {json_path} for shorts...")

            for idx, ex_video in enumerate(existing_videos_from_file):
                is_short = False
                video_id_for_log = ex_video.get('id', f"entry_{idx}")
                duration_iso_str = ex_video.get('duration_iso')
                
                if duration_iso_str:
                    seconds = parse_duration_to_seconds(duration_iso_str)
                    if 0 < seconds < 120:
                        is_short = True
                elif 'duration' in ex_video: # Legacy entry, try parsing human-readable duration
                    seconds = parse_human_readable_duration_to_seconds(ex_video['duration'])
                    if 0 < seconds < 120:
                        is_short = True
                
                if is_short:
                    removed_short_video_ids.append(video_id_for_log)
                else:
                    videos_to_keep.append(ex_video)
            
            if removed_short_video_ids:
                print(f"Removed {len(removed_short_video_ids)} existing short videos: {', '.join(removed_short_video_ids)}")
            
            existing_videos = videos_to_keep # This list is now filtered

            print(f"Found {len(existing_videos)} existing videos in {json_path} (after filtering shorts)")
            if existing_videos:
                existing_videos.sort(key=lambda x: x.get('date', ''), reverse=True)
                print(f"Most recent video date: {existing_videos[0]['date']}")
                print(f"Oldest video date: {existing_videos[-1]['date']}")
        except json.JSONDecodeError:
            print(f"Error reading {json_path}, will create new file.")
            existing_videos = [] # Ensure it's an empty list
            print("Most recent video date: None")
            print("Oldest video date: None")
    else:
        print(f"No existing video file found at {json_path}. Will create a new one.")
        existing_videos = [] # <--- ADD THIS LINE
        print("Most recent video date: None")
        print("Oldest video date: None")
    
    # Create a dictionary of existing videos by ID for quick lookup
    existing_video_ids = {video.get('id'): video for video in existing_videos}
    
    # Update existing videos and add new ones
    updated = False
    new_videos = []
    updated_videos = []
    
    for video in videos:
        video_id = video.get('id')
        if video_id in existing_video_ids:
            # Check if we need to update any fields
            existing_video = existing_video_ids[video_id]
            
            # Preserve Apple Podcasts link if it exists
            apple_podcast_link = next((link for link in existing_video.get('links', []) 
                                     if link.get('platform') == 'Apple Podcasts'), None)
            if apple_podcast_link:
                video_links = video.get('links', [])
                if not any(link.get('platform') == 'Apple Podcasts' for link in video_links):
                    video_links.append(apple_podcast_link)
                    video['links'] = video_links
            
            # Check if thumbnails need to be added or updated
            if 'thumbnails' not in existing_video or existing_video['thumbnails'] != video['thumbnails']:
                print(f"Updating thumbnails for video {video_id}")
                existing_video_ids[video_id] = video
                updated = True
                updated_videos.append(video_id)
            # Check if any other fields need updating
            elif any(existing_video.get(key) != video.get(key) for key in ['title', 'description', 'duration']):
                print(f"Updating fields for video {video_id}")
                existing_video_ids[video_id] = video
                updated = True
                updated_videos.append(video_id)
        else:
            # This is a new video
            print(f"Adding new video {video_id}")
            print(f"Title: {video.get('title')}")
            print(f"Date: {video.get('date')}")
            existing_videos.append(video)
            updated = True
            new_videos.append(video_id)
    
    if new_videos:
        print(f"\nFound {len(new_videos)} new videos:")
        for vid_id in new_videos:
            print(f"- {vid_id}")
        print() # Add a blank line for spacing

    if updated_videos:
        print(f"\nUpdated details for {len(updated_videos)} existing videos: {', '.join(updated_videos)}")
        print()
    
    # Rebuild the list from the updated dictionary if new videos were added or existing ones updated
    if updated:
        # Consolidate new videos with potentially updated existing ones
        # New videos were appended to existing_videos list directly if they were truly new.
        # Updated videos replaced entries in existing_video_ids.
        
        # Rebuild the list correctly to include new and updated videos
        current_video_list = []
        processed_ids_for_rebuild = set()

        # Add all videos from the updated existing_video_ids dictionary
        for vid_id, video_data in existing_video_ids.items():
            current_video_list.append(video_data)
            processed_ids_for_rebuild.add(vid_id)

        # Add any genuinely new videos that were appended to existing_videos list
        # but not part of the original existing_video_ids keys
        for video_data in existing_videos:
            if video_data.get('id') not in processed_ids_for_rebuild:
                current_video_list.append(video_data)
                processed_ids_for_rebuild.add(video_data.get('id'))

        # Sort videos by date (newest first)
        current_video_list.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # Save the updated list
        with open(json_path, 'w') as f:
            json.dump(current_video_list, f, indent=2)
        print(f"Updated {json_path} with new videos or information")
        print(f"Total videos after update: {len(current_video_list)}")
    else:
        print(f"No updates needed for {json_path}")
    print("==================================================")

def main():
    parser = argparse.ArgumentParser(description='Fetch YouTube videos and save to JSON')
    parser.add_argument('--config', default='channels-config.json', help='Path to channel configuration file')
    parser.add_argument('--channel', help='Process only this channel slug')
    args = parser.parse_args()
    
    if not API_KEY:
        print("Error: YOUTUBE_API_KEY environment variable not set")
        return
    
    channels = load_config(args.config)
    
    for channel in channels:
        if args.channel and args.channel != channel['slug']:
            continue

        print(f"Processing channel: {channel['name']}")
        
        # Script now assumes youtubeId is present in the config.
        # If not, get_channel_videos will likely fail when it tries to use a None or missing ID.
        # A more robust solution would be to call get_channel_id if youtubeId is missing,
        # but that's outside the scope of this cleanup.
        if not channel.get('youtubeId'):
            print(f"youtubeId missing for {channel['name']}. Skipping channel. Please ensure config has youtubeId.")
            continue

        videos = get_channel_videos(channel['youtubeId'])
        update_channel_json(channel, videos)

if __name__ == "__main__":
    main() 