from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Count, Max
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, TemplateView

from .forms import ChatMessageForm, RegistrationForm
from .models import Course, Dashboard, Enrollment, Role, User, LoginEvent
from . import services


class HomeView(TemplateView):
    template_name = "home.html"


class UserLoginView(LoginView):
    template_name = "registration/login.html"


class UserLogoutView(LogoutView):
    next_page = reverse_lazy("home")


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully")
            return redirect("dashboard")
    else:
        form = RegistrationForm()

    return render(request, "registration/register.html", {"form": form})


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["enrollments"] = self.request.user.enrollments.select_related("course")
        context["dashboards"] = Dashboard.objects.filter(student=self.request.user.full_name)
        return context


class CourseListView(LoginRequiredMixin, ListView):
    model = Course
    template_name = "courses/list.html"
    context_object_name = "courses"

    def get_queryset(self):
        return Course.objects.prefetch_related("learning_goals")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["enrolled_ids"] = set(self.request.user.enrollments.values_list("course_id", flat=True))
        return context


@login_required
def enroll(request, pk: int):
    course = get_object_or_404(Course, pk=pk)
    enrollment, created = Enrollment.objects.get_or_create(user=request.user, course=course)
    if created:
        messages.success(request, f"Enrolled in {course.name}")
    else:
        messages.info(request, f"You are already enrolled in {course.name}")
    return redirect("courses")


@login_required
def chat_session(request, pk: int):
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
                services.stream_chat_completion(
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
            "messages": session.messages.order_by("created_at"),
            "form": form,
            "course": enrollment.course,
        },
    )


@login_required
def teacher_dashboard(request):
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
    if not request.user.has_role(Role.RoleEnum.ADMIN):
        messages.error(request, "Admin privileges required")
        return redirect("dashboard")

    login_stats = (
        LoginEvent.objects.values("user__id", "user__username", "user__email", "user__first_name", "user__last_name")
        .annotate(total=Count("id"), last_seen=Max("logged_in_at"))
        .order_by("-last_seen")
    )

    return render(
        request,
        "admin/login_activity.html",
        {"login_stats": login_stats},
    )
