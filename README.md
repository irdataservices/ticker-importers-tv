# YouTube Channel Video Importer

This project automatically fetches videos from specified YouTube channels and stores them in JSON format. It's designed to run as a GitHub Action that checks for new videos hourly.

## Features

- Fetches videos from multiple YouTube channels
- Stores video metadata in JSON format
- Preserves existing Apple Podcasts links
- Runs automatically via GitHub Actions
- Can be run manually for testing

## Setup

### Prerequisites

- Python 3.10 or higher
- A YouTube Data API v3 key

### Installation

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `.env` file with your YouTube API key: `YOUTUBE_API_KEY=your_api_key_here`

### Configuration

Edit the `channels-config.json` file to include the YouTube channels you want to track:

```json
[
  {
    "name": "Channel Name",
    "youtubeId": "UCxxxxxxxxxxxxxxxx",
    "slug": "channel-slug"
  }
]
```

- `name`: Display name of the channel
- `youtubeId`: YouTube channel ID (starts with UC...)
- `slug`: Used for the JSON filename (e.g., `data/channel-slug.json`)

## Usage

### Running Locally

Run the script with: `python fetch_youtube_videos.py`

To process a specific channel only: `python fetch_youtube_videos.py --channel channel-slug`

### Finding Channel IDs

If you need to find a channel ID, you can use the included helper script: `python find_channel_ids.py`

Alternatively, you can find a channel ID by:
1. Going to the channel's YouTube page
2. Viewing the page source (right-click > View Page Source)
3. Searching for "channelId" or "externalId"

## GitHub Actions

This project includes a GitHub Actions workflow that runs hourly from 7am to 10pm UTC. To set it up:

1. Add your YouTube API key as a repository secret named `YOUTUBE_API_KEY`
2. The workflow will automatically run according to the schedule
3. You can also trigger it manually from the Actions tab

## Output Format

Videos are stored in JSON files in the `data/` directory, with one file per channel. Each file contains an array of video objects with metadata including title, date, links, and description.

## License

[MIT License](LICENSE)