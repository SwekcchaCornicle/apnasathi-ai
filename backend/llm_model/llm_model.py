import logging

from google.genai import types
from pydantic import BaseModel
from .intent_classifier import IntentSchema
from .prompt import intent_clasify_prompt as prompt

from .vertex_auth import get_vertex_client

logger = logging.getLogger(__name__)


class VertexUnavailable(RuntimeError):
    pass


def generate_content(**request):
    try:
        return get_vertex_client().models.generate_content(**request)
    except Exception as error:
        # SDK exceptions can contain upstream bodies or identifying request metadata.
        logger.warning("Vertex request failed (%s).", type(error).__name__)
        raise VertexUnavailable("The AI service is temporarily unavailable.") from None


def vertex_model(transcription, *, user_context=None, preferred_language="en"):
    return classify_intent(transcription, user_context=user_context, preferred_language=preferred_language)


def classify_intent(transcription, *, user_context=None, preferred_language="en"):
    prompt_text = prompt(transcription, user_context=user_context, preferred_language=preferred_language)
    response = generate_content(
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
        response = generate_content(
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
    except VertexUnavailable:
        return []
    return response.parsed.items if isinstance(response.parsed, ShoppingItems) else []
