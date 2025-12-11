from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count, Max, Min
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import ListView, TemplateView

from .forms import ChatMessageForm, ProfileChatMessageForm, RegistrationForm
from .models import (
    Actor,
    Course,
    Dashboard,
    Enrollment,
    LoginEvent,
    ProfileChatSession,
    ProfileMessage,
    Role,
    User,
)
from . import services


def _redirect_if_profile_incomplete(request):
    """
    Redirect authenticated non-admin users to the profile chat until it is completed.
    """
    if not request.user.is_authenticated:
        return None

    # Allow superusers/admins to skip gating
    if request.user.is_superuser or request.user.has_role(Role.RoleEnum.ADMIN):
        return None

    profile = services.get_or_create_student_profile(request.user)
    profile_chat_path = reverse("profile-chat")
    if not profile.is_completed and request.path != profile_chat_path:
        messages.info(request, "Rond eerst je intake-chat af om je leerprofiel op te bouwen.")
        return redirect("profile-chat")
    return None


class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["persona_count"] = Actor.objects.count()
        context["course_count"] = Course.objects.count()

        return context


class UserLoginView(LoginView):
    template_name = "registration/login.html"


class UserLogoutView(LogoutView):
    next_page = reverse_lazy("home")
    template_name = "registration/logged_out.html"


def logout_view(request):
    """
    Explicit logout handler that shows a confirmation page with a login link.
    """
    logout(request)
    return render(request, "registration/logged_out.html")


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            services.get_or_create_student_profile(user)
            login(request, user)
            messages.success(request, "Account created successfully")
            return redirect("profile-chat")
    else:
        form = RegistrationForm()

    return render(request, "registration/register.html", {"form": form})


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        redirect_response = _redirect_if_profile_incomplete(request)
        if redirect_response:
            return redirect_response
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["enrollments"] = self.request.user.enrollments.select_related("course")
        context["dashboards"] = Dashboard.objects.filter(student=self.request.user.full_name)
        return context


class CourseListView(LoginRequiredMixin, ListView):
    model = Course
    template_name = "courses/list.html"
    context_object_name = "courses"

    def dispatch(self, request, *args, **kwargs):
        redirect_response = _redirect_if_profile_incomplete(request)
        if redirect_response:
            return redirect_response
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Course.objects.prefetch_related("learning_goals")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["enrolled_ids"] = set(self.request.user.enrollments.values_list("course_id", flat=True))
        return context


@login_required
def enroll(request, pk: int):
    redirect_response = _redirect_if_profile_incomplete(request)
    if redirect_response:
        return redirect_response

    course = get_object_or_404(Course, pk=pk)
    enrollment, created = Enrollment.objects.get_or_create(user=request.user, course=course)
    if created:
        messages.success(request, f"Enrolled in {course.name}")
    else:
        messages.info(request, f"You are already enrolled in {course.name}")
    return redirect("courses")


@login_required
def chat_session(request, pk: int):
    redirect_response = _redirect_if_profile_incomplete(request)
    if redirect_response:
        return redirect_response

    enrollment = get_object_or_404(Enrollment, course_id=pk, user=request.user)
    enrollment.last_login = timezone.now()
    enrollment.save(update_fields=["last_login"])

    session = enrollment.get_newest_chat_session()
    if session is None:
        session = enrollment.create_new_session()

    if request.method == "POST":
        form = ChatMessageForm(request.POST)
        if form.is_valid():
            model_override = form.cleaned_data["model_override"]
            if model_override and not (
                request.user.has_role(Role.RoleEnum.GPT4_PRIVILEGED)
                or request.user.has_role(Role.RoleEnum.ADMIN)
            ):
                messages.error(request, "GPT-4 access requires an elevated role.")
                return redirect("chat-session", pk=pk)

            try:
                services.complete_chat_once(
                    session=session,
                    user_message=form.cleaned_data["message"],
                    model_override=model_override,
                )
                services.record_chat_activity(enrollment, session)
            except RuntimeError as exc:
                messages.error(request, str(exc))
                return redirect("chat-session", pk=pk)
            except Exception:
                messages.error(request, "Chat service is currently unavailable. Please try again.")
                return redirect("chat-session", pk=pk)

            messages.success(request, "Assistant replied successfully")
            return redirect("chat-session", pk=pk)
    else:
        form = ChatMessageForm()

    return render(
        request,
        "chat/session.html",
        {
            "session": session,
            "messages": session.messages.filter(is_visible=True).order_by("created_at"),
            "form": form,
            "course": enrollment.course,
        },
    )


@login_required
def teacher_dashboard(request):
    redirect_response = _redirect_if_profile_incomplete(request)
    if redirect_response:
        return redirect_response

    if not (request.user.has_role(Role.RoleEnum.TEACHER) or request.user.has_role(Role.RoleEnum.ADMIN)):
        messages.error(request, "Teacher privileges required")
        return redirect("dashboard")

    dashboards = Dashboard.objects.all().order_by("student")
    return render(
        request,
        "teacher/dashboard.html",
        {"dashboards": dashboards},
    )


@login_required
def admin_user_management(request):
    redirect_response = _redirect_if_profile_incomplete(request)
    if redirect_response:
        return redirect_response

    if not request.user.has_role(Role.RoleEnum.ADMIN):
        messages.error(request, "Admin privileges required")
        return redirect("dashboard")

    if request.method == "POST":
        email = request.POST.get("email")
        selected_roles = request.POST.getlist("roles")
        user = get_object_or_404(User, email=email)
        user.roles.set(Role.objects.filter(name__in=selected_roles))
        messages.success(request, f"Updated roles for {user.full_name}")
        return redirect("admin-user-management")

    return render(
        request,
        "admin/user_management.html",
        {
            "roles": Role.objects.all(),
            "users": User.objects.all().select_related(),
        },
    )


@login_required
def admin_login_activity(request):
    redirect_response = _redirect_if_profile_incomplete(request)
    if redirect_response:
        return redirect_response

    if not request.user.has_role(Role.RoleEnum.ADMIN):
        messages.error(request, "Admin privileges required")
        return redirect("dashboard")

    login_stats_query = (
        LoginEvent.objects.values(
            "user__id",
            "user__username",
            "user__email",
            "user__first_name",
            "user__last_name",
        )
        .annotate(
            total=Count("id"),
            last_seen=Max("logged_in_at"),
            first_seen=Min("logged_in_at"),
        )
        .order_by("-last_seen")
    )

    login_stats = []
    for stat in login_stats_query:
        first = stat.get("first_seen")
        last = stat.get("last_seen")
        if first and last:
            stat["active_minutes"] = int((last - first).total_seconds() / 60)
        else:
            stat["active_minutes"] = None
        login_stats.append(stat)

    return render(
        request,
        "admin/login_activity.html",
        {"login_stats": login_stats},
    )


@login_required
@require_POST
def chat_session_stream(request, pk: int):
    redirect_response = _redirect_if_profile_incomplete(request)
    if redirect_response:
        return redirect_response

    enrollment = get_object_or_404(Enrollment, course_id=pk, user=request.user)
    enrollment.last_login = timezone.now()
    enrollment.save(update_fields=["last_login"])

    session = enrollment.get_newest_chat_session()
    if session is None:
        session = enrollment.create_new_session()

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    form = ChatMessageForm(payload)
    if not form.is_valid():
        return JsonResponse({"error": "Ongeldig verzoek", "details": form.errors}, status=400)

    model_override = form.cleaned_data["model_override"]
    if model_override and not (
        request.user.has_role(Role.RoleEnum.GPT4_PRIVILEGED)
        or request.user.has_role(Role.RoleEnum.ADMIN)
    ):
        return JsonResponse({"error": "GPT-4 toegang is niet toegestaan voor dit account."}, status=403)

    def event_stream():
        def _sse(data: dict):
            return f"data: {json.dumps(data)}\n\n"

        yield _sse({"type": "status", "message": "started"})
        try:
            for delta in services.stream_chat_completion(
                    session=session,
                    user_message=form.cleaned_data["message"],
                    model_override=model_override,
            ):
                if delta:
                    yield _sse({"type": "token", "text": delta})
            services.record_chat_activity(enrollment, session)
            yield _sse({"type": "done"})
        except RuntimeError as exc:
            # Config/runtime issues we cannot recover from
            yield _sse({"type": "error", "message": str(exc)})
        except Exception as exc:
            # Fallback: try non-streaming to still serve a reply
            try:
                text = services.complete_chat_once(
                    session=session,
                    user_message=form.cleaned_data["message"],
                    model_override=model_override,
                )
                services.record_chat_activity(enrollment, session)
                yield _sse({"type": "token", "text": text})
                yield _sse({"type": "done"})
            except Exception as exc2:
                print("Streaming + fallback error:", repr(exc), repr(exc2))
                yield _sse({"type": "error", "message": "Chat service is currently unavailable."})

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    return response


@login_required
def profile_chat(request):
    profile = services.get_or_create_student_profile(request.user)
    if profile.is_completed:
        messages.info(request, "Je intake-profiel is al afgerond.")
        return redirect("profile-detail")

    session = (
        ProfileChatSession.objects.filter(user=request.user, end__isnull=True)
        .order_by("-start")
        .first()
    )
    if session is None:
        session = ProfileChatSession.objects.create(user=request.user)

    if request.method == "POST":
        if request.POST.get("action") == "finish":
            user_message_count = session.messages.filter(role=ProfileMessage.Role.USER).count()
            if user_message_count < 6:
                messages.error(request, "Beantwoord minimaal 6 vragen voordat je opslaat.")
                return redirect("profile-chat")

            try:
                summary_text = services.summarize_profile_chat(session)
            except RuntimeError as exc:
                messages.error(request, str(exc))
                return redirect("profile-chat")
            except Exception:
                messages.error(request, "Samenvatten is nu niet mogelijk. Probeer het opnieuw.")
                return redirect("profile-chat")
            profile.mark_completed(summary_text)
            session.end_session()
            messages.success(request, "Je profiel is opgeslagen. Je kunt nu verder met het platform.")
            return redirect("dashboard")

        form = ProfileChatMessageForm(request.POST)
        if form.is_valid():
            try:
                services.complete_profile_chat_once(session=session, user_message=form.cleaned_data["message"])
            except RuntimeError as exc:
                messages.error(request, str(exc))
                return redirect("profile-chat")
            except Exception:
                messages.error(request, "Profiel assistent is tijdelijk niet beschikbaar. Probeer opnieuw.")
                return redirect("profile-chat")
            messages.success(request, "Bericht verstuurd")
            return redirect("profile-chat")
    else:
        form = ProfileChatMessageForm()

    user_message_count = session.messages.filter(role=ProfileMessage.Role.USER).count()

    return render(
        request,
        "profile/chat.html",
        {
            "session": session,
            "messages": session.messages.order_by("created_at"),
            "form": form,
            "user_message_count": user_message_count,
        },
    )


@login_required
@require_POST
def profile_chat_stream(request):
    profile = services.get_or_create_student_profile(request.user)
    if profile.is_completed:
        return JsonResponse({"error": "Profiel is al afgerond."}, status=400)

    session = (
        ProfileChatSession.objects.filter(user=request.user, end__isnull=True)
        .order_by("-start")
        .first()
    )
    if session is None:
        session = ProfileChatSession.objects.create(user=request.user)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    form = ProfileChatMessageForm(payload)
    if not form.is_valid():
        return JsonResponse({"error": "Ongeldig verzoek", "details": form.errors}, status=400)

    def event_stream():
        def _sse(data: dict):
            return f"data: {json.dumps(data)}\n\n"

        yield _sse({"type": "status", "message": "started"})
        try:
            for delta in services.stream_profile_chat_completion(
                    session=session,
                    user_message=form.cleaned_data["message"],
            ):
                if delta:
                    yield _sse({"type": "token", "text": delta})
            yield _sse({"type": "done"})
        except RuntimeError as exc:
            yield _sse({"type": "error", "message": str(exc)})
        except Exception as exc:
            try:
                text = services.complete_profile_chat_once(
                    session=session,
                    user_message=form.cleaned_data["message"],
                )
                yield _sse({"type": "token", "text": text})
                yield _sse({"type": "done"})
            except Exception as exc2:
                print("Profile stream error:", repr(exc), repr(exc2))
                yield _sse({"type": "error", "message": "Profiel assistent is tijdelijk niet beschikbaar."})

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    return response


@login_required
def profile_detail(request):
    profile = services.get_or_create_student_profile(request.user)
    if not profile.is_completed:
        messages.info(request, "Rond eerst je intake-chat af om een samenvatting te zien.")
    return render(
        request,
        "profile/detail.html",
        {"profile": profile},
    )
