from agents.speech import generate_voice
from agents.watch_show.watch_show import provider_key

PROMPTS = {
    "opened": ("Did {platform} open in the new tab? Say yes or no.", "क्या {platform} नए टैब में खुला? हाँ या नहीं कहें।"),
    "profile": ("Choose your Netflix profile if asked. Is your profile selected?", "अगर Netflix पूछे, तो अपनी प्रोफ़ाइल चुनें। क्या आपने प्रोफ़ाइल चुन ली?"),
    "profile_retry": ("Select your profile on the Who's watching screen. Were you able to select it?", "कौन देख रहा है वाली स्क्रीन पर अपनी प्रोफ़ाइल चुनें। क्या आप उसे चुन पाए?"),
    "playing": ("Is the video playing? Say yes or no.", "क्या वीडियो चल रहा है? हाँ या नहीं कहें।"),
    "tab": ("Select Open in {platform} in the chat. Did the tab open?", "चैट में {platform} का लिंक दबाएँ। क्या टैब खुल गया?"),
    "signin": ("Are you signed in to {platform}?", "क्या आप {platform} में लॉग इन हैं?"),
    "signin_retry": ("Sign in on the {platform} tab. Were you able to sign in?", "{platform} टैब में लॉग इन करें। क्या आप लॉग इन कर पाए?"),
    "retry": ("Press Play in {platform}. Is the video playing now?", "{platform} में प्ले दबाएँ। क्या अब वीडियो चल रहा है?"),
    "confirmed": ("The video is playing.", "वीडियो चल रहा है।"),
    "finished": ("Playback could not be confirmed. Check the message shown in {platform}.", "वीडियो चलने की पुष्टि नहीं हुई। {platform} में दिख रहा संदेश देखें।"),
}

# Each step can only advance on a recognized yes or no. No LLM is involved.
NEXT_STEP = {
    "opened": ("playing", "tab"),
    "profile": ("retry", "profile_retry"),
    "profile_retry": ("retry", "finished"),
    "playing": ("confirmed", "signin"),
    "tab": ("playing", "finished"),
    "signin": ("retry", "signin_retry"),
    "signin_retry": ("retry", "finished"),
    "retry": ("confirmed", "finished"),
}
YES = {"yes", "yeah", "yep", "haan", "han", "haa", "ha", "हाँ", "हां", "हा", "ہاں", "جی", "जी"}
NO = {"no", "nope", "naa", "na", "nahi", "nahin", "nhi", "ना", "नहीं", "नही", "نہیں", "نا"}


def guide_reply(step: str, language: str, transcript: str | None = None, *, platform: str = "the streaming service") -> dict:
    language = "hi" if language.lower().split("-", 1)[0] == "hi" else "en"
    retry = False
    provider = provider_key(platform)
    if transcript is not None:
        # Trim trailing punctuation without stripping Indic vowel marks.
        answer = transcript.strip().casefold().strip(" .,!?:;।؟،")
        if answer in YES:
            # Wait for a separate spoken tab-open reply before checking the Netflix profile.
            step = "profile" if provider == "netflix" and step in {"opened", "tab"} else NEXT_STEP[step][0]
        elif answer in NO:
            step = NEXT_STEP[step][1]
        else:
            retry = True

    # Provider-specific wording shares the same yes/no transitions.
    retry_prompts = {
        "netflix": (
            "Choose your Netflix profile if prompted, then press Play. Is the video playing now?",
            "अगर Netflix प्रोफ़ाइल पूछे, तो उसे चुनें और प्ले दबाएँ। क्या अब वीडियो चल रहा है?",
        ),
        "primevideo": (
            "In Prime Video, select an episode and press Play or Resume. Is the video playing now?",
            "Prime Video में एपिसोड चुनें और प्ले या रिज़्यूम दबाएँ। क्या अब वीडियो चल रहा है?",
        ),
    }
    prompt = PROMPTS[step]
    if step == "retry":
        prompt = retry_prompts.get(provider, prompt)
    message = prompt[language == "hi"].format(platform=platform)
    if retry:
        prefix = "कृपया केवल हाँ या नहीं कहें। " if language == "hi" else "Please say only yes or no. "
        message = prefix + message
    return {
        "step": step,
        "done": step not in NEXT_STEP,
        "response": message,
        "voice": generate_voice(message, language),
    }
