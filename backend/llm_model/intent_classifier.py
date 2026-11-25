
from pydantic import BaseModel, Field
from typing import Optional, Literal


class IntentSchema(BaseModel):

    intent: Literal[
        "GREETING",
        "OPEN_APP",
        "POST_PHOTO",
        "WATCH_SHOW",
        "ORDER_GROCERIES",
        "GENERAL_QUESTION",
        "GENERAL_CONVERSATION",
        "UNKNOWN"
    ]

    application: Optional[str] = None

    confidence: float = Field(
        ge=0,
        le=1
    )

    response: str

    response_language: str = Field(description="BCP 47 language tag of the reply text, or und if undetermined")

    requires_confirmation: bool

    entities: dict = Field(default_factory=dict)
