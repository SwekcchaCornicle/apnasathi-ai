"""Authenticated daily assistant plan, confirmation and domain endpoints."""
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from agents.daily_planner import plan_daily_command
from auth.dependencies import get_current_user
from database.daily_models import DailyAction, Reminder, DailyTask, ShoppingList, Expense, MealPlan, MessageDraft, GoogleCalendarCredential, GoogleOAuthState
from database.models import User, UserProfile
from database.session import get_db
from llm_model.llm_model import VertexUnavailable
from integrations.google_calendar import GoogleCalendarError, create_calendar_event, google_oauth_url, exchange_google_code, encrypt_refresh_token

router = APIRouter(prefix="/daily", tags=["daily-assistant"])
UserDep = Annotated[User, Depends(get_current_user)]
DbDep = Annotated[Session, Depends(get_db)]

class PlanInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    language: str = Field(default="hi", pattern="^(hi|en)$")
class ReminderInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    scheduled_at: datetime
    timezone: str = "Asia/Kolkata"
class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    priority: str = Field(default="medium", pattern="^(low|medium|high)$")
    due_at: datetime | None = None
class ShoppingInput(BaseModel):
    name: str = "My shopping list"
    items: list[str] = Field(default_factory=list, max_length=100)
class ExpenseInput(BaseModel):
    amount: float = Field(gt=0, le=100000000)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    category: str
    description: str
    spent_at: datetime
class MealInput(BaseModel):
    plan_date: datetime
    meal_type: str = Field(pattern="^(breakfast|lunch|snack|dinner)$")
    title: str
    ingredients: list[str] = Field(default_factory=list)
class DraftInput(BaseModel):
    channel: str = Field(default="whatsapp", pattern="^(whatsapp|email|sms)$")
    recipient: str | None = None
    body: str = Field(min_length=1, max_length=4000)

def owned(db, model, user_id, item_id):
    row = db.scalar(select(model).where(model.id == item_id, model.user_id == user_id))
    if row is None: raise HTTPException(404, "Resource not found.")
    return row

@router.post("/plan")
def plan(payload: PlanInput, user: UserDep, db: DbDep):
    try: result = plan_daily_command(payload.text, payload.language)
    except VertexUnavailable as exc: raise HTTPException(503, str(exc)) from None
    except ValueError as exc: raise HTTPException(502, str(exc)) from None
    if result.needs_clarification:
        return {"status":"needs_clarification","question":result.clarification_question,"response":result.response,"actions":[]}
    actions=[]
    for item in result.actions:
        row=DailyAction(user_id=user.id,intent=item.intent,payload=item.entities,
                        status="awaiting_confirmation" if item.requires_confirmation else "planned")
        db.add(row); db.flush()
        actions.append({"id":str(row.id),"intent":row.intent,"payload":row.payload,"status":row.status})
    return {"status":"awaiting_confirmation" if actions else "completed","language":result.language,
            "response":result.response,"actions":actions,"confidence":result.confidence}

@router.post("/actions/{action_id}/confirm")
def confirm(action_id: UUID, user: UserDep, db: DbDep):
    action=owned(db,DailyAction,user.id,action_id)
    if action.status!="awaiting_confirmation": raise HTTPException(409,"Action is not awaiting confirmation.")
    p=action.payload or {}; result={}
    if action.intent=="SET_REMINDER":
        if not p.get("title") or not p.get("scheduled_at"): raise HTTPException(422,"Reminder title and time are required.")
        when=datetime.fromisoformat(p["scheduled_at"].replace("Z","+00:00"))
        if when.tzinfo is None: raise HTTPException(422,"Reminder time must include timezone.")
        row=Reminder(user_id=user.id,title=p["title"],scheduled_at=when,timezone=p.get("timezone","Asia/Kolkata")); db.add(row); db.flush(); result={"reminder_id":str(row.id)}
    elif action.intent=="CREATE_TODO":
        if not p.get("title"): raise HTTPException(422,"Task title is required.")
        row=DailyTask(user_id=user.id,title=p["title"],priority=p.get("priority","medium")); db.add(row); db.flush(); result={"task_id":str(row.id)}
    elif action.intent in {"CREATE_SHOPPING_LIST","ADD_SHOPPING_ITEM"}:
        items=p.get("items") or ([p["item"]] if p.get("item") else [])
        if not items: raise HTTPException(422,"Shopping items are required.")
        row=ShoppingList(user_id=user.id,name=p.get("name","My shopping list"),items=items); db.add(row); db.flush(); result={"shopping_list_id":str(row.id)}
    elif action.intent=="TRACK_EXPENSE":
        if any(p.get(k) is None for k in ("amount","category","description","spent_at")): raise HTTPException(422,"Expense amount, category, description and date are required.")
        row=Expense(user_id=user.id,amount=p["amount"],currency=p.get("currency","INR"),category=p["category"],description=p["description"],spent_at=datetime.fromisoformat(p["spent_at"].replace("Z","+00:00"))); db.add(row); db.flush(); result={"expense_id":str(row.id)}
    elif action.intent=="PLAN_MEAL":
        if any(p.get(k) is None for k in ("plan_date","meal_type","title")): raise HTTPException(422,"Meal date, type and title are required.")
        row=MealPlan(user_id=user.id,plan_date=datetime.fromisoformat(p["plan_date"].replace("Z","+00:00")),meal_type=p["meal_type"],title=p["title"],ingredients=p.get("ingredients",[])); db.add(row); db.flush(); result={"meal_plan_id":str(row.id)}
    elif action.intent=="CREATE_CALENDAR_EVENT":
        if not all(p.get(k) for k in ("title", "start_at", "end_at", "timezone")): raise HTTPException(422,"Calendar title, start, end and timezone are required.")
        try:
            event = create_calendar_event(db, user.id, p)
        except GoogleCalendarError as exc:
            raise HTTPException(exc.status_code, str(exc)) from None
        result = {"calendar_event_id": event["id"], "html_link": event.get("htmlLink")}
    elif action.intent=="DRAFT_MESSAGE":
        if not p.get("body"): raise HTTPException(422,"Message body is required.")
        row=MessageDraft(user_id=user.id,channel=p.get("channel","whatsapp"),recipient=p.get("recipient"),body=p["body"]); db.add(row); db.flush(); result={"draft_id":str(row.id),"sent":False}
    else: raise HTTPException(422,"This intent is not an executable daily action.")
    action.status="completed"; action.result=result
    return {"id":str(action.id),"status":action.status,"result":result}

@router.post("/reminders",status_code=201)
def add_reminder(data: ReminderInput,user: UserDep,db: DbDep):
    if data.scheduled_at.tzinfo is None: raise HTTPException(422,"scheduled_at must include timezone.")
    row=Reminder(user_id=user.id,**data.model_dump()); db.add(row); db.flush()
    return {"id":str(row.id),"title":row.title,"scheduled_at":row.scheduled_at,"status":row.status}
@router.get("/reminders")
def reminders(user: UserDep,db: DbDep):
    return [{"id":str(x.id),"title":x.title,"scheduled_at":x.scheduled_at,"status":x.status} for x in db.scalars(select(Reminder).where(Reminder.user_id==user.id).order_by(Reminder.scheduled_at))]
@router.delete("/reminders/{item_id}")
def delete_reminder(item_id:UUID,user:UserDep,db:DbDep):
    row=owned(db,Reminder,user.id,item_id); row.status="cancelled"; return {"id":str(row.id),"status":row.status}
@router.post("/tasks",status_code=201)
def add_task(data:TaskInput,user:UserDep,db:DbDep):
    row=DailyTask(user_id=user.id,**data.model_dump()); db.add(row); db.flush(); return {"id":str(row.id),"title":row.title,"status":row.status}
@router.get("/tasks")
def tasks(user:UserDep,db:DbDep):
    return [{"id":str(x.id),"title":x.title,"priority":x.priority,"status":x.status,"due_at":x.due_at} for x in db.scalars(select(DailyTask).where(DailyTask.user_id==user.id))]
@router.patch("/tasks/{item_id}/complete")
def complete_task(item_id:UUID,user:UserDep,db:DbDep):
    row=owned(db,DailyTask,user.id,item_id); row.status="completed"; return {"id":str(row.id),"status":row.status}
@router.post("/shopping-lists",status_code=201)
def add_list(data:ShoppingInput,user:UserDep,db:DbDep):
    row=ShoppingList(user_id=user.id,name=data.name,items=data.items); db.add(row); db.flush(); return {"id":str(row.id),"name":row.name,"items":row.items}
@router.get("/shopping-lists")
def lists(user:UserDep,db:DbDep):
    return [{"id":str(x.id),"name":x.name,"items":x.items} for x in db.scalars(select(ShoppingList).where(ShoppingList.user_id==user.id))]
@router.post("/expenses",status_code=201)
def add_expense(data:ExpenseInput,user:UserDep,db:DbDep):
    if data.spent_at.tzinfo is None: raise HTTPException(422,"spent_at must include timezone.")
    row=Expense(user_id=user.id,**data.model_dump()); db.add(row); db.flush(); return {"id":str(row.id),"amount":row.amount,"currency":row.currency}
@router.get("/expenses/summary")
def expense_summary(user:UserDep,db:DbDep):
    rows=db.execute(select(Expense.currency,func.sum(Expense.amount),func.count(Expense.id)).where(Expense.user_id==user.id).group_by(Expense.currency)).all()
    return {"totals":[{"currency":c,"amount":float(a),"count":n} for c,a,n in rows]}
@router.post("/meals",status_code=201)
def add_meal(data:MealInput,user:UserDep,db:DbDep):
    row=MealPlan(user_id=user.id,**data.model_dump()); db.add(row); db.flush(); return {"id":str(row.id),"title":row.title,"meal_type":row.meal_type}
@router.get("/meals")
def meals(user:UserDep,db:DbDep):
    return [{"id":str(x.id),"plan_date":x.plan_date,"meal_type":x.meal_type,"title":x.title,"ingredients":x.ingredients} for x in db.scalars(select(MealPlan).where(MealPlan.user_id==user.id).order_by(MealPlan.plan_date))]
@router.post("/message-drafts",status_code=201)
def add_draft(data:DraftInput,user:UserDep,db:DbDep):
    row=MessageDraft(user_id=user.id,**data.model_dump()); db.add(row); db.flush(); return {"id":str(row.id),"channel":row.channel,"recipient":row.recipient,"body":row.body,"sent":False}
@router.get("/message-drafts")
def drafts(user:UserDep,db:DbDep):
    return [{"id":str(x.id),"channel":x.channel,"recipient":x.recipient,"body":x.body} for x in db.scalars(select(MessageDraft).where(MessageDraft.user_id==user.id).order_by(MessageDraft.created_at.desc()))]

@router.get("/google/calendar/connect")
def google_calendar_connect(user: UserDep, db: DbDep):
    import hashlib, secrets
    from datetime import timedelta
    state = secrets.token_urlsafe(32)
    db.add(GoogleOAuthState(state_hash=hashlib.sha256(state.encode()).hexdigest(), user_id=user.id,
                           expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)))
    try: url = google_oauth_url(state)
    except GoogleCalendarError as exc: raise HTTPException(exc.status_code, str(exc)) from None
    return {"authorization_url": url}

@router.get("/google/calendar/callback")
def google_calendar_callback(code: str, state: str, db: DbDep):
    import hashlib
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    row = db.scalar(select(GoogleOAuthState).where(
        GoogleOAuthState.state_hash == state_hash,
        GoogleOAuthState.expires_at > datetime.now(timezone.utc),
        GoogleOAuthState.used_at.is_(None),
    ).with_for_update())
    if row is None: raise HTTPException(400, "Google authorization state is invalid or expired.")
    try:
        token_data = exchange_google_code(code)
        refresh_token = token_data.get("refresh_token")
        if not refresh_token: raise GoogleCalendarError("Google did not return a refresh token. Reconnect and approve offline access.", 400)
        encrypted = encrypt_refresh_token(refresh_token)
    except GoogleCalendarError as exc: raise HTTPException(exc.status_code, str(exc)) from None
    credential = db.get(GoogleCalendarCredential, row.user_id)
    if credential is None:
        db.add(GoogleCalendarCredential(user_id=row.user_id, refresh_token_encrypted=encrypted))
    else: credential.refresh_token_encrypted = encrypted
    row.used_at = datetime.now(timezone.utc)
    return {"connected": True, "message": "Google Calendar connected."}

@router.get("/google/calendar/status")
def google_calendar_status(user: UserDep, db: DbDep):
    return {"connected": db.get(GoogleCalendarCredential, user.id) is not None}

class CalendarEventInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    start_at: datetime
    end_at: datetime
    timezone: str = Field(default="Asia/Kolkata", max_length=64)
    description: str | None = Field(default=None, max_length=2000)

@router.post("/calendar/events", status_code=201)
def add_calendar_event(data: CalendarEventInput, user: UserDep, db: DbDep):
    if data.start_at.tzinfo is None or data.end_at.tzinfo is None: raise HTTPException(422, "Calendar event times must include timezone offsets.")
    if data.end_at <= data.start_at: raise HTTPException(422, "Event end must be after its start.")
    try: event = create_calendar_event(db, user.id, data.model_dump())
    except GoogleCalendarError as exc: raise HTTPException(exc.status_code, str(exc)) from None
    return {"id": event["id"], "html_link": event.get("htmlLink"), "status": event.get("status")}


class WhatsAppPhoneInput(BaseModel):
    phone: str = Field(min_length=8, max_length=16, pattern=r"^\+[1-9][0-9]{7,14}$")
    opt_in: bool

@router.put("/whatsapp/phone")
def set_whatsapp_phone(data: WhatsAppPhoneInput, user: UserDep, db: DbDep):
    profile = db.get(UserProfile, user.id)
    if not data.opt_in:
        raise HTTPException(400, "Explicit WhatsApp reminder opt-in is required.")
    if profile is None:
        profile = UserProfile(user_id=user.id, whatsapp_phone=data.phone, whatsapp_opt_in=True)
        db.add(profile)
    else:
        profile.whatsapp_phone = data.phone
        profile.whatsapp_opt_in = True
    return {"configured": True, "phone": "••••" + data.phone[-4:]}

@router.delete("/whatsapp/phone")
def clear_whatsapp_phone(user: UserDep, db: DbDep):
    profile = db.get(UserProfile, user.id)
    if profile is not None:
        profile.whatsapp_phone = None
        profile.whatsapp_opt_in = False
    return {"configured": False}
