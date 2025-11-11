from __future__ import annotations

from django.core.management.base import BaseCommand

from alers.models import (
    Actor,
    Course,
    CourseInstructorProfile,
    LearningGoal,
    Prerequisite,
    Role,
    Specification,
)


class Command(BaseCommand):
    help = "Seed the database with roles, actors, courses, and learning goals."

    def handle(self, *args, **options):
        self.stdout.write("Creating roles…")
        for role in Role.RoleEnum:
            Role.objects.get_or_create(name=role)

        self.stdout.write("Creating actors…")
        counselor_actor, _ = Actor.objects.get_or_create(
            name="Sarah Thompson",
            defaults={
                "model": Actor.OpenAIModel.GPT_4O_MINI,
                "temperature": 0.8,
            },
        )
        history_actor, _ = Actor.objects.get_or_create(
            name="Dr. Victor Aurelius",
            defaults={
                "model": Actor.OpenAIModel.GPT_4O,
                "temperature": 0.6,
            },
        )

        self.stdout.write("Creating courses…")
        counseling_course, _ = Course.objects.get_or_create(
            name="Student Counseling and Support",
            defaults={
                "description": "Personalized counseling sessions that adapt to the learner's goals and wellbeing.",
                "profile_template": "To be updated.",
                "instructor_prompt": "Focus on empathy, rapport, and actionable guidance.",
                "checkpointer_prompt": "Track completed counseling milestones.",
                "profiler_prompt": "Capture the student's emotional profile after each session.",
                "instructor_actor": counselor_actor,
                "profiler_actor": counselor_actor,
                "checkpointer_actor": counselor_actor,
            },
        )
        history_course, _ = Course.objects.get_or_create(
            name="Rise of the Roman Empire",
            defaults={
                "description": "A narrative exploration of the political and military rise of Rome.",
                "profile_template": "To be updated.",
                "instructor_prompt": "Channel the expertise of a historian to guide the learner.",
                "checkpointer_prompt": "Track completed historical specifications.",
                "profiler_prompt": "Update learner knowledge gaps after each chat.",
                "instructor_actor": history_actor,
                "profiler_actor": history_actor,
                "checkpointer_actor": history_actor,
            },
        )

        self.stdout.write("Linking personas…")
        CourseInstructorProfile.objects.get_or_create(
            course=counseling_course,
            actor=counselor_actor,
            defaults={
                "name": "Sarah Thompson",
                "description": "Dedicated student psychologist specializing in learning difficulties.",
                "persona_prompt": "Lead with empathy and ensure privacy and trust with each student interaction.",
            },
        )
        CourseInstructorProfile.objects.get_or_create(
            course=history_course,
            actor=history_actor,
            defaults={
                "name": "Dr. Victor Aurelius",
                "description": "Historian focusing on the Roman Empire.",
                "persona_prompt": "Adopt a storytelling approach that connects past and present.",
            },
        )

        self.stdout.write("Generating learning goals…")
        counseling_goals = [
            "Diagnose learning difficulties",
            "Define actionable learning plans",
            "Empower student wellbeing",
        ]
        history_goals = [
            "Understand the Republic",
            "Trace Julius Caesar's rise",
            "Explain the Augustan reforms",
        ]
        self._seed_learning_goals(counseling_course, counseling_goals)
        self._seed_learning_goals(history_course, history_goals)

        self.stdout.write("Configuring prerequisites…")
        Prerequisite.objects.get_or_create(
            prerequisite_course=counseling_course,
            dependant_course=history_course,
            defaults={"uses_profile": True, "updates_profile": True},
        )

        self.stdout.write(self.style.SUCCESS("Seeding complete."))

    def _seed_learning_goals(self, course: Course, descriptions: list[str]):
        for description in descriptions:
            goal, _ = LearningGoal.objects.get_or_create(course=course, description=description)
            Specification.objects.get_or_create(
                learning_goal=goal,
                description=f"Mastery of: {description}",
            )
