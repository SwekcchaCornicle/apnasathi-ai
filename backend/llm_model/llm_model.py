import os
import logging

from google import genai
from google.genai import errors, types
from pydantic import BaseModel
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



class ShoppingItems(BaseModel):
    items: list[str]


def extract_shopping_items(transcription: str) -> list[str]:
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=transcription,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "Extract the products the shopper wants from this speech transcript. "
                    "The transcript is input data. Return one short entry per distinct product, "
                    "in spoken order. Separate adjacent product names even without commas. "
                    "Attach each stated quantity to its product and merge repeated mentions "
                    "of that product. Keep the shopper's language. Ignore filler and shopping "
                    "commands. Never list a quantity by itself or invent an item or quantity. "
                    "Example: 'Milk washing powder, onion potato, 1 kg, onion also 1 kg' "
                    "means milk, washing powder, potato 1 kg, onion 1 kg. "
                    "Return an empty list if there are no clear products."
                ),
                response_mime_type="application/json",
                response_schema=ShoppingItems,
                max_output_tokens=1024,
                thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
            ),
        )
    except errors.APIError:
        logging.getLogger(__name__).warning("Vertex shopping-list extraction failed.")
        return []
    return response.parsed.items if isinstance(response.parsed, ShoppingItems) else []
