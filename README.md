# AI Podcast Generator

An application that automatically generates tech news podcasts using AI.

## Features

- Fetch articles from RSS feeds
- Generate podcast scripts using OpenAI
- Convert scripts to audio using ElevenLabs
- Publish podcasts to GitHub Pages
- Customizable podcast settings
- Multiple podcast support
- User authentication
- Podcast duration control

## Setup

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and add your API keys
4. Run with `python main.py` or `gunicorn --bind 0.0.0.0:5000 main:app`

## Environment Variables

Required API keys:
- OPENAI_API_KEY: For generating podcast scripts
- ELEVENLABS_API_KEY: For text-to-speech conversion
- GITHUB_TOKEN, GITHUB_USERNAME, GITHUB_REPO: For publishing podcasts
