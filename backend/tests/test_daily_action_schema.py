from pydantic import ValidationError
import pytest

from llm_model.daily_action_schema import DailyActionPlan
from api.daily_assistant import WhatsAppPhoneInput

def test_planner_accepts_multiple_hindi_daily_actions():
    plan = DailyActionPlan.model_validate({
        "language": "hi",
        "response": "दो काम तैयार हैं।",
        "actions": [
            {"intent": "SET_REMINDER", "entities": {"title": "दवा", "scheduled_at": "2026-11-29T09:00:00+05:30"}},
            {"intent": "CREATE_CALENDAR_EVENT", "entities": {
                "title": "Team meeting",
                "start_at": "2026-11-29T11:00:00+05:30",
                "end_at": "2026-11-29T11:30:00+05:30",
                "timezone": "Asia/Kolkata",
            }},
        ],
        "needs_clarification": False,
        "confidence": 0.95,
    })
    assert len(plan.actions) == 2
    assert plan.actions[1].intent == "CREATE_CALENDAR_EVENT"

def test_planner_can_ask_for_missing_time():
    plan = DailyActionPlan.model_validate({
        "language": "hi",
        "response": "किस समय याद दिलाऊँ?",
        "actions": [],
        "needs_clarification": True,
        "clarification_question": "किस समय?",
        "confidence": 0.6,
    })
    assert plan.needs_clarification
    assert not plan.actions

def test_whatsapp_number_requires_explicit_opt_in():
    data = WhatsAppPhoneInput(phone="+919876543210", opt_in=True)
    assert data.opt_in is True

def test_whatsapp_number_must_be_e164():
    with pytest.raises(ValidationError):
        WhatsAppPhoneInput(phone="9876543210", opt_in=True)
