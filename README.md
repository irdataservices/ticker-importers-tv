# YouTube Channel Video Importer

This project automatically fetches videos from specified YouTube channels and stores them in a Supabase database. It's designed to run as a GitHub Action that checks for new videos hourly, or can be run manually for backfilling and recovery.

## Features

- Fetches videos from multiple YouTube channels
- Stores video metadata in Supabase
- Skips existing videos and supports safe backfilling
- Runs automatically via GitHub Actions
- Can be run manually for testing or recovery

## Setup

### Prerequisites

- Python 3.10 or higher
- A YouTube Data API v3 key
- Access to a Supabase project (with the correct tables set up)

### Installation

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `.env` file with your API keys, Supabase credentials, and Better Stack logging variables:

```
YOUTUBE_API_KEY=your_youtube_api_key
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
BETTERSTACK_SOURCE_TOKEN=your_betterstack_source_token
BETTERSTACK_INGEST_HOST=your_betterstack_ingest_host
BETTERSTACK_SOURCE_ID=your_betterstack_source_id
```

- The three `BETTERSTACK_*` variables are required for logging to Better Stack/Logtail. You can find these in your Better Stack Logtail source settings.

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
- `slug`: Used as the unique identifier for the channel in the database

## Usage

### Running Locally

Run the script with: `python fetch_youtube_videos.py`

The script will only fetch and insert new videos (by date and ID) for each channel, and is safe to re-run for backfilling or recovery.

### Finding Channel IDs

If you need to find a channel ID, you can use the included helper script: `python find_channel_ids.py`

## GitHub Actions

This project includes a GitHub Actions workflow that runs hourly from 7am to 10pm UTC. To set it up:

1. Add your YouTube API key, Supabase credentials, and Better Stack logging variables as repository secrets:
   - `YOUTUBE_API_KEY`
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `BETTERSTACK_SOURCE_TOKEN`
   - `BETTERSTACK_INGEST_HOST`
   - `BETTERSTACK_SOURCE_ID`
2. The workflow will automatically run according to the schedule
3. You can also trigger it manually from the Actions tab

## Data Storage

All video and channel data is stored in your Supabase database, not in local JSON files. The script is designed to efficiently fetch and insert only new videos, and can safely be re-run to recover from partial failures.

## License

[MIT License](LICENSE)