from agents.greeting import greeting
def intent_action(intent):
    """
    This function takes the detected intent and performs the corresponding action.
    It returns a dictionary containing the response, whether user confirmation is required,
    and any additional entities related to the intent.
    """
    if intent.intent == "GREETING":
        return greeting(intent.response)

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
        return {
            "response": f"Playing {intent.entities.get('show_name', 'the show')}.",
            "requires_confirmation": True,
            "entities": {"show_name": intent.entities.get("show_name")}
        }
    elif intent.intent == "ORDER_GROCERIES":
        return {
            "response": f"Ordering groceries: {intent.entities.get('items', 'no items specified')}.",
            "requires_confirmation": True,
            "entities": {"items": intent.entities.get("items")}
        }
    elif intent.intent == "GENERAL_QUESTION":
        return {
            "response": intent.response,
            "requires_confirmation": False,
            "entities": {}
        }
    elif intent.intent == "GENERAL_CONVERSATION":
        return {
            "response": intent.response,
            "requires_confirmation": False,
            "entities": {}
        }
    else:  # UNKNOWN
        return {
            "response": "I'm not sure how to help with that.",
            "requires_confirmation": False,
            "entities": {}
        }