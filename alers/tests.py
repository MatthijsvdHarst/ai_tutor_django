from unittest import mock

from django.test import TestCase
from django.urls import reverse

from .models import (
    Actor,
    Course,
    Enrollment,
    ProfileChatSession,
    ProfileMessage,
    StudentProfile,
    User,
)


class ProfileIntakeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="learner", password="pass", email="learner@example.com")

    def test_redirects_to_profile_chat_when_incomplete(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("profile-chat"))

    def test_redirects_other_pages_when_incomplete(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("courses"))
        self.assertRedirects(response, reverse("profile-chat"))

    def test_profile_summary_added_to_system_prompt(self):
        profile = StudentProfile.objects.create(
            user=self.user,
            summary="Prefer korte uitleg en veel voorbeelden.",
            is_completed=True,
        )
        actor = Actor.objects.create(name="Tutor", model=Actor.OpenAIModel.GPT_4O_MINI)
        course = Course.objects.create(
            name="Test Course",
            description="Desc",
            profile_template="tmpl",
            instructor_prompt="inst",
            checkpointer_prompt="chk",
            profiler_prompt="prof",
            instructor_actor=actor,
            profiler_actor=actor,
            checkpointer_actor=actor,
        )
        enrollment = Enrollment.objects.create(user=self.user, course=course)

        prompts = enrollment.build_instructor_system_prompt_messages()

        self.assertTrue(
            any(profile.summary in message["content"] for message in prompts),
            "Profile summary should be injected into course system prompts",
        )

    @mock.patch("alers.services.summarize_profile_chat", return_value="Samenvatting test")
    def test_finishing_profile_chat_marks_profile(self, summarize_mock):
        self.client.force_login(self.user)
        session = ProfileChatSession.objects.create(user=self.user)
        ProfileMessage.objects.create(session=session, role=ProfileMessage.Role.USER, content="Hoi")

        response = self.client.post(reverse("profile-chat"), {"action": "finish"})

        profile = StudentProfile.objects.get(user=self.user)
        self.assertTrue(profile.is_completed)
        self.assertEqual(profile.summary, "Samenvatting test")
        self.assertRedirects(response, reverse("dashboard"))
        summarize_mock.assert_called_once()

    def test_access_allowed_after_profile_completed(self):
        StudentProfile.objects.create(user=self.user, summary="klaar", is_completed=True)
        self.client.force_login(self.user)
        response = self.client.get(reverse("courses"))
        self.assertEqual(response.status_code, 200)

    def test_logout_shows_logged_out_page(self):
        StudentProfile.objects.create(user=self.user, summary="klaar", is_completed=True)
        self.client.force_login(self.user)
        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Je bent uitgelogd")

    @mock.patch("alers.services.summarize_profile_chat", return_value="Samenvatting test")
    def test_finish_requires_student_input(self, summarize_mock):
        self.client.force_login(self.user)
        ProfileChatSession.objects.create(user=self.user)
        response = self.client.post(reverse("profile-chat"), {"action": "finish"})
        self.assertRedirects(response, reverse("profile-chat"))
        profile = StudentProfile.objects.get(user=self.user)
        self.assertFalse(profile.is_completed)
        summarize_mock.assert_not_called()
