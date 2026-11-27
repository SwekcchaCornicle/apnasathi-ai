import base64
import json
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import expect, sync_playwright


class SpaHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/record":
            self.path = "/index.html"
        super().do_GET()


@pytest.fixture(scope="module")
def frontend_url():
    dist = Path(__file__).resolve().parents[1] / "dist"
    assert (dist / "index.html").exists(), "Build the frontend before running the browser suite."
    with ThreadingHTTPServer(("127.0.0.1", 0), partial(SpaHandler, directory=dist)) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            worker.join()


def fake_jwt():
    claims = {"iat": int(time.time()), "exp": int(time.time()) + 3600}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"e30.{payload}.fixture"


@pytest.mark.parametrize(("language", "code", "width"), [("English", "en", 1280), ("Hindi", "hi", 390)])
def test_signup_confirmation_srp_chat_recovery_and_history(frontend_url, language, code, width):
    token = fake_jwt()
    cognito_requests = []
    messages = []
    conversations = []
    unavailable = False
    instagram_publish_attempts = []

    def cognito(route):
        target = route.request.headers.get("x-amz-target", "").rsplit(".", 1)[-1]
        if route.request.method == "OPTIONS":
            route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*"})
            return
        data = route.request.post_data_json
        cognito_requests.append(target)
        assert "SecretHash" not in data
        if target == "InitiateAuth":
            assert data["AuthFlow"] == "USER_SRP_AUTH"
            assert "PASSWORD" not in data["AuthParameters"]
            result = {
                "ChallengeName": "PASSWORD_VERIFIER",
                "ChallengeParameters": {"USER_ID_FOR_SRP": "qa@example.test", "SRP_B": "02", "SALT": "01", "SECRET_BLOCK": "Zml4dHVyZQ=="},
                "Session": "fixture",
            }
        elif target == "RespondToAuthChallenge":
            assert data["ChallengeName"] == "PASSWORD_VERIFIER"
            assert data["ChallengeResponses"]["PASSWORD_CLAIM_SIGNATURE"]
            result = {"AuthenticationResult": {"IdToken": token, "AccessToken": token, "RefreshToken": "fixture"}}
        elif target == "SignUp":
            assert {item["Name"]: item["Value"] for item in data["UserAttributes"]} == {"name": "QA Fixture", "email": "qa@example.test"}
            result = {"UserConfirmed": False, "UserSub": "fixture"}
        else:
            result = {}
        route.fulfill(json=result, headers={"Access-Control-Allow-Origin": "*"})

    def api(route):
        request = route.request
        path = request.url.split("/api/v1", 1)[1].split("?")[0]
        result = {}
        headers = {"Access-Control-Allow-Origin": frontend_url, "Access-Control-Allow-Headers": "authorization,content-type", "Access-Control-Allow-Methods": "GET,POST,PATCH,DELETE", "Access-Control-Allow-Credentials": "true"}
        if request.method == "OPTIONS":
            route.fulfill(status=204, headers=headers)
            return
        if path != "/auth/cognito":
            assert request.headers["authorization"] == f"Bearer {token}"
        if path == "/users/me/profile":
            assert request.post_data_json["preferred_language"] == code
        elif path == "/conversations" and request.method == "POST":
            assert request.post_data_json["language"] == code
            result = {"id": "conversation-1", "title": "New conversation", "language": code, "updated_at": "2026-11-27T12:00:00Z"}
            conversations.append(result)
        elif path == "/conversations":
            result = conversations
        elif path.endswith("/messages"):
            result = messages
        elif path == "/assistant/audio":
            assert request.method == "POST"
            assert "multipart/form-data" in request.headers["content-type"]
            assert "conversation_id=conversation-1" in request.url
            transcript = "Voice fixture question"
            messages.extend([{"id": "voice-1", "role": "user", "content": transcript}, {"id": "voice-2", "role": "assistant", "intent": "GENERAL_QUESTION", "content": "Voice fixture response"}])
            result = {"user_message_id": "voice-1", "assistant_message_id": "voice-2", "transcription": transcript, "response": "Voice fixture response", "intent": "GENERAL_QUESTION", "language": code}
        elif path == "/watch-show/troubleshoot":
            result = {"step": "playing", "response": "Is the video playing?", "done": False}
            if b"Yes" in (request.post_data_buffer or b""):
                result = {"step": "confirmed", "response": "The video is playing.", "done": True}
        elif path == "/instagram/photo":
            result = {"step": "authorization", "action": {"url": "https://www.instagram.com/oauth/authorize"}}
        elif path == "/instagram/status":
            result = {"step": "caption"}
        elif path == "/instagram/publish":
            instagram_publish_attempts.append(request.post_data_buffer)
            result = {"step": "published", "response": "Fixture post confirmed"}
        elif path == "/assistant/chat":
            if unavailable:
                route.abort()
                return
            text = request.post_data_json["message"]
            answer = "Fixture response"
            intent = "GENERAL_QUESTION"
            extra = {}
            if text == "Watch a fixture video":
                intent, answer = "WATCH_SHOW", "Fixture video is ready"
                extra["playback"] = {"url": "https://www.netflix.com/", "platform": "Netflix"}
            elif text == "Help me post a fixture photo to Instagram":
                intent, answer = "POST_PHOTO", "Please attach a photo"
            elif text == "Shop for fixture groceries":
                intent, answer = "ORDER_GROCERIES", "Choose a store"
                extra["shopping"] = {"choices": ["Blinkit", "Amazon"], "done": False, "actions": [{"url": "https://blinkit.com/", "label": "Open Blinkit"}], "session": {"items": ["bread", "1 packet of milk", "2 kg potato"]}}
            elif text == "Cancel":
                intent, answer = "ORDER_GROCERIES", "Shopping finished"
                extra["shopping"] = {"choices": [], "done": True}
            user_id, assistant_id = str(len(messages)), str(len(messages) + 1)
            messages.extend([{"id": user_id, "role": "user", "content": text}, {"id": assistant_id, "role": "assistant", "intent": intent, "content": answer, **extra}])
            result = {"user_message_id": user_id, "assistant_message_id": assistant_id, "response": answer, "intent": intent, "language": code, **extra}
        route.fulfill(json=result, headers=headers)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", args=["--disable-gpu"])
        page = browser.new_page(viewport={"width": width, "height": 850})
        page.route("https://cognito-idp.*.amazonaws.com/**", cognito)
        page.route("**/api/v1/**", api)
        page.set_default_timeout(8000)
        page.on("pageerror", lambda error: print(f"Browser error: {error}"))
        page.goto(frontend_url)
        page.get_by_role("button", name="Looking for another language?").click()
        expect(page.get_by_role("status")).to_have_text("We are about to launch support for this language.")
        page.get_by_role("radio", name=language).click()
        page.get_by_role("button", name="Continue").click()
        page.get_by_role("button", name="Create account", exact=True).click()
        page.locator('input[type="email"]').fill("qa@example.test")
        page.get_by_label("Full name").fill("   ")
        page.locator('input[type="password"]').fill("Fixture-only-123!")
        page.get_by_role("button", name="Create account", exact=True).click()
        expect(page.get_by_role("status")).to_have_text("Enter your full name.")
        assert cognito_requests == []
        page.get_by_label("Full name").fill("  QA Fixture  ")
        page.get_by_role("button", name="Create account", exact=True).click()
        page.get_by_placeholder("Enter code from email").fill("123456")
        page.get_by_role("button", name="Verify email").click()
        page.get_by_role("button", name="Sign in", exact=True).click()
        composer = page.locator("textarea")
        expect(composer).to_be_enabled()
        unavailable = True
        composer.fill("Fixture question")
        composer.press("Enter")
        expect(composer).to_have_value("Fixture question")
        expect(composer).to_be_enabled()
        unavailable = False
        composer.press("Enter")
        expect(page.get_by_text("Fixture response", exact=True)).to_be_visible()
        page.reload()
        expect(page.get_by_text("Fixture response", exact=True)).to_be_visible()
        page.get_by_role("button", name="Open conversation sidebar").click()
        expect(page.get_by_role("heading", name="Questions")).to_be_visible()
        search = page.get_by_role("searchbox").or_(page.get_by_label("Search conversation history"))
        search.fill("no match")
        expect(page.get_by_role("heading", name="Questions")).to_have_count(0)
        search.fill("Fixture question")
        page.get_by_role("button", name="New conversation Fixture question", exact=False).click()
        expect(page.get_by_text("Fixture response", exact=True)).to_be_visible()
        page.evaluate("""() => {
            window.qaSpeech = [];
            window.qaPlayback = [];
            window.speechSynthesis.speak = (utterance) => window.qaSpeech.push(utterance.text);
            window.open = () => ({
              document: { body: {} },
              closed: false,
              close() { this.closed = true; },
              location: { replace: (url) => window.qaPlayback.push(url) },
            });
            window.qaStoppedTracks = 0;
            window.qaAllowMic = false;
            navigator.mediaDevices.getUserMedia = async () => {
              if (!window.qaAllowMic) throw new DOMException('Fixture permission denial', 'NotAllowedError');
              return { getTracks: () => [{ stop: () => window.qaStoppedTracks++ }] };
            };
            window.MediaRecorder = class {
              static isTypeSupported() { return true; }
              constructor() { this.mimeType = 'audio/webm'; }
              start() { this.state = 'recording'; }
              stop() {
                this.state = 'inactive';
                this.ondataavailable?.({ data: new Blob(['fixture'], { type: this.mimeType }) });
                this.onstop?.();
              }
            };
        }""")
        record = page.get_by_role("button", name="Speak to ApnaSathi")
        record.click()
        expect(page.get_by_role("status")).to_contain_text("microphone")
        page.evaluate("window.qaAllowMic = true")
        record.click()
        page.get_by_role("button", name="Stop recording and send").click()
        expect(page.get_by_text("Voice fixture question", exact=True)).to_be_visible()
        expect(page.get_by_text("Voice fixture response", exact=True)).to_be_visible()
        assert page.evaluate("window.qaStoppedTracks") == 1
        assert page.evaluate("window.qaSpeech") == ["Voice fixture response"]
        if width == 1280:
            def send(text):
                composer.fill(text)
                composer.press("Enter")

            send("Shop for fixture groceries")
            expect(page.get_by_role("button", name="Blinkit")).to_be_visible()
            expect(page.get_by_role("list", name="Shopping list").get_by_role("listitem")).to_have_count(3)
            expect(page.get_by_role("link", name="Open Blinkit")).to_have_count(0)
            page.get_by_role("button", name="End shopping").click()
            expect(page.get_by_text("Shopping finished", exact=True)).to_be_visible()

            send("Watch a fixture video")
            expect(page.get_by_role("link", name="Open in Netflix")).to_have_attribute("href", "https://www.netflix.com/")
            assert page.evaluate("window.qaPlayback") == []
            page.get_by_role("button", name="Troubleshoot playback").click()
            expect(page.get_by_text("Is the video playing?", exact=True)).to_be_visible()
            page.get_by_role("button", name="Yes").click()
            expect(page.get_by_text("The video is playing.", exact=True)).to_be_visible()
            page.get_by_role("button", name="Close playback guide").click()

            send("Help me post a fixture photo to Instagram")
            expect(page.get_by_role("button", name="Attach photo")).to_be_disabled()
            page.get_by_label("Choose a JPEG").set_input_files({"name": "fixture.jpg", "mimeType": "image/jpeg", "buffer": b"jpeg-fixture"})
            page.get_by_role("button", name="Attach photo").click()
            expect(page.get_by_role("link", name="Connect Instagram")).to_be_visible()
            page.get_by_role("button", name="Check connection").click()
            page.get_by_label("Caption", exact=True).fill("Fixture caption")
            page.get_by_role("button", name="Review post").click()
            expect(page.get_by_text("Fixture caption", exact=True)).to_be_visible()
            assert instagram_publish_attempts == []
            page.get_by_role("button", name="Confirm and post to Instagram").click()
            expect(page.get_by_text("Fixture post confirmed", exact=True)).to_be_visible()
            assert b"true" in instagram_publish_attempts[0]
        page.get_by_role("button", name="Sign out").click()
        expect(page.get_by_role("button", name="Sign in", exact=True)).to_be_visible()
        assert cognito_requests == ["SignUp", "ConfirmSignUp", "InitiateAuth", "RespondToAuthChallenge"]
        browser.close()


def test_cognito_password_reset_reports_invalid_and_expired_codes(frontend_url):
    targets = []

    def cognito(route):
        headers = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*"}
        if route.request.method == "OPTIONS":
            route.fulfill(status=204, headers=headers)
            return
        target = route.request.headers.get("x-amz-target", "").rsplit(".", 1)[-1]
        targets.append(target)
        data = route.request.post_data_json
        assert "SecretHash" not in data
        if target == "ForgotPassword":
            route.fulfill(json={}, headers=headers)
            return
        assert target == "ConfirmForgotPassword"
        errors = {"000001": "CodeMismatchException", "000002": "ExpiredCodeException"}
        error = errors.get(data["ConfirmationCode"])
        if error:
            route.fulfill(status=400, json={"__type": error, "message": "fixture"}, headers=headers | {"x-amzn-errortype": error})
        else:
            route.fulfill(json={}, headers=headers)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", args=["--disable-gpu"])
        page = browser.new_page(viewport={"width": 820, "height": 1000})
        page.set_default_timeout(8000)
        page.route("https://cognito-idp.*.amazonaws.com/**", cognito)
        page.goto(frontend_url)
        page.get_by_role("button", name="Continue").click()
        page.get_by_role("button", name="Forgot password?").click()
        page.get_by_label("Email address").fill("qa@example.test")
        page.get_by_role("button", name="Send reset code").click()
        page.get_by_label("New password").fill("Fixture-only-456!")
        code = page.get_by_label("Email verification code")
        submit = page.get_by_role("button", name="Reset password", exact=True)
        for value, message in (
            ("000001", "The verification code is incorrect."),
            ("000002", "The code has expired. Request a new one."),
        ):
            code.fill(value)
            submit.click()
            expect(page.get_by_role("status")).to_have_text(message)
        code.fill("123456")
        submit.click()
        expect(page.get_by_role("status")).to_have_text("Password reset successfully. Please sign in.")
        assert targets == ["ForgotPassword", "ConfirmForgotPassword", "ConfirmForgotPassword", "ConfirmForgotPassword"]
        browser.close()
