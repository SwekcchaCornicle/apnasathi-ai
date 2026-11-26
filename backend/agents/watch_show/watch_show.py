import logging
import os
from urllib.parse import urlsplit

import requests

from agents.speech import generate_voice
from agents.watch_show.prime_video.prime_video import play_or_prompt_login

logger = logging.getLogger(__name__)
BASE_URL = "https://api.watchmode.com/v1"


def clean_streaming_platforms(
    sources: list[dict], show_name: str
) -> list[dict]:
    """Deduplicate streaming sources and return the fields used by the caller."""
    platforms = []
    seen = set()
    for src in sources:
        key = (src["name"], src["type"])
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
        raise RuntimeError("WATCHMODE_API_KEY is missing.")
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


def watch_show(show_name, language):
    status = "failed"
    if not isinstance(show_name, str) or not show_name.strip():
        status = "missing_title"
    else:
        try:
            platforms = get_streaming_platforms(show_name.strip())
            for platform in platforms:
                url = platform.get("web_url") or ""
                parsed = urlsplit(url)
                host = parsed.hostname or ""
                if parsed.scheme == "https" and (
                    host in {"primevideo.com", "amazon.in", "amazon.com"}
                    or host.endswith((".primevideo.com", ".amazon.in", ".amazon.com"))
                ) and "prime" in platform["platform"].lower():
                    status = play_or_prompt_login(url)
                    break
        except (RuntimeError, ValueError):
            logger.warning("Could not look up a Prime Video link.")

    messages = {
        "playing": ("Video is playing in the other browser.", "वीडियो दूसरे ब्राउज़र में प्ले हो रहा है।"),
        "login_required": ("You are not logged in.", "आप ऐप में लॉग इन नहीं हैं।"),
        "failed": ("I couldn't start the video.", "वीडियो प्ले नहीं हो सका।"),
        "missing_title": ("Which video would you like to watch?", "आप कौन सा वीडियो देखना चाहते हैं?"),
    }
    english, hindi = messages[status]
    message = hindi if language.lower().split("-", 1)[0] == "hi" else english
    return {
        "response": message,
        "playback_status": status,
        "voice": generate_voice(message, language),
    }
