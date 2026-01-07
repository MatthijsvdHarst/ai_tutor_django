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

from .models import (
    ChatSession,
    Dashboard,
    Enrollment,
    EnrollmentSummary,
    Message,
    ProfileChatSession,
    ProfileMessage,
    StudentProfile,
)

SYSTEM_INSTRUCTIONS = (
    "Rol en doel\n"
    "Je bent een digitale studie-assistent voor het vak Embedded Systems. "
    "Je helpt NSE-studenten bij het begrijpen en studeren van de stof uit:\n"
    "“Dictaat Embedded Systems, versie 1.1, R.A. van Neijhof, oktober 2018”\n"
    "Alle antwoorden moeten binnen de grenzen van dit dictaat blijven.\n"
    "1. Scope van de inhoud\n"
    "Baseer je uitleg uitsluitend op de onderwerpen zoals behandeld in het dictaat, waaronder:\n"
    "H1: Inleiding & algemene kenmerken van embedded systems\n"
    "H2: Talstelsels (decimaal, binair, octaal, hexadecimaal, omrekenen, shortcuts)\n"
    "H3: Toepassingen van talstelsels (FLAGS-register, IPv4/IPv6, chmod, MAC-adressen, RGB, etc.)\n"
    "H4: Negatieve getallen (unsigned, signed magnitude, 1’s complement, 2’s complement, bias)\n"
    "H5: Integer berekeningen en hardware\n"
    "H6: Gebroken getallen (binaire punt, fixed point representatie, problemen)\n"
    "H7: Digitale poorten (AND, OR, NOT, EXOR, NAND, NOR, EXNOR, De Morgan, universele bouwstenen)\n"
    "H8: Combinatorische schakelingen (analyse, synthese, minimalisatie)\n"
    "H9: Microcontrollers programmeren (hardware registers, bit-manipulaties zoals shifting, OR, AND, XOR, clearing bits)\n"
    "Gebruik geen externe bronnen of extra theorie buiten wat in het dictaat logisch voortvloeit.\n"
    "Algemeen rekenwerk en basiswiskunde (zoals 2 + 2, machtsverheffen, basislogica) mag je wel gebruiken.\n"
    "Als een student een vraag stelt over een onderwerp dat niet of onvoldoende in het dictaat voorkomt:\n"
    "Zeg expliciet dat dit buiten de stof van het dictaat valt.\n"
    "Geef hoogstens een korte, globale uitleg (of verwijs de student naar andere literatuur), maar ga er niet diep op in.\n"
    "2. Doelgroep en taal\n"
    "Doelgroep: NSE-studenten (hbo-niveau) die dit vak volgen.\n"
    "Taal:\n"
    "Als de vraag in het Nederlands is, antwoord in het Nederlands.\n"
    "Als de vraag in het Engels is, mag je in het Engels antwoorden.\n"
    "Schrijf helder en gestructureerd, met zo min mogelijk jargon óf leg jargon direct uit.\n"
    "3. Wat je wél moet doen\n"
    "Je primaire taak is om studenten te helpen begrijpen en oefenen. Je doet o.a.:\n"
    "Uitleg geven\n"
    "Leg begrippen uit, zoals:\n"
    "Embedded system, sensoren, actuatoren, CPU, talstelsels, 2’s complement, digitale poorten, "
    "combinatorische schakelingen, fixed point, bit-shifts, etc.\n"
    "Gebruik concrete voorbeelden en, waar nuttig, korte vergelijkingen uit het dictaat (zoals kruisjes tellen bij talstelsels, FLAGS-register, IPv4-voorbeelden, chmod-rechten).\n"
    "Stap-voor-stap rekenen en redeneren\n"
    "Laat tussenstappen zien bij:\n"
    "Omrekenen tussen talstelsels (somregel, Euclidische deling, shortcuts).\n"
    "Omzetten van binaire codes naar decimale waarden voor verschillende integer-representaties.\n"
    "Analyseren van logische schakelingen (waarheidstabellen, vereenvoudiging, De Morgan).\n"
    "Maak de stappen duidelijk maar niet onnodig lang.\n"
    "Oefenen en toetsen van begrip\n"
    "Genereer extra oefenvragen in dezelfde stijl als in het dictaat (niveau en type vergelijkbaar).\n"
    "Vraag de student af en toe:\n"
    "“Waar loop je precies op vast?”\n"
    "“Wil je eerst een hint of meteen een volledige uitwerking?”\n"
    "Geef feedback op hun uitwerkingen en wijs netjes aan waar fouten zitten.\n"
    "Helpen bij opdrachten uit het dictaat\n"
    "Als de student een concrete opdracht uit het dictaat geeft:\n"
    "Help met hints, deelstappen en uitleg van de methode.\n"
    "Geef niet meteen het volledige eindantwoord, tenzij:\n"
    "De student expliciet zegt dat hij/zij alleen wil controleren, of\n"
    "De opdracht al stap voor stap door de student is geprobeerd.\n"
    "4. Wat je níet moet doen\n"
    "Geen volledig nieuwe theorie introduceren die niet in het dictaat aan bod komt.\n"
    "Geen lange uitweidingen over:\n"
    "Geavanceerde elektronica,\n"
    "Gevorderde microcontroller-architecturen,\n"
    "Besturingssystemen, AI, machine learning, etc., tenzij het een zeer korte context is en duidelijk wordt gezegd dat dit niet tot de dictaatstof behoort.\n"
    "Geen examenopgaven “verraden” als de student aangeeft dat het om een officiële toets gaat:\n"
    "Geef dan liever hints, tussenstappen en controle van hun redenering.\n"
    "5. Stijl en vorm\n"
    "Wees vriendelijk, geduldig en motiverend.\n"
    "Structureer je antwoorden met:\n"
    "Korte paragrafen,\n"
    "Lijsten en tabellen waar dat helpt,\n"
    "Duidelijke notatie voor talstelsels, bijvoorbeeld:\n"
    "1011₂, 47₁₀, 0x2A, 075₈.\n"
    "Bij berekeningen:\n"
    "Geef de belangrijkste tussenstappen en een korte samenvatting van de uitkomst.\n"
    "Als je een formule gebruikt, schrijf die leesbaar in gewone tekst of eenvoudige wiskunde-notatie, bijvoorbeeld:\n"
    "x = 1 × 10^3 + 4 × 10^2 + 3 × 10^1 + 2 × 10^0.\n"
    "6. Omgaan met onzekerheid\n"
    "Als informatie niet in het dictaat staat of onduidelijk is:\n"
    "Zeg eerlijk dat je het op basis van het dictaat niet zeker weet.\n"
    "Bedenk geen feiten of voorbeelden die niet duidelijk uit de dictaatstof volgen.\n"
    "Als een student een fout beeld heeft van de stof:\n"
    "Corrigeer dat rustig en verwijs zo mogelijk naar het relevante hoofdstuk of paragraaf (bijv. “Zie H2.7 over omrekenen tussen talstelsels.”).\n"
    "7. Samenvatting van je missie\n"
    "Je bent een strikt op het dictaat gebaseerde studie-assistent Embedded Systems. "
    "Je helpt studenten de theorie en voorbeelden uit het dictaat te begrijpen, te oefenen en toe te passen, "
    "zonder buiten de kaders van de dictaatstof te gaan. Geef duidelijke, gestructureerde uitleg en begeleid de student stap voor stap, "
    "zodat hij/zij zelf leert en inzicht opbouwt.\n"
)

SUMMARY_BATCH_SIZE = 5
RECENT_VISIBLE_LIMIT = 8

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


def build_responses_input(session: ChatSession, user_message: str | None):
    history = build_chat_history(session)
    input_items: list[dict] = []

    for m in history:
        role = m["role"]
        text = m["content"]

        # Zorg dat de role altijd een string is
        if hasattr(role, "value"):  # bijv. Enum
            role = role.value

        # User / system / developer → input_text
        if role in ("user", "system", "developer"):
            input_items.append({
                "role": role,
                "content": [
                    {
                        "type": "input_text",
                        "text": text,
                    }
                ],
            })
        # Assistant-berichten → output_text (dit is precies waar jouw error vandaan kwam)
        elif role == "assistant":
            input_items.append({
                "type": "message",  # expliciet, mag ook weggelaten worden maar dit is duidelijk
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": text,
                    }
                ],
                # status laten we weg; is optioneel
            })
        else:
            # Onbekende role? Dan kun je óf skippen, óf dit loggen.
            print("Onbekende role in history:", role)

    # Nieuw user-bericht aan het einde toevoegen
    if user_message:
        input_items.append({
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": user_message,
                }
            ],
        })

    return input_items


def _persist_assistant_reply(session: ChatSession, user_message: str, assistant_reply: str):
    """Save the user/assistant messages and update learning progress."""
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

    try:
        progress_summary = summarize_course_progress(session)
        profile = get_or_create_student_profile(session.enrollment.user)
        progress = profile.learning_progress or {}
        progress[str(session.enrollment.course_id)] = {
            "course": session.enrollment.course.name,
            "summary": progress_summary,
            "updated_at": timezone.now().isoformat(),
        }
        profile.learning_progress = progress
        profile.save(update_fields=["learning_progress", "updated_at"])
    except RuntimeError:
        pass
    except Exception as exc:
        print("Updating learning_progress failed:", repr(exc))


def _build_chat_messages(session: ChatSession, user_message: str) -> list[dict]:
    history = build_chat_history(session)
    messages: list[dict] = [{"role": "system", "content": SYSTEM_INSTRUCTIONS}]
    messages.extend(history)
    if user_message:
        messages.append({"role": "user", "content": user_message})
    return messages


def _get_or_create_enrollment_summary(session: ChatSession) -> EnrollmentSummary:
    summary, _ = EnrollmentSummary.objects.get_or_create(enrollment=session.enrollment)
    return summary


def _build_compact_chat_messages(session: ChatSession, user_message: str | None) -> list[dict]:
    messages: list[dict] = [{"role": "system", "content": SYSTEM_INSTRUCTIONS}]

    system_history = session.messages.filter(role=Message.Role.SYSTEM).order_by("created_at")
    messages.extend(message.to_chat_completion() for message in system_history)

    summary = getattr(session.enrollment, "summary", None)
    if summary and summary.summary:
        messages.append(
            {
                "role": "system",
                "content": f"Gespreks-samenvatting (tot nu toe):\n{summary.summary}",
            }
        )

    visible_history = session.messages.filter(is_visible=True).exclude(role=Message.Role.SYSTEM).order_by("created_at")
    if RECENT_VISIBLE_LIMIT:
        recent = list(visible_history.order_by("-created_at")[:RECENT_VISIBLE_LIMIT])
        recent.reverse()
    else:
        recent = list(visible_history)
    messages.extend(message.to_chat_completion() for message in recent)

    if user_message:
        messages.append({"role": "user", "content": user_message})
    return messages


def _update_enrollment_summary_if_needed(session: ChatSession) -> None:
    if client is None:
        return

    summary = _get_or_create_enrollment_summary(session)
    visible_messages = Message.objects.filter(
        chat_session__enrollment=session.enrollment,
        is_visible=True,
    ).exclude(role=Message.Role.SYSTEM).order_by("id")
    if summary.last_summarized_message_id:
        visible_messages = visible_messages.filter(id__gt=summary.last_summarized_message_id)

    new_messages = list(visible_messages)
    if len(new_messages) < SUMMARY_BATCH_SIZE:
        return

    lines: list[str] = []
    for message in new_messages:
        content = (message.content or "").strip()
        if not content:
            continue
        lines.append(f"{message.role}: {content}")
    if not lines:
        return

    prompt = (
        "Je werkt een lopende samenvatting bij van wat de student al weet en heeft geoefend. "
        "Houd het kort en bruikbaar (5-10 bullets). "
        "Focus op: behandelde onderwerpen, begrip, fouten, open vragen, en de volgende stap. "
        "Schrijf in het Nederlands."
    )
    current_summary = summary.summary.strip() if summary.summary else "(nog leeg)"
    user_content = (
        "Bestaande samenvatting:\n"
        f"{current_summary}\n\n"
        "Nieuwe berichten:\n"
        f"{chr(10).join(lines)}"
    )
    model_name = getattr(settings, "OPENAI_MODEL", None) or "gpt-4o-mini"

    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.4,
        max_tokens=300,
        top_p=1,
    )
    summary_text = completion.choices[0].message.content or ""
    summary.summary = summary_text.strip()
    summary.last_summarized_message_id = new_messages[-1].id
    summary.save(update_fields=["summary", "last_summarized_message_id", "updated_at"])


def stream_chat_completion(
        *,
        session: ChatSession,
        user_message: str,
        model_override: str | None = None,
) -> Iterable[str]:
    """
    Stream tokens from OpenAI while persisting the final reply.

    Yields each text delta; when the stream finishes the messages are stored
    and the learning progress is refreshed.
    """
    if client is None:
        raise RuntimeError(client_error or "OpenAI client is not configured.")

    collected: list[str] = []
    model_name = model_override or getattr(settings, "OPENAI_MODEL", None) or "gpt-4o-mini"

    try:
        stream = client.chat.completions.create(
            model=model_name,
            messages=_build_compact_chat_messages(session, user_message),
            temperature=1,
            max_tokens=4048,
            top_p=1,
            stream=True,
        )
        for chunk in stream:
            for choice in getattr(chunk, "choices", []) or []:
                delta_parts = getattr(choice.delta, "content", None) or []
                text_piece = ""
                for part in delta_parts:
                    if isinstance(part, str):
                        text_piece += part
                    else:
                        text_piece += getattr(part, "text", "") or part.get("text", "") if isinstance(part, dict) else ""
                if text_piece:
                    collected.append(text_piece)
                    yield text_piece
    except Exception as exc:
        print("OpenAI stream error:", repr(exc))
        raise

    assistant_reply = "".join(collected)
    _persist_assistant_reply(session, user_message, assistant_reply)
    _update_enrollment_summary_if_needed(session)

    return


def complete_chat_once(
        *,
        session: ChatSession,
        user_message: str,
        model_override: str | None = None,
) -> str:
    """Blocking helper that streams then returns the full reply text."""
    parts: list[str] = []
    for chunk in stream_chat_completion(
            session=session,
            user_message=user_message,
            model_override=model_override,
    ):
        parts.append(chunk)
    return "".join(parts)


def get_or_create_student_profile(user) -> StudentProfile:
    profile, _ = StudentProfile.objects.get_or_create(user=user)
    return profile


def build_profile_chat_history(session: ProfileChatSession) -> list[dict]:
    return [message.to_chat_completion() for message in session.messages.order_by("created_at")]


def _build_profile_messages(session: ProfileChatSession, user_message: str) -> list[dict]:
    history = build_profile_chat_history(session)
    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "Je bent een intake-assistent. Je enige taak is om een leerprofiel op te bouwen door gerichte vragen te stellen. "
                "Vraag naar hobby's, voorkeursmanier van uitleg (kort/snappy of uitgebreid/stap-voor-stap), "
                "taalvoorkeur en naar welke doelen de student wil toewerken. "
                "Houd de toon vriendelijk, kort en in het Nederlands tenzij de student anders kiest. "
                "Geef na elk student-antwoord een beknopte vervolgvraag of erkenning, maar bewaar de uiteindelijke samenvatting voor later.\n\n"
                "BELANGRIJK - Je mag NIET onderwijzen of educatieve vragen beantwoorden:\n"
                "- Geef GEEN uitleg over cursusstof, theorie, of technische onderwerpen\n"
                "- Beantwoord GEEN vragen over hoe iets werkt, berekeningen, of concepten\n"
                "- Los GEEN opdrachten of oefeningen op\n"
                "- Geef GEEN voorbeelden van cursusmateriaal\n\n"
                "Als de student een educatieve vraag stelt of om uitleg vraagt:\n"
                "- Vriendelijk maar duidelijk zeggen dat je hier alleen bent voor de intake\n"
                "- Verwijs de student naar de cursus-chats waar de AI-instructeur kan helpen\n"
                "- Ga daarna terug naar het stellen van intake-vragen\n\n"
                "Blijf gefocust op het verzamelen van profielinformatie. Als de student afdwaalt, leid het gesprek vriendelijk terug naar intake-vragen."
            ),
        }
    ]
    messages.extend(history)
    if user_message:
        messages.append({"role": "user", "content": user_message})
    return messages


def _persist_profile_reply(session: ProfileChatSession, user_message: str, assistant_reply: str):
    persisted: list[ProfileMessage] = []
    if user_message:
        persisted.append(
            ProfileMessage(
                session=session,
                role=ProfileMessage.Role.USER,
                content=user_message,
            )
        )
    persisted.append(
        ProfileMessage(
            session=session,
            role=ProfileMessage.Role.ASSISTANT,
            content=assistant_reply,
        )
    )
    session.add_messages(persisted)


def stream_profile_chat_completion(*, session: ProfileChatSession, user_message: str) -> str:
    """Chat with the intake assistant to gather learner preferences."""
    if client is None:
        raise RuntimeError(client_error or "OpenAI client is not configured.")

    collected: list[str] = []
    model_name = getattr(settings, "OPENAI_MODEL", None) or "gpt-4o-mini"

    try:
        stream = client.chat.completions.create(
            model=model_name,
            messages=_build_profile_messages(session, user_message),
            temperature=0.7,
            max_tokens=600,
            top_p=1,
            stream=True,
        )
        for chunk in stream:
            for choice in getattr(chunk, "choices", []) or []:
                delta_parts = getattr(choice.delta, "content", None) or []
                text_piece = ""
                for part in delta_parts:
                    if isinstance(part, str):
                        text_piece += part
                    else:
                        text_piece += getattr(part, "text", "") or part.get("text", "") if isinstance(part, dict) else ""
                if text_piece:
                    collected.append(text_piece)
                    yield text_piece
    except Exception as exc:
        print("OpenAI error (profile chat):", repr(exc))
        raise

    assistant_reply = "".join(collected)
    _persist_profile_reply(session, user_message, assistant_reply)
    return


def complete_profile_chat_once(*, session: ProfileChatSession, user_message: str) -> str:
    """Blocking helper for profile chat streaming."""
    parts: list[str] = []
    for chunk in stream_profile_chat_completion(session=session, user_message=user_message):
        parts.append(chunk)
    return "".join(parts)


def generate_initial_chat_greeting(session: ChatSession) -> str:
    """Generate an initial greeting message for a new chat session."""
    if client is None:
        raise RuntimeError(client_error or "OpenAI client is not configured.")

    model_name = getattr(settings, "OPENAI_MODEL", None) or "gpt-4o-mini"
    course = session.enrollment.course
    
    try:
        messages = _build_chat_messages(session, user_message=None)
        # Add a prompt to generate a greeting
        messages.append({
            "role": "user",
            "content": "Start de sessie met een vriendelijke begroeting en vraag hoe ik je vandaag kan helpen met de cursus."
        })
        
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.8,
            max_tokens=200,
            top_p=1,
        )
        return completion.choices[0].message.content
    except Exception as exc:
        print(f"Error generating initial chat greeting: {exc}")
        # Return a fallback greeting
        return f"Hallo! Welkom bij {course.name}. Hoe kan ik je vandaag helpen met de cursus?"


def generate_initial_profile_greeting(session: ProfileChatSession) -> str:
    """Generate an initial greeting message for a new profile chat session."""
    if client is None:
        raise RuntimeError(client_error or "OpenAI client is not configured.")

    model_name = getattr(settings, "OPENAI_MODEL", None) or "gpt-4o-mini"
    
    try:
        messages = _build_profile_messages(session, user_message=None)
        # Add a prompt to generate a greeting
        messages.append({
            "role": "user",
            "content": (
                "Start de intake met een vriendelijke begroeting. "
                "Leg kort uit dat je hier bent om het leerprofiel op te bouwen door vragen te stellen over voorkeuren en doelen. "
                "Stel daarna de eerste vraag om het leerprofiel op te bouwen. "
                "Verwijs niet naar het beantwoorden van educatieve vragen - die zijn voor de cursus-chats."
            )
        })
        
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.7,
            max_tokens=150,
            top_p=1,
        )
        return completion.choices[0].message.content
    except Exception as exc:
        print(f"Error generating initial profile greeting: {exc}")
        # Return a fallback greeting
        return "Hallo! Welkom bij de intake. Laten we beginnen met het opbouwen van je leerprofiel. Wat zijn je belangrijkste hobby's of interesses?"


def summarize_profile_chat(session: ProfileChatSession) -> str:
    """Summarize the intake conversation for later course personalization."""
    if client is None:
        raise RuntimeError(client_error or "OpenAI client is not configured.")

    history = build_responses_input(session, user_message=None)
    try:
        completion = client.responses.create(
            model=settings.OPENAI_MODEL,
            instructions=(
                "Vat de intake samen in maximaal 8 bullets. "
                "Gebruik het formaat: '• **Label:** antwoord' waarbij het label in bold is en het antwoord normaal. "
                "Vermeld: belangrijkste hobby's/interesses, taal- of uitlegvoorkeur (kort vs. uitgebreid), "
                "voorkeursleerwijze (voorbeelden, stappenplan), en doelen/ambities. "
                "Gebruik bondige Nederlandse zinnen en benoem concrete voorkeuren die relevant zijn voor latere lessen. "
                "Eindig direct na de laatste bullet; voeg geen vragen, uitnodigingen of conversatie-elementen toe. "
                "Zorg dat elke bullet direct de informatie bevat, geen lege labels."
            ),
            input=history,
            text={"format": {"type": "text"}},
            temperature=0.5,
            max_output_tokens=300,
            top_p=1,
        )
    except Exception as exc:
        print("OpenAI error (profile summary):", repr(exc))
        raise

    try:
        summary = completion.output[0].content[0].text
    except Exception:
        summary = getattr(completion, "output_text", "") or ""
    
    # Remove common conversational endings that shouldn't be in a summary
    endings_to_remove = [
        "Als je meer wilt bespreken",
        "Als je vragen hebt",
        "Laat het me weten",
        "Laat het me weten als",
        "Als je specifieke vragen hebt",
        "Als je meer wilt bespreken of specifieke vragen hebt",
    ]
    for ending in endings_to_remove:
        # Remove the ending phrase and everything after it
        idx = summary.find(ending)
        if idx != -1:
            summary = summary[:idx].strip()
            # Also remove any trailing punctuation that might be left
            summary = summary.rstrip(".,;:")
            break
    
    return summary


def summarize_course_progress(session: ChatSession) -> str:
    """Summarize a chat session to capture where the student is in the course."""
    if client is None:
        raise RuntimeError(client_error or "OpenAI client is not configured.")

    history = build_chat_history(session)
    course = session.enrollment.course
    try:
        completion = client.responses.create(
            model=settings.OPENAI_MODEL,
            instructions=(
                "Vat dit gesprek kort samen zodat een volgende sessie kan doorgaan waar deze stopte. "
                "Noem 3-6 bullets: huidige onderwerp, behaalde specificaties/leerdoelen, open vragen of fouten, "
                "volgende logische stap. Gebruik bondig Nederlands."
            ),
            input=history,
            text={"format": {"type": "text"}},
            temperature=0.4,
            max_output_tokens=250,
            top_p=1,
        )
    except Exception as exc:
        print("OpenAI error (course progress):", repr(exc))
        raise

    try:
        return completion.output[0].content[0].text
    except Exception:
        return getattr(completion, "output_text", "") or ""


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
