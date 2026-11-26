
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
    show_name: Optional[str] = Field(
        default=None,
        description="Requested series or film title for WATCH_SHOW, or null if no title is given",
    )

    shopping_items: list[str] = Field(default_factory=list, description="Items the user explicitly wants to buy")
    confidence: float = Field(
        ge=0,
        le=1
    )

    response: str

    response_language: str = Field(description="BCP 47 language tag of the reply text, or und if undetermined")

    requires_confirmation: bool

    entities: dict = Field(default_factory=dict)
