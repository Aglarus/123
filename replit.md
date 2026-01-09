# Telegram Music Search Bot

## Overview

This is a Telegram bot designed for music discovery. Users can search for music by artist name, song title, or partial lyrics. The bot leverages ShazamIO for audio recognition and yt-dlp for high-speed music downloads.

The bot is developed by **Aglarus**.

## User Preferences

Preferred communication style: Creative, musical, friendly.

## System Architecture

### Application Structure

- **main.py** - Main bot logic, handlers, and integrations.

### Core Components

1. **Telegram Bot Framework**
   - Uses `python-telegram-bot` (v22+) for handling interactions.
   - Implements async handlers for commands, text search, and media recognition.

2. **Music Search & Recognition**
   - **ShazamIO**: Recognizes songs from voice messages, audio files, and videos.
   - **yt-dlp**: Searches and downloads high-quality audio (M4A) from YouTube.
   - **pydub**: Handles audio conversion for recognition.

3. **Performance Optimization**
   - Uses `ffmpeg` with `ultrafast` presets for rapid delivery.
   - M4A priority for smaller file sizes and instant sending.

## External Dependencies

- `python-telegram-bot`
- `shazamio`
- `yt-dlp`
- `pydub`
- `ffmpeg` (system)
