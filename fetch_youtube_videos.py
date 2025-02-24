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

def format_duration(duration_str):
    """Convert YouTube API duration format to human-readable format."""
    # YouTube duration format is like PT1H30M15S
    hours = re.search(r'(\d+)H', duration_str)
    minutes = re.search(r'(\d+)M', duration_str)
    seconds = re.search(r'(\d+)S', duration_str)
    
    duration_parts = []
    if hours:
        duration_parts.append(f"{hours.group(1)}h")
    if minutes:
        duration_parts.append(f"{minutes.group(1)}m")
    if seconds and not (hours or minutes):
        duration_parts.append(f"{seconds.group(1)}s")
    
    return " ".join(duration_parts)

def get_channel_id(username):
    """Get channel ID from username."""
    url = f"https://www.googleapis.com/youtube/v3/channels?part=id&forUsername={username}&key={API_KEY}"
    response = requests.get(url)
    data = response.json()
    
    if 'items' in data and data['items']:
        return data['items'][0]['id']
    
    # If not found by username, try searching by custom URL
    # This is a workaround as the API doesn't directly support @ handles
    print(f"Channel not found by username: {username}. Trying alternative methods...")
    
    # Try with "c/" prefix (some channels use this format)
    search_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={username}&type=channel&key={API_KEY}"
    search_response = requests.get(search_url)
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
    response = requests.get(channel_url)
    channel_data = response.json()
    
    if 'items' not in channel_data or not channel_data['items']:
        print(f"No channel found with ID: {channel_id}")
        return []
    
    uploads_playlist_id = channel_data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    
    # Now get the videos from the uploads playlist
    videos = []
    next_page_token = None
    
    while True:
        playlist_url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=50&playlistId={uploads_playlist_id}&key={API_KEY}"
        if next_page_token:
            playlist_url += f"&pageToken={next_page_token}"
        
        response = requests.get(playlist_url)
        playlist_data = response.json()
        
        if 'items' not in playlist_data:
            break
        
        video_ids = [item['snippet']['resourceId']['videoId'] for item in playlist_data['items']]
        
        # Get detailed video information
        video_details_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails&id={','.join(video_ids)}&key={API_KEY}"
        video_details_response = requests.get(video_details_url)
        video_details_data = video_details_response.json()
        
        for video in video_details_data.get('items', []):
            video_id = video['id']
            title = video['snippet']['title']
            description = video['snippet']['description']
            published_at = video['snippet']['publishedAt']
            duration = format_duration(video['contentDetails']['duration'])
            
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
                "description": description
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
    existing_videos = []
    
    # Load existing videos if the file exists
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r') as f:
                existing_videos = json.load(f)
        except json.JSONDecodeError:
            print(f"Error reading {json_path}, creating new file")
    
    # Create a dictionary of existing videos by ID for quick lookup
    existing_video_ids = {video.get('id'): video for video in existing_videos}
    
    # Update existing videos and add new ones
    updated = False
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
                    updated = True
        else:
            # This is a new video
            existing_videos.append(video)
            updated = True
    
    # Sort videos by date (newest first)
    existing_videos.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    # Save the updated list if changes were made
    if updated:
        with open(json_path, 'w') as f:
            json.dump(existing_videos, f, indent=2)
        print(f"Updated {json_path} with new videos")
    else:
        print(f"No updates needed for {json_path}")

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
        videos = get_channel_videos(channel['youtubeId'])
        update_channel_json(channel, videos)

if __name__ == "__main__":
    main() 