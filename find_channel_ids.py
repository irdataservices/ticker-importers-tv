import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ.get('YOUTUBE_API_KEY')

def find_channel_id(channel_name):
    search_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={channel_name}&type=channel&key={API_KEY}"
    response = requests.get(search_url)
    data = response.json()
    
    if 'items' in data and data['items']:
        print(f"Results for '{channel_name}':")
        for i, item in enumerate(data['items']):
            channel_id = item['snippet']['channelId']
            title = item['snippet']['title']
            print(f"{i+1}. {title}: {channel_id}")
    else:
        print(f"No results found for '{channel_name}'")

if __name__ == "__main__":
    with open('channels-config.json', 'r') as f:
        channels = json.load(f)
    
    for channel in channels:
        find_channel_id(channel['name'])
        print("-" * 50) 