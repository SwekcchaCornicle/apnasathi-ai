from .speech import generate_voice


def greeting(message, language):
    """
    This function takes a greeting message and performs the corresponding action.
    It returns a dictionary containing the response, whether user confirmation is required,
    and any additional entities related to the intent.
    """
    return {
        "response": message,
        "requires_confirmation": False,
        "entities": {},
        "voice": generate_voice(message, language)
    }