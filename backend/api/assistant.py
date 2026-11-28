"""Authenticated chat orchestration: history -> semantic cache -> Gemini fallback."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, TypeAdapter
from request_tracing import stage
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from agents.daily_planner import plan_daily_command
from agents.shoaping import ShoppingSession, retailer_item_links, shopping_message, shopping_reply, start_shopping
from auth.dependencies import get_current_user
from database.models import Conversation, Memory, Message, SearchHistory, User
from database.daily_models import DailyAction
from database.session import get_db
from llm_model.classify_intent_action import intent_action
from llm_model.llm_model import VertexUnavailable, vertex_model
from services.answer_reuse import find_reusable_answer, normalize_question, store_approved_answer
from api.persistence import require_supported_language
from storage.s3_audio_storage import AudioStorageError, MAX_AUDIO_REQUEST_BYTES, validate_audio

router = APIRouter(tags=["assistant"])
logger = logging.getLogger(__name__)
AUTO_CACHE_MIN_CONFIDENCE = 0.90
CURRENT_INFO = re.compile(r"(today|current|latest|now|live|weather|price|stock|yesterday|tomorrow)|आज|अभी|ताज़ा|मौसम|कीमत", re.IGNORECASE)
ACTION_REQUEST = re.compile(r"\b(use|open|launch|call|phone|send|message|text|post|upload|share|order|buy|purchase|book|play|watch|navigate|install|delete|cancel)\b|(खोलो|खोलना|कॉल|फोन|भेजो|मैसेज|पोस्ट|ऑर्डर|मंगाओ|खरीदो|चलाओ|देखो)", re.IGNORECASE)

BLINKIT = re.compile(r"\bblinkit\b|ब्लिंकिट", re.IGNORECASE)
SHOPPING_STATE = TypeAdapter(ShoppingSession)
CHANGE_ITEMS = re.compile(r"^(?:change|replace) (?:the )?items(?: to)?[ :]+(.+)$", re.IGNORECASE)
DAILY_COMMAND = re.compile(r"\b(remind me|set a reminder|reminder|to[- ]?do|todo|task|track (?:an? )?expense|log (?:an? )?expense|plan (?:my )?meal|meal plan|shopping list|draft (?:a )?message|write (?:a )?message)\b|रिमाइंडर|याद दिला|याद रखना|टू[- ]?डू|काम की सूची|खर्चा|खर्च लिख|खाने का प्लान|खाना प्लान|शॉपिंग लिस्ट|मैसेज लिख", re.IGNORECASE)
PREVIOUS_ORDER = re.compile(r"\b(last|previous|prior)\b.{0,30}\b(order|ordered|time)\b|पिछली बार|पिछला ऑर्डर", re.IGNORECASE)


def is_action_request(message: str) -> bool:
    return bool(ACTION_REQUEST.search(message))


class AssistantChatRequest(BaseModel):
    conversation_id: UUID
    message: str = Field(min_length=1, max_length=4000)


class AssistantChatResponse(BaseModel):
    conversation_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID
    intent: str
    response: str
    language: str
    source: str
    similarity: float | None = None
    transcription: str | None = None
    requires_confirmation: bool = False
    shopping: dict | None = None
    playback: dict | None = None
    daily_actions: list[dict] | None = None


def _shopping_in_chat(session: ShoppingSession) -> ShoppingSession:
    if session.step == "item" and not session.store:
        return replace(session, step="store")
    if session.step in {"login", "offer_login", "sign_in", "sign_in_self"}:
        return replace(session, step="item" if session.items else "items")
    if session.step in {"offer_checkout", "checkout_cart", "checkout_address", "checkout_payment", "payment_ready"}:
        return replace(session, step="done")
    return session


def _shopping_chat_payload(session: ShoppingSession) -> dict:
    message = shopping_message(session)
    if session.step == "item":
        message["response"] = f"Your list includes {session.items[session.item_index]}. Did the item link work and show what you wanted? Say “change items to…” to update the list."
    elif session.step == "store":
        message["response"] = "Which platform would you like to shop on? Choose Blinkit, Amazon, or Swiggy Instamart."
    elif session.step == "cart":
        message["response"] = "Is your shopping list complete?"
    elif session.step == "done":
        message["response"] = "Your shopping list is saved in this chat."
    message.pop("action", None)
    message["actions"] = retailer_item_links(session.store, session.items)
    return {**message, "session": asdict(session)}


def _chat_conversation(db: Session, user_id: UUID, conversation_id: UUID) -> Conversation:
    conversation = db.scalar(select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == user_id,
        Conversation.is_archived.is_(False),
    ))
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation


def _saved_blinkit_reply(db: Session, user_id: UUID, language: str) -> str:
    requests = db.scalars(select(Message).where(
        Message.user_id == user_id,
        Message.intent == "ORDER_GROCERIES", Message.role == "user",
        or_(Message.content.ilike("%blinkit%"), Message.content.contains("ब्लिंकिट"),
            Message.metadata_json["shopping_store"].as_string() == "Blinkit"),
    ).order_by(Message.created_at.desc(), Message.id.desc()).limit(20))
    latest = next((item for item in requests if not PREVIOUS_ORDER.search(item.content)), None)
    if latest is None:
        return (
            "आपकी सहेजी गई बातचीत में मुझे कोई पिछला ब्लिंकिट अनुरोध नहीं मिला।"
            if language == "hi" else "I couldn't find a previous Blinkit request in your saved chats."
        )
    items = (latest.metadata_json or {}).get("shopping_items")
    saved_items = [item for item in items if isinstance(item, str) and item.strip()] if isinstance(items, list) else []
    details = ", ".join(saved_items) if saved_items else latest.content
    return (
        f"आपकी पिछली सहेजी गई ब्लिंकिट बातचीत में यह अनुरोध था: {details}। मैं ब्लिंकिट पर दिए गए ऑर्डर की पुष्टि नहीं कर सकता।"
        if language == "hi" else
        f"Your last saved Blinkit chat included: {details}. I can't verify orders placed on Blinkit."
    )


@router.post("/assistant/chat", response_model=AssistantChatResponse)
def assistant_chat(
    payload: AssistantChatRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Answer a text message using private semantic reuse before invoking Gemini."""
    conversation = _chat_conversation(db, user.id, payload.conversation_id)

    language = require_supported_language(conversation.language)
    question = payload.message.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    user_message = Message(
        user_id=user.id,
        conversation_id=conversation.id,
        role="user",
        created_at=datetime.now(timezone.utc),
        content=question,
        language=language,
    )
    db.add(user_message)
    conversation.updated_at = datetime.now(timezone.utc)
    db.flush()

    # Cache lookup happens before Gemini intent classification. Only GENERAL_QUESTION
    # entries can match; action workflows are never cached or replayed.
    source = "gemini"
    similarity = None
    intent = "GENERAL_QUESTION"
    requires_confirmation = False
    previous_assistant = db.scalar(select(Message).where(
        Message.user_id == user.id, Message.conversation_id == conversation.id,
        Message.role == "assistant",
    ).order_by(Message.created_at.desc(), Message.id.desc()).limit(1))
    prior_shopping = (previous_assistant.metadata_json or {}).get("shopping") if previous_assistant else None
    shopping = None
    playback = None
    daily_actions = None
    previous_blinkit = bool(BLINKIT.search(question) and PREVIOUS_ORDER.search(question))
    shopping_active = bool(prior_shopping and not prior_shopping["done"])
    cache_allowed = not (shopping_active or previous_blinkit or is_action_request(question) or CURRENT_INFO.search(question))
    match = None
    if cache_allowed:
        try:
            with db.begin_nested():
                stage("assistant.cache.lookup")
                match = find_reusable_answer(
                    db, user_id=user.id, question=question,
                    intent="GENERAL_QUESTION", language=language,
                )
        except Exception as error:
            logger.warning("Semantic lookup failed (%s).", type(error).__name__)

    if DAILY_COMMAND.search(question):
        try:
            planned = plan_daily_command(question, language)
        except VertexUnavailable:
            raise HTTPException(status_code=503, detail="The AI service is temporarily unavailable.") from None
        except ValueError:
            raise HTTPException(status_code=502, detail="The AI could not create a valid action plan.") from None
        intent = planned.actions[0].intent if planned.actions else "DAILY_ASSISTANT"
        language = planned.language if planned.language in {"en", "hi"} else language
        response_text = planned.clarification_question or planned.response
        source = "daily_planner"
        if planned.needs_clarification:
            daily_actions = []
        else:
            daily_actions = []
            for item in planned.actions:
                row = DailyAction(
                    user_id=user.id,
                    intent=item.intent,
                    payload=item.entities,
                    status="awaiting_confirmation" if item.requires_confirmation else "planned",
                )
                db.add(row)
                db.flush()
                daily_actions.append({
                    "id": str(row.id), "intent": row.intent, "payload": row.payload,
                    "status": row.status, "requires_confirmation": item.requires_confirmation,
                })
        requires_confirmation = bool(daily_actions)
    elif previous_blinkit:
        response_text = _saved_blinkit_reply(db, user.id, language)
        source = "saved_history"
        intent = "ORDER_GROCERIES"
    elif shopping_active:
        session = _shopping_in_chat(SHOPPING_STATE.validate_python(prior_shopping["session"]))
        correction = CHANGE_ITEMS.match(question)
        if correction:
            session = replace(session, step="items", item_index=0)
        session = _shopping_in_chat(shopping_reply(session, correction.group(1) if correction else question))
        shopping = _shopping_chat_payload(session)
        if session.step == "item" and question.strip(" .!?,").casefold() in {"no", "nope", "nahi", "नहीं"}:
            shopping["response"] = (
                f"Try reopening the {session.store} link for {session.items[session.item_index]}. "
                "If it opens but the results differ, try a shorter search on the retailer. "
                "Did it work now? Say “change items to…” if you want different links."
            )
        if session.store == "Blinkit" and session.items and (
            session.store != prior_shopping["session"].get("store")
            or session.items != tuple(prior_shopping["session"]["items"])
        ):
            user_message.metadata_json = {"shopping_items": list(session.items), "shopping_store": session.store}
        response_text = shopping["response"]
        requires_confirmation = not shopping["done"]
        source = "shopping_guide"
        intent = "ORDER_GROCERIES"
    elif match is not None:
        stage("assistant.cache.hit")
        response_text = match.answer
        source = "semantic_cache"
        similarity = round(match.similarity, 4)
    else:
        try:
            now = datetime.now(timezone.utc)
            memory_rows = db.scalars(select(Memory).where(Memory.user_id == user.id, Memory.is_active.is_(True), or_(Memory.expires_at.is_(None), Memory.expires_at > now)).order_by(Memory.updated_at.desc()).limit(20))
            memory_context = "; ".join(
                f"{memory.category}/{memory.memory_key}: {memory.memory_value}"
                for memory in memory_rows
            )
            # Use only this account’s previous shopping messages as private context.
            previous_shopping = db.scalars(
                select(Message)
                .where(
                    Message.user_id == user.id,
                    Message.intent == "ORDER_GROCERIES",
                    Message.role.in_({"user", "assistant"}),
                )
                .order_by(Message.created_at.desc())
                .limit(12)
            ).all()
            shopping_context = " | ".join(
                f"{item.role}: {item.content}" for item in reversed(previous_shopping)
            )
            recent_messages = db.scalars(
                select(Message).where(
                    Message.conversation_id == conversation.id,
                    Message.user_id == user.id,
                    Message.id != user_message.id,
                    Message.role.in_({"user", "assistant"}),
                ).order_by(Message.created_at.desc(), Message.id.desc()).limit(12)
            ).all()
            context_parts = []
            if memory_context:
                context_parts.append(f"Saved user memories: {memory_context}")
            if shopping_context:
                context_parts.append(f"Recent shopping conversation history: {shopping_context}")
            if recent_messages:
                recent_context = "\n".join(
                    f"{item.role}: {item.content[:400]}" for item in reversed(recent_messages)
                )
                context_parts.insert(0, f"Conversation so far: {recent_context}")
            user_context = "\n".join(context_parts)[:6000]
            stage("assistant.vertex.start")
            classified = vertex_model(question, user_context=user_context, preferred_language=language)
        except VertexUnavailable:
            raise HTTPException(status_code=503, detail="The AI service is temporarily unavailable.") from None
        stage("assistant.vertex.complete", structured=classified is not None)
        if classified is None:
            raise HTTPException(status_code=502, detail="The AI returned no structured response.")
        intent = classified.intent
        if intent == "ORDER_GROCERIES":
            raw_items = classified.shopping_items or classified.entities.get("items")
            items = tuple(item for item in raw_items if isinstance(item, str) and item.strip()) if isinstance(raw_items, list) else ()
            session = _shopping_in_chat(start_shopping(f"{classified.application or ''} {question}", items))
            shopping = _shopping_chat_payload(session)
            if session.items:
                user_message.metadata_json = {"shopping_items": list(session.items), "shopping_store": session.store}
        language = classified.response_language if classified.response_language in {"en", "hi"} else language
        if shopping is not None:
            response_text = shopping["response"]
            requires_confirmation = not shopping["done"]
        elif intent in {"GENERAL_QUESTION", "GENERAL_CONVERSATION", "GREETING"}:
            response_text = classified.response
            requires_confirmation = False
        else:
            action = intent_action(classified)
            response_text = action.get("response") or classified.response
            if intent == "WATCH_SHOW" and action.get("playback_url"):
                playback = {"url": action["playback_url"], "platform": action["playback_platform"], "kind": action["playback_status"]}
            elif intent == "WATCH_SHOW" and action.get("playback_options"):
                playback = {"kind": "choices", "options": action["playback_options"]}
            requires_confirmation = bool(action.get("requires_confirmation", classified.requires_confirmation))

        # Cache only high-confidence, stable informational answers for this user.
        # Never cache action intents, transient results, or general conversation.
        if cache_allowed and language == conversation.language and intent == "GENERAL_QUESTION" and classified.confidence >= AUTO_CACHE_MIN_CONFIDENCE and response_text.strip():
            try:
                with db.begin_nested():
                    store_approved_answer(
                        db, user_id=user.id, question=question, answer=response_text,
                        intent=intent, language=language, quality_score=float(classified.confidence),
                        source_message_id=user_message.id,
                    )
            except Exception as error:
                logger.warning("Semantic cache write failed (%s).", type(error).__name__)

    user_message.intent = intent
    assistant_message = Message(
        user_id=user.id,
        conversation_id=conversation.id,
        role="assistant",
        created_at=datetime.now(timezone.utc),
        content=response_text,
        language=language,
        intent=intent,
        metadata_json={"source": source, "similarity": similarity, **({"shopping": shopping} if shopping is not None else {}), **({"playback": playback} if playback is not None else {}), **({"daily_actions": daily_actions} if daily_actions is not None else {})},
    )
    db.add(assistant_message)
    db.add(SearchHistory(
        user_id=user.id,
        conversation_id=conversation.id,
        query=question,
        normalized_query=normalize_question(question),
        intent=intent,
        language=language,
        result_source=source,
    ))
    conversation.updated_at = datetime.now(timezone.utc)
    db.flush()

    stage("assistant.reply.persisted", source=source)
    return AssistantChatResponse(
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        intent=intent,
        response=response_text,
        language=language,
        source=source,
        similarity=similarity,
        requires_confirmation=requires_confirmation,
        shopping=shopping,
        playback=playback,
        daily_actions=daily_actions,
    )

@router.post("/assistant/audio", response_model=AssistantChatResponse, max_body_size=MAX_AUDIO_REQUEST_BYTES)
def assistant_audio(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    conversation_id: UUID,
    audio: UploadFile = File(...),
):
    """Authenticated voice chat, using the same persistence and semantic lookup flow."""
    _chat_conversation(db, user.id, conversation_id)
    stage("assistant.audio.validating")
    try:
        validate_audio(audio.file, audio.content_type)
    except AudioStorageError as error:
        raise HTTPException(error.status, str(error)) from None

    with tempfile.TemporaryDirectory(prefix="apnasathi-chat-") as directory:
        audio_path = Path(directory) / "recording"
        with audio_path.open("wb") as target:
            shutil.copyfileobj(audio.file, target)
        try:
            from app import transcribe_audio
            transcription = transcribe_audio(audio_path, strip=True)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=503, detail="Audio transcription is temporarily unavailable.") from None

    stage("assistant.audio.transcribed", has_speech=bool(transcription))
    if len(transcription) > 4000:
        raise HTTPException(status_code=422, detail="The transcript is too long. Please record a shorter message.")
    if not transcription:
        raise HTTPException(status_code=422, detail="No speech was detected. Please try again.")
    result = assistant_chat(
        AssistantChatRequest(conversation_id=conversation_id, message=transcription),
        user,
        db,
    )
    return result.model_copy(update={"transcription": transcription})
