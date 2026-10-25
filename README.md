# Xtream IPTV Python Server

A lightweight, high-performance Flask-based Xtream Codes API compatible IPTV server designed to serve local media libraries (movies, series, and live streams) with virtualized genre categorization and multi-account support.

## Features

- **Xtream Codes API Compatible**: Works out of the box with standard IPTV players (IPTV Smarters, Tivimate, TiviX, custom Flutter apps, etc.).
- **Virtualized Categories**: Maps media files to clean, virtual categories prefixed with `FR |` without altering your physical folder structure.
- **Multi-Account Isolation**:
  - `admin`: Standard media library.
  - `system`: System/lost directory media.
  - `all`: Combined media source.
  - `demo`: Dedicated mock demonstration library (`library_demo.json`) with working test streams (ideal for App Store / Play Store review submissions).
- **TMDB Integration**: Automatic metadata scraping (posters, backdrops, cast, ratings, overviews) with local JSON caching.
- **Systemd Integration**: Persistent background execution with auto-restart capabilities.

## Installation & Configuration

1. **Clone the repository**:
   ```bash
   git clone https://github.com/PsyOhm23/xtream-server.git
   cd xtream-server
   ```

2. **Install dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Configure the server**:
   Copy `config.example.json` to `config.json` and adjust your media directories and TMDB API key:
   ```bash
   cp config.example.json config.json
   ```
   Edit `config.json`:
   ```json
   {
       "tmdb_api_key": "YOUR_TMDB_API_KEY",
       "media_dirs": ["/path/to/your/videos"],
       "system_dirs": ["/path/to/your/system"],
       "users": {
           "admin": "admin",
           "system": "system",
           "all": "all",
           "demo": "demo"
       }
   }
   ```

4. **Run the server**:
   ```bash
   python3 server.py
   ```
   Or install it as a systemd service for automatic background execution.
