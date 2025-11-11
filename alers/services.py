"""Domain services for the A.L.E.R.S. Django implementation."""

from __future__ import annotations

from typing import Iterable

from django.conf import settings
from django.db import transaction
from django.utils import timezone

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency for tooling
    OpenAI = None

from .models import ChatSession, Dashboard, Enrollment, Message

if OpenAI and settings.OPENAI_API_KEY:
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    client_error = None
else:
    client = None
    if not OpenAI:
        client_error = "Install the openai package (pip install -r requirements.txt)."
    elif not settings.OPENAI_API_KEY:
        client_error = "Set the OPENAI_API_KEY environment variable before starting the server."
    else:
        client_error = "OpenAI client unavailable."


def build_chat_history(session: ChatSession) -> list[dict]:
    return [message.to_chat_completion() for message in session.messages.order_by("created_at")]


def stream_chat_completion(
    *,
    session: ChatSession,
    user_message: str,
    model_override: str | None = None,
) -> str:
    """Send a prompt to OpenAI and persist the assistant/user messages."""

    messages = build_chat_history(session)
    if user_message:
        messages.append({"role": Message.Role.USER, "content": user_message})

    if client is None:
        raise RuntimeError(client_error or "OpenAI client is not configured.")

    completion = client.chat.completions.create(
        model=model_override or settings.OPENAI_MODEL,
        messages=messages,
        timeout=settings.OPENAI_COMPLETION_TIMEOUT,
    )
    assistant_reply = completion.choices[0].message.content or ""

    persisted_messages: list[Message] = []
    if user_message:
        persisted_messages.append(
            Message(
                chat_session=session,
                role=Message.Role.USER,
                content=user_message,
            )
        )
    persisted_messages.append(
        Message(
            chat_session=session,
            role=Message.Role.ASSISTANT,
            content=assistant_reply,
        )
    )
    session.add_messages(persisted_messages)
    return assistant_reply


def update_dashboard(enrollment: Enrollment) -> Dashboard:
    dashboard, _ = Dashboard.objects.get_or_create(
        student=enrollment.user.full_name,
        course=enrollment.course.name,
        defaults={
            "creator": enrollment.user.full_name,
            "course_started": enrollment.starting_date,
        },
    )
    now = timezone.now()
    dashboard.student_last_login = now

    durations: list[float] = []
    for chat in enrollment.chat_sessions.exclude(end__isnull=True):
        durations.append((chat.end - chat.start).total_seconds() / 60)
    if durations:
        dashboard.mean_session_minutes = sum(durations) / len(durations)
    dashboard.save()
    return dashboard


def record_chat_activity(enrollment: Enrollment, session: ChatSession) -> None:
    with transaction.atomic():
        enrollment.last_login = timezone.now()
        enrollment.save(update_fields=["last_login"])
        update_dashboard(enrollment)
