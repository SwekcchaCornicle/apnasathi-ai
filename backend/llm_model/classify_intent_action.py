from agents.greeting import greeting


def intent_action(intent):
    """
    This function takes the detected intent and performs the corresponding action.
    It returns a dictionary containing the response, whether user confirmation is required,
    and any additional entities related to the intent.
    """
    if intent.intent == "GREETING":
        return greeting(intent.response, intent.response_language)

    elif intent.intent == "OPEN_APP":
        return {
            "response": f"Opening {intent.application}.",
            "requires_confirmation": True,
            "entities": {"application": intent.application}
        }
    elif intent.intent == "POST_PHOTO":
        return {
            "response": "Please provide the photo you want to post.",
            "requires_confirmation": True,
            "entities": {}
        }
    elif intent.intent == "WATCH_SHOW":
        from agents.watch_show.watch_show import watch_show

        return watch_show(intent.entities.get("show_name"), intent.response_language)
    elif intent.intent == "ORDER_GROCERIES":
        return {
            "response": f"Ordering groceries: {intent.entities.get('items', 'no items specified')}.",
            "requires_confirmation": True,
            "entities": {"items": intent.entities.get("items")}
        }
    elif intent.intent in {"GENERAL_QUESTION", "GENERAL_CONVERSATION"}:
        language = intent.response_language.lower().split("-", 1)[0]
        warning = (
            "यहाँ चैट करना उपयुक्त नहीं है।"
            if language == "hi"
            else "This is not the place for chatting."
        )
        return {
            "response": f"{intent.response}\n\n{warning}",
            "requires_confirmation": False,
            "entities": {},
        }
    else:  # UNKNOWN
        return {
            "response": "I'm not sure how to help with that.",
            "requires_confirmation": False,
            "entities": {}
        }