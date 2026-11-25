import os
from google import genai
from google.genai import types
from .intent_classifier import IntentSchema
from .prompt import intent_clasify_prompt as prompt

client = genai.Client(
    vertexai=True,
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "global")
)

def vertex_model(transcription):
    print("Transcription received:", transcription)
    intent = classify_intent(transcription)
    print("Detected intent:", intent)
    return intent


def classify_intent(transcription):
    prompt_text = prompt(transcription)
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt_text,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=IntentSchema,
            temperature=0.1
        )
    )
    return response.parsed

