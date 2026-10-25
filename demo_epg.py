"""Demo EPG built from the current time, in one-hour slots.

Listings run from six hours ago through twenty-four hours ahead, so a store
review always sees a filled guide.
"""

import base64
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

import demo_generator

_SLOT_SECONDS = 3600
_PAST_SECONDS = 6 * _SLOT_SECONDS
_FUTURE_SECONDS = 24 * _SLOT_SECONDS


def short_epg(video, lang, now=None):
    """Next four programmes for one channel. Titles are Base64, as Xtream expects."""
    now = now or datetime.now(timezone.utc)
    current = _floor_hour(now)
    listings = []
    for offset in range(4):
        start = current + timedelta(hours=offset)
        listings.append(_listing(video, lang, start))
    return {"epg_listings": listings}


def xmltv(channels, lang, now=None):
    """XMLTV document covering now-6h to now+24h for every demo live channel."""
    now = now or datetime.now(timezone.utc)
    start = _floor_hour(now) - timedelta(seconds=_PAST_SECONDS)
    stop = _floor_hour(now) + timedelta(seconds=_FUTURE_SECONDS)
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<tv generator-info-name="xtream-server-demo">',
    ]
    for channel in channels:
        channel_id = channel["epg_channel_id"]
        name = escape(channel["name"])
        parts.append(f'  <channel id="{escape(channel_id)}">')
        parts.append(f'    <display-name>{name}</display-name>')
        parts.append("  </channel>")
    for channel in channels:
        slot = start
        while slot < stop:
            title, description = _copy(channel, lang, slot)
            parts.append(
                f'  <programme start="{_xmltv_stamp(slot)}" stop="{_xmltv_stamp(slot + timedelta(hours=1))}" channel="{escape(channel["epg_channel_id"])}">'
            )
            parts.append(f"    <title>{escape(title)}</title>")
            parts.append(f"    <desc>{escape(description)}</desc>")
            parts.append("  </programme>")
            slot += timedelta(hours=1)
    parts.append("</tv>")
    return "\n".join(parts) + "\n"


def _listing(video, lang, start):
    title, description = _copy(video, lang, start)
    stop = start + timedelta(hours=1)
    return {
        "id": f"{video['epg_channel_id']}_{int(start.timestamp())}",
        "epg_id": video["epg_channel_id"],
        "channel_id": video["epg_channel_id"],
        "title": _b64(title),
        "description": _b64(description),
        "start": start.strftime("%Y-%m-%d %H:%M:%S"),
        "end": stop.strftime("%Y-%m-%d %H:%M:%S"),
        "start_timestamp": str(int(start.timestamp())),
        "stop_timestamp": str(int(stop.timestamp())),
        "lang": lang,
    }


def _copy(video, lang, start):
    seed = int(video["stream_id"]) * 1_000_003 + int(start.timestamp())
    return demo_generator.describe(lang, seed)


def _floor_hour(moment):
    moment = moment.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return moment


def _xmltv_stamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S +0000")


def _b64(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")
