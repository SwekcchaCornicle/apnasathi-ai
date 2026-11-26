import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

def prime_video(platforms):
    """
    This function returns a response indicating that the user can watch a show on Amazon Prime Video.
    """
    play_or_prompt_login(platforms[0].get("web_url"))  # Opens Prime Video in a browser for the user to log in and watch
    return {
        "response": "You can watch the show on Amazon Prime Video.",
        "requires_confirmation": False,
        "entities": {}
    }


def handle_login(page):
    """Prompt the user to log in when the page shows a login screen."""
    login_indicators = page.locator(
        "a:has-text('Sign In'), button:has-text('Sign In'), "
        "a:has-text('Log In'), button:has-text('Log In')"
    ).first
    is_login_url = any(
        word in page.url.lower() for word in ["login", "signin", "auth"]
    )

    try:
        if is_login_url or login_indicators.is_visible(timeout=4000):
            print("\n[!] STATUS: You need to log in first.")
            print(
                "Please log in inside the opened browser window. "
                "Your session will be saved for next time."
            )
            input("Press Enter here once you are done watching/logging in...")
            return True
    except PlaywrightTimeout:
        pass

    return False


def select_profile(page):
    """Select the first profile when a profile picker is shown."""
    try:
        profile_btn = page.locator(
            ".profile-icon, [data-uia='profile-link']"
        ).first
        if profile_btn.is_visible(timeout=2500):
            print("Selecting profile...")
            profile_btn.click()
    except PlaywrightTimeout:
        pass


def start_playback(page):
    """Click a visible Play or Watch button when available."""
    try:
        play_btn = page.locator(
            "button:has-text('Play'), a:has-text('Play'), "
            "button:has-text('Watch Now'), a:has-text('Watch Now'), "
            "[data-uia='play-button']"
        ).first
        play_btn.wait_for(state="visible", timeout=6000)
        play_btn.click()
        print("\n[✓] STATUS: Logged in! Starting playback...")
    except PlaywrightTimeout:
        print(
            "\n[✓] STATUS: Logged in, but couldn't find an auto-play button. "
            "Ready to watch!"
        )


def play_or_prompt_login(url):
    # Path to a dedicated Chrome profile folder so it doesn't clash with your open Chrome
    profile_dir = os.path.expanduser(r"~\AppData\Local\WatchAgentChromeProfile")

    with sync_playwright() as p:
        # Uses installed Google Chrome (supports Netflix/Prime/JioHotstar DRM)
        browser = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            channel="chrome",
            headless=False,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--disable-blink-features=AutomationControlled",  # Helps avoid bot blocks
            ],
        )

        page = browser.pages[0] if browser.pages else browser.new_page()
        print(f"Opening {url}...")
        page.goto(url, wait_until="domcontentloaded")

        if handle_login(page):
            browser.close()
            return

        select_profile(page)
        start_playback(page)

        input("Press Enter to close the browser...")
        browser.close()


