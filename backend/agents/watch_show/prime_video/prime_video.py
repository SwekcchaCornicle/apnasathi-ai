import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor

from playwright.sync_api import Error as PlaywrightError, sync_playwright

logger = logging.getLogger(__name__)
_browser_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="prime-video")
_playwright = None
_browser = None


def handle_login(page):
    return (
        any(path in page.url.lower() for path in ("/ap/signin", "/auth/", "/login"))
        or page.get_by_role("link", name=re.compile(r"^sign in(?: to watch)?$", re.I)).first.is_visible()
        or page.get_by_role("button", name=re.compile(r"^sign in(?: to watch)?$", re.I)).first.is_visible()
    )


def start_playback(page):
    play = page.get_by_role(
        "button", name=re.compile(r"^(?:play|watch now|resume)(?:\b(?!.*trailer).*)?$", re.I)
    ).or_(page.get_by_role("link", name=re.compile(r"^(?:play|watch now|resume)$", re.I)))
    play.first.click(timeout=6000)
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('video')).some(
            video => !video.paused && !video.ended && video.readyState >= 2 && video.currentTime > 0
        )""",
        timeout=12000,
    )


def _open_and_play(url):
    global _playwright, _browser
    try:
        if _playwright is None:
            _playwright = sync_playwright().start()
        if _browser is None:
            profile_dir = os.path.expanduser(r"~\AppData\Local\WatchAgentChromeProfile")
            _browser = _playwright.chromium.launch_persistent_context(
                user_data_dir=profile_dir, channel="chrome", headless=False
            )
            _browser.on("close", _clear_browser)

        page = _browser.pages[0] if _browser.pages else _browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        if handle_login(page):
            return "login_required"

        profile = page.locator(".profile-icon, [data-uia='profile-link']").first
        if profile.is_visible():
            profile.click(timeout=4000)
        try:
            start_playback(page)
        except PlaywrightError:
            if handle_login(page):
                return "login_required"
            raise
        return "playing"
    except PlaywrightError:
        logger.warning("Prime Video playback could not be verified.", exc_info=True)
        return "failed"


def _clear_browser(_context):
    global _browser
    _browser = None


def play_or_prompt_login(url):
    # Keep Playwright calls on one thread and leave the browser open after the API returns.
    return _browser_worker.submit(_open_and_play, url).result()
