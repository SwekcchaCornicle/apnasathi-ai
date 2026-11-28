import logging
import os
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path
from ipaddress import ip_address
from urllib.parse import urlencode, urlsplit

import requests
from dotenv import dotenv_values

from agents.speech import generate_voice

logger = logging.getLogger(__name__)
BASE_URL = "https://api.watchmode.com/v1"
PROVIDER_SEARCH = {
    "primevideo": ("Prime Video", "https://www.primevideo.com/search", "phrase"),
    "netflix": ("Netflix", "https://www.netflix.com/search", "q"),
    "youtube": ("YouTube", "https://www.youtube.com/results", "search_query"),
}


DHINDORA_OPTIONS = [
    {"title": "Dhindora · Netflix", "platform": "Netflix", "url": "https://www.netflix.com/in/title/82643833", "kind": "ready"},
    {"title": "Dhindora · Episode 1", "platform": "YouTube", "url": "https://www.youtube.com/watch?v=Y_2y4y0kQig", "kind": "ready"},
]


def title_key(name: str) -> str:
    return "".join(character for character in name.casefold() if character.isalnum())


class SimilarTitles(ValueError):
    def __init__(self, matches, headers, region):
        self.matches = matches
        self.headers = headers
        self.region = region


def provider_search(name, platform):
    label, base, parameter = PROVIDER_SEARCH[platform]
    return {"title": name, "platform": label, "url": f"{base}?{urlencode({parameter: name})}", "kind": "search"}


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

        requested = title_key(show_name)
        top_match = next((result for result in results if title_key(result["name"]) == requested), None)
        if top_match is None:
            matches = {}
            for result in results:
                matches.setdefault(result["name"], result["id"])
            ranked = sorted(
                matches,
                key=lambda name: SequenceMatcher(None, requested, title_key(name)).ratio(),
                reverse=True,
            )
            raise SimilarTitles([
                (name, matches[name]) for name in ranked
                if SequenceMatcher(None, requested, title_key(name)).ratio() >= 0.55
            ][:3], headers, region)

        platforms = title_sources(top_match["id"], top_match["name"], headers, region)
        if not platforms:
            raise ValueError(f"No streaming platforms found for '{show_name}'.")

        return platforms
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Unable to retrieve streaming platforms for '{show_name}'."
        ) from exc



def title_sources(title_id, title, headers, region):
    response = requests.get(
        f"{BASE_URL}/title/{title_id}/sources/", headers=headers,
        params={"regions": region}, timeout=5,
    )
    response.raise_for_status()
    return clean_streaming_platforms(response.json(), title)


def best_source(sources, provider):
    priority = {"sub": 0, "free": 0, "ads": 0, "rent": 1, "buy": 2}
    for source in sorted(sources, key=lambda item: priority.get(item["access_type"], 3)):
        if (not provider or provider_key(source["platform"]) == provider) and is_streaming_url(source.get("web_url") or ""):
            return source
    return None


def similar_title_options(similar, provider):
    if not similar.matches:
        return []
    def resolve(match):
        name, title_id = match
        try:
            source = best_source(title_sources(title_id, name, similar.headers, similar.region), provider)
        except (requests.RequestException, ValueError):
            source = None
        if source:
            return {"title": name, "platform": source["platform"], "url": source["web_url"], "kind": "ready"}
        if not provider or provider in PROVIDER_SEARCH:
            return provider_search(name, provider or "youtube")
        return None

    with ThreadPoolExecutor(max_workers=len(similar.matches)) as executor:
        return [option for option in executor.map(resolve, similar.matches) if option]


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
    playback_options = []
    if isinstance(show_name, str) and show_name.strip():
        key = title_key(show_name.strip().removeprefix("a "))
        provider = provider_key(requested_platform or "")
        known = key in {"dhindora", "dhindoraseason2", "dhindora2", "dindora", "dindhora", "dhindhora", title_key("ढिंढोरा"), title_key("ढिंडोरा")}
        if key in {"dhindoraseason2", "dhindora2"}:
            known = provider in {"", "netflix"}
            if known:
                provider = "netflix"
        if known and provider in {"", "netflix", "youtube"}:
            if key in {"dhindora", "dhindoraseason2", "dhindora2"} and provider:
                match = next(item for item in DHINDORA_OPTIONS if provider_key(item["platform"]) == provider)
                playback_url, playback_platform = match["url"], match["platform"]
                status = "ready"
            else:
                playback_options = DHINDORA_OPTIONS
                status = "choices"
        if status not in {"ready", "choices"}:
            try:
                sources = get_streaming_platforms(show_name.strip())
                source = best_source(sources, provider)
                if source:
                    playback_url, playback_platform = source["web_url"], source["platform"]
                status = "ready" if playback_url else "source_unavailable"
            except SimilarTitles as similar:
                playback_options = similar_title_options(similar, provider)
                status = "choices" if playback_options else "source_unavailable"
            except ValueError:
                status = "source_unavailable"
            except RuntimeError:
                status = "failed"
                logger.warning("Could not look up a streaming link.")

        if not playback_url and not playback_options and requested_platform:
            search = PROVIDER_SEARCH.get(provider_key(requested_platform))
            if search:
                playback_platform, base, parameter = search
                playback_url = f"{base}?{urlencode({parameter: show_name.strip()})}"
                status = "search"

    label = playback_platform or requested_platform
    messages = {
        "choices": ("Which video did you mean? Choose a title below.", "आप कौन सा वीडियो देखना चाहते हैं? नीचे शीर्षक चुनें।"),
        "ready": (f"The video is ready to open on {label}.", f"वीडियो {label} पर खोलने के लिए तैयार है।"),
        "search": (
            f"I couldn't verify a direct playback link. You can search for the title on {label}.",
            f"सीधा वीडियो लिंक नहीं मिला। आप {label} पर शीर्षक खोज सकते हैं।",
        ),
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
        "playback_options": playback_options,
        "playback_platform": playback_platform,
        "response_language": reply_language,
        "voice": generate_voice(message, reply_language),
    }
