#!/bin/bash
cd /home/pi/xtream-server
export MEDIA_DIR="/media/3To/videos"
export XTREAM_USER="admin"
export XTREAM_PASS="admin"
python3 server.py

