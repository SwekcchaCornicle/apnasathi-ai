import logging
import os
from pathlib import Path
from ipaddress import ip_address
from urllib.parse import urlsplit

import requests
from dotenv import dotenv_values

from agents.speech import generate_voice

logger = logging.getLogger(__name__)
BASE_URL = "https://api.watchmode.com/v1"


def clean_streaming_platforms(
    sources: list[dict], show_name: str
) -> list[dict]:
    """Deduplicate streaming sources and return the fields used by the caller."""
    platforms = []
    seen = set()
    for src in sources:
        key = (src["name"], src["type"], src.get("web_url"))
        if key not in seen:
            seen.add(key)
            platforms.append({
                "show_name": show_name,
                "platform": src["name"],
                "access_type": src["type"],
                "web_url": src.get("web_url"),
            })

    return platforms


def get_streaming_platforms(show_name: str, region: str = "IN") -> list[dict]:
    """Finds streaming platforms for a given show name and country code (e.g., 'IN', 'US')."""
    api_key = os.getenv("WATCHMODE_API_KEY")
    if not api_key:
        config = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
        api_key = config.get("WATCHMODE_API_KEY") or config.get("watch_mode_api")
    if not api_key:
        raise RuntimeError("Set WATCHMODE_API_KEY or watch_mode_api in agents/.env.")
    headers = {"X-API-Key": api_key}

    # Step 1: Search for the show by name to get its Watchmode ID
    search_url = f"{BASE_URL}/search/"
    search_params = {
        "search_field": "name",
        "search_value": show_name,
        "types": "tv,movie",
    }

    try:
        search_res = requests.get(
            search_url, headers=headers, params=search_params, timeout=10
        )
        search_res.raise_for_status()
        results = search_res.json().get("title_results", [])

        if not results:
            raise ValueError(f"No streaming platforms found for '{show_name}'.")

        # Take the top search match
        top_match = results[0]
        title_id = top_match["id"]
        matched_name = top_match["name"]

        # Step 2: Fetch streaming sources using the title_id
        sources_url = f"{BASE_URL}/title/{title_id}/sources/"
        sources_params = {"regions": region}

        sources_res = requests.get(
            sources_url, headers=headers, params=sources_params, timeout=10
        )
        sources_res.raise_for_status()
        sources = sources_res.json()

        platforms = clean_streaming_platforms(sources, matched_name)

        if not platforms:
            raise ValueError(f"No streaming platforms found for '{show_name}'.")

        return platforms
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Unable to retrieve streaming platforms for '{show_name}'."
        ) from exc


def provider_key(name: str) -> str:
    key = "".join(character for character in name.casefold() if character.isalnum())
    return {
        "amazonprime": "primevideo",
        "amazonprimevideo": "primevideo",
        "amazonvideo": "primevideo",
        "disneyplushotstar": "hotstar",
        "jiohotstar": "hotstar",
        "appletvplus": "appletv",
    }.get(key, key)


def is_streaming_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname or ""
        if parsed.scheme != "https" or parsed.username is not None or "." not in hostname:
            return False
        if hostname.endswith((".localhost", ".local", ".internal")):
            return False
        try:
            ip_address(hostname)
        except ValueError:
            return True
    except ValueError:
        pass
    return False


def watch_show(show_name, language, requested_platform=None):
    status = "missing_title"
    playback_url = None
    playback_platform = None
    if isinstance(show_name, str) and show_name.strip():
        try:
            sources = get_streaming_platforms(show_name.strip())
            # Prefer included/free options before rental or purchase listings.
            priority = {"sub": 0, "free": 0, "ads": 0, "rent": 1, "buy": 2}
            for source in sorted(sources, key=lambda item: priority.get(item["access_type"], 3)):
                platform = source["platform"]
                url = source.get("web_url") or ""
                if requested_platform and provider_key(platform) != provider_key(requested_platform):
                    continue
                if is_streaming_url(url):
                    playback_url = url
                    playback_platform = platform
                    break
            status = "ready" if playback_url else "source_unavailable"
        except ValueError:
            status = "source_unavailable"
        except RuntimeError:
            status = "failed"
            logger.warning("Could not look up a streaming link.")

    label = playback_platform or requested_platform
    messages = {
        "ready": (f"The video is ready to open on {label}.", f"वीडियो {label} पर खोलने के लिए तैयार है।"),
        "failed": ("I couldn't look up this video.", "इस वीडियो का लिंक खोजा नहीं जा सका।"),
        "source_unavailable": (
            f"I couldn't find a watch link on {label}." if label else "I couldn't find a watch link for this title.",
            f"{label} पर वीडियो का लिंक नहीं मिला।" if label else "इस शीर्षक के लिए वीडियो का लिंक नहीं मिला।",
        ),
        "missing_title": ("Which video would you like to watch?", "आप कौन सा वीडियो देखना चाहते हैं?"),
    }
    reply_language = "hi" if language.lower().split("-", 1)[0] == "hi" else "en"
    message = messages[status][reply_language == "hi"]
    return {
        "response": message,
        "playback_status": status,
        "playback_url": playback_url,
        "playback_platform": playback_platform,
        "response_language": reply_language,
        "voice": generate_voice(message, reply_language),
    }
