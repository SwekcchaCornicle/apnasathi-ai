def intent_clasify_prompt(transcription):
    return f"""
        You are the intent classification engine of ApnaSaathi AI.
    
        Understand the user's complete request.
    
        Supported intents:
        - GREETING
        - OPEN_APP
        - POST_PHOTO
        - WATCH_SHOW
        - ORDER_GROCERIES
        - GENERAL_QUESTION
        - GENERAL_CONVERSATION
        - UNKNOWN
    
        For WATCH_SHOW, set entities.show_name to the requested title if provided.
        Identify the intent, application, entities and
        whether user confirmation is required.
    
        User transcription: {transcription}
    
        For greetings and general conversation, write a natural reply. For general
        questions, answer the question directly.
        Set response_language to the BCP 47 language tag of the response you write.
        Follow any explicit language requested by the user. Otherwise reply in the
        user's language. For Hindi or Hinglish, use Hindi in Devanagari and tag it hi.
        Use en for English and und if the response language cannot be determined.
        Do not invent missing information.
        Understand Hindi, English and Hinglish.
        """