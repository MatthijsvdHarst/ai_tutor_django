from __future__ import annotations

from typing import Iterable, List

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Role(models.Model):
    class RoleEnum(models.TextChoices):
        STUDENT = "student", "Student"
        TEACHER = "teacher", "Teacher"
        ADMIN = "admin", "Admin"
        GPT4_PRIVILEGED = "gpt_4_privileged", "GPT-4 Privileged"

    name = models.CharField(max_length=50, choices=RoleEnum.choices, unique=True)
    description = models.TextField(blank=True)

    def __str__(self) -> str:  # pragma: no cover - admin helper
        return self.get_name_display()


class User(AbstractUser):
    roles = models.ManyToManyField(Role, related_name="users", blank=True)

    @property
    def full_name(self) -> str:
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.username

    # Convenience role guards -------------------------------------------------
    def has_role(self, role_name: str) -> bool:
        return self.roles.filter(name=role_name).exists()

    def grant_role(self, role_name: str) -> None:
        role, _ = Role.objects.get_or_create(name=role_name)
        self.roles.add(role)


class Actor(models.Model):
    class OpenAIModel(models.TextChoices):
        GPT_35_TURBO_1106 = "gpt-3.5-turbo-1106", "GPT-3.5 Turbo 1106"
        GPT_35_TURBO_16K = "gpt-3.5-turbo-16k", "GPT-3.5 Turbo 16K"
        GPT_4O = "gpt-4o", "GPT-4o"
        GPT_4O_MINI = "gpt-4o-mini", "GPT-4o mini"

    name = models.CharField(max_length=100)
    model = models.CharField(max_length=50, choices=OpenAIModel.choices)
    temperature = models.FloatField(default=0.7, validators=[MinValueValidator(0.0), MaxValueValidator(2.0)])
    max_tokens = models.PositiveIntegerField(default=2048)
    top_p = models.FloatField(default=1.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    frequency_penalty = models.FloatField(default=0.0, validators=[MinValueValidator(-2.0), MaxValueValidator(2.0)])
    presence_penalty = models.FloatField(default=0.0, validators=[MinValueValidator(-2.0), MaxValueValidator(2.0)])

    def get_settings(self) -> dict:
        return {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
        }

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} ({self.model})"


class Course(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    image_url = models.URLField(blank=True)
    profile_template = models.TextField()
    instructor_prompt = models.TextField()
    checkpointer_prompt = models.TextField()
    profiler_prompt = models.TextField()

    instructor_actor = models.ForeignKey(Actor, related_name="instructor_courses", on_delete=models.PROTECT)
    profiler_actor = models.ForeignKey(Actor, related_name="profiler_courses", on_delete=models.PROTECT)
    checkpointer_actor = models.ForeignKey(Actor, related_name="checkpointer_courses", on_delete=models.PROTECT)

    def __str__(self) -> str:  # pragma: no cover
        return self.name

    def get_curriculum(self, enrollment: "Enrollment | None" = None, include_spec_id: bool = False) -> str:
        completed_ids = set()
        if enrollment:
            completed_ids = set(enrollment.checkpoints.values_list("specification_id", flat=True))
        lines: List[str] = []
        for idx, goal in enumerate(self.learning_goals.all(), start=1):
            lines.append(f"{idx}. {goal.description}")
            for spec_idx, spec in enumerate(goal.specifications.all()):
                marker = " (COMPLETED)" if spec.id in completed_ids else ""
                spec_id_part = f" (specification_id={spec.id})" if include_spec_id else ""
                letter = chr(ord("a") + spec_idx)
                lines.append(f"    {letter}. {spec.description}{spec_id_part}{marker}")
        return "\n".join(lines)


class Prerequisite(models.Model):
    prerequisite_course = models.ForeignKey(Course, related_name="dependants", on_delete=models.CASCADE)
    dependant_course = models.ForeignKey(Course, related_name="prerequisites", on_delete=models.CASCADE)
    uses_profile = models.BooleanField(default=False)
    updates_profile = models.BooleanField(default=False)

    class Meta:
        unique_together = ("prerequisite_course", "dependant_course")


class LearningGoal(models.Model):
    course = models.ForeignKey(Course, related_name="learning_goals", on_delete=models.CASCADE)
    description = models.CharField(max_length=750)

    def __str__(self) -> str:  # pragma: no cover
        return self.description


class Specification(models.Model):
    learning_goal = models.ForeignKey(LearningGoal, related_name="specifications", on_delete=models.CASCADE)
    description = models.CharField(max_length=750)

    def __str__(self) -> str:  # pragma: no cover
        return self.description


class CourseInstructorProfile(models.Model):
    course = models.ForeignKey(Course, related_name="instructors", on_delete=models.CASCADE)
    actor = models.ForeignKey(Actor, related_name="course_profiles", on_delete=models.PROTECT)
    persona_prompt = models.TextField(blank=True)
    name = models.CharField(max_length=100)
    description = models.TextField()

    def get_settings(self) -> dict:
        settings = self.actor.get_settings()
        if self.persona_prompt:
            settings["persona_prompt"] = self.persona_prompt
        return settings


class Enrollment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="enrollments", on_delete=models.CASCADE)
    course = models.ForeignKey(Course, related_name="enrollments", on_delete=models.CASCADE)
    starting_date = models.DateTimeField(default=timezone.now)
    ending_date = models.DateTimeField(blank=True, null=True)
    last_login = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("user", "course")

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.user.full_name} -> {self.course.name}"

    def get_newest_chat_session(self) -> "ChatSession | None":
        return self.chat_sessions.order_by("-start").first()

    def create_new_session(self, title: str | None = None) -> "ChatSession":
        session = ChatSession.objects.create(enrollment=self, title=title)
        session.start_session()
        return session

    def get_latest_profile(self) -> "Profile | None":
        return self.profiles.order_by("-created_at").first()

    def build_instructor_system_prompt_messages(self) -> list[dict]:
        system_prompts: list[dict] = []
        intro = (
            "Initial System Message:\n\n"
            "Welcome to the Adaptive Learning Environment. You will receive several system "
            "messages describing the course, curriculum and learner context. After the final "
            "message you start the session immediately."
        )
        system_prompts.append({"role": Message.Role.SYSTEM, "content": intro})

        course_info = (
            f"General Course Information:\n\nCourse: {self.course.name}\n"
            f"Description: {self.course.description}\n"
            f"Teacher: {self.course.instructors.first().name if self.course.instructors.exists() else 'AI Instructor'}"
        )
        system_prompts.append({"role": Message.Role.SYSTEM, "content": course_info})

        curriculum = self.course.get_curriculum(self)
        system_prompts.append(
            {
                "role": Message.Role.SYSTEM,
                "content": f"Course Curriculum:\n{curriculum}",
            }
        )

        latest_profile = self.get_latest_profile()
        if latest_profile:
            system_prompts.append(
                {
                    "role": Message.Role.SYSTEM,
                    "content": (
                        "User Specific Information and Instructions:\n\n"
                        f"{latest_profile.content}"
                    ),
                }
            )

        student_profile = getattr(self.user, "student_profile", None)
        if student_profile and student_profile.is_completed and student_profile.summary:
            system_prompts.append(
                {
                    "role": Message.Role.SYSTEM,
                    "content": (
                        "Learner Intake Summary (preferences and goals):\n"
                        f"{student_profile.summary}"
                    ),
                }
            )

        system_prompts.append(
            {
                "role": Message.Role.SYSTEM,
                "content": f"Extra context:\nCurrent date: {timezone.now().date().isoformat()}",
            }
        )

        return system_prompts


class Dashboard(models.Model):
    student = models.CharField(max_length=150)
    course = models.CharField(max_length=150)
    creator = models.CharField(max_length=150)
    course_started = models.DateTimeField()
    course_completed = models.DateTimeField(blank=True, null=True)
    student_last_login = models.DateTimeField(blank=True, null=True)
    mean_session_minutes = models.FloatField(default=0.0)
    skill_metrics = models.JSONField(default=dict, blank=True)
    behavioral_metrics = models.JSONField(default=dict, blank=True)
    affective_metrics = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("student", "course")


class ChatSession(models.Model):
    enrollment = models.ForeignKey(Enrollment, related_name="chat_sessions", on_delete=models.CASCADE)
    start = models.DateTimeField(default=timezone.now)
    end = models.DateTimeField(blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)

    def start_session(self) -> None:
        system_messages = self.enrollment.build_instructor_system_prompt_messages()
        Message.objects.bulk_create(
            [
                Message(
                    chat_session=self,
                    role=message["role"],
                    content=message["content"],
                )
                for message in system_messages
            ]
        )

    def end_session(self) -> None:
        self.end = timezone.now()
        self.save(update_fields=["end"])

    def add_messages(self, messages: Iterable["Message"]) -> None:
        Message.objects.bulk_create(messages)


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        SYSTEM = "system", "System"
        ASSISTANT = "assistant", "Assistant"
        TOOL = "tool", "Tool"

    chat_session = models.ForeignKey(ChatSession, related_name="messages", on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    is_visible = models.BooleanField(default=True)

    def to_chat_completion(self) -> dict:
        return {"role": self.role, "content": self.content}


class Profile(models.Model):
    enrollment = models.ForeignKey(Enrollment, related_name="profiles", on_delete=models.CASCADE)
    chat_session = models.ForeignKey(ChatSession, related_name="profiles", on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)


class Checkpoint(models.Model):
    enrollment = models.ForeignKey(Enrollment, related_name="checkpoints", on_delete=models.CASCADE)
    specification = models.ForeignKey(Specification, related_name="checkpoints", on_delete=models.CASCADE)
    completed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("enrollment", "specification")


class LoginEvent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="login_events", on_delete=models.CASCADE)
    logged_in_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-logged_in_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.user} @ {self.logged_in_at.isoformat()}"


class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="student_profile", on_delete=models.CASCADE)
    summary = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def mark_completed(self, summary: str) -> None:
        self.summary = summary
        self.is_completed = True
        self.completed_at = timezone.now()
        self.save(update_fields=["summary", "is_completed", "completed_at", "updated_at"])

    def __str__(self) -> str:  # pragma: no cover
        return f"StudentProfile({self.user.username})"


class ProfileChatSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="profile_chat_sessions", on_delete=models.CASCADE)
    start = models.DateTimeField(default=timezone.now)
    end = models.DateTimeField(blank=True, null=True)

    def end_session(self) -> None:
        self.end = timezone.now()
        self.save(update_fields=["end"])

    def add_messages(self, messages: Iterable["ProfileMessage"]) -> None:
        ProfileMessage.objects.bulk_create(messages)

    def __str__(self) -> str:  # pragma: no cover
        return f"ProfileChatSession({self.user.username} @ {self.start.isoformat()})"


class ProfileMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        SYSTEM = "system", "System"
        ASSISTANT = "assistant", "Assistant"
        TOOL = "tool", "Tool"

    session = models.ForeignKey(ProfileChatSession, related_name="messages", on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    def to_chat_completion(self) -> dict:
        return {"role": self.role, "content": self.content}
