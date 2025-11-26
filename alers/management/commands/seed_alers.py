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
        self.stdout.write("Ensuring roles…")
        for role in Role.RoleEnum:
            Role.objects.get_or_create(name=role)

        self.stdout.write("Resetting existing courses and actors…")
        Course.objects.all().delete()
        Actor.objects.all().delete()

        self.stdout.write("Creating actors…")
        tutor_actor, _ = Actor.objects.get_or_create(
            name="Embedded Systems Tutor",
            defaults={
                "model": Actor.OpenAIModel.GPT_4O,
                "temperature": 0.6,
            },
        )
        exam_actor, _ = Actor.objects.get_or_create(
            name="Exam Proctor",
            defaults={
                "model": Actor.OpenAIModel.GPT_4O_MINI,
                "temperature": 0.2,
            },
        )

        self.stdout.write("Creating courses…")
        tutor_course, _ = Course.objects.get_or_create(
            name="Embedded Systems Tutor",
            defaults={
                "description": "Interactieve begeleiding op basis van het dictaat Embedded Systems (versie 1.1, R.A. van Neijhof).",
                "profile_template": "Gebruik de intake-samenvatting om voorbeelden en uitleg aan te passen.",
                "instructor_prompt": (
                    "Je bent een docent Embedded Systems. Baseer je uitleg strikt op het dictaat. "
                    "Leg stap-voor-stap uit met voorbeelden uit het boek en check regelmatig begrip."
                ),
                "checkpointer_prompt": "Markeer behandelde specificaties en volg voortgang per hoofdstuk.",
                "profiler_prompt": "Werk kennis- en vaardigheidsgaps bij na elk gesprek.",
                "instructor_actor": tutor_actor,
                "profiler_actor": tutor_actor,
                "checkpointer_actor": tutor_actor,
            },
        )
        exam_course, _ = Course.objects.get_or_create(
            name="Embedded Systems Exam Practice",
            defaults={
                "description": "Examengerichte oefensessies: de AI stelt vragen, geeft geen antwoorden, maar checkt of je oplossing klopt.",
                "profile_template": "Gebruik intake-samenvatting alleen voor toon; geef geen inhoudelijke hints.",
                "instructor_prompt": (
                    "Je speelt de rol van strikte examinator. Stel één vraag tegelijk, geef geen oplossingen. "
                    "Beoordeel antwoorden kort en vraag door totdat de student zelf de juiste redenering toont."
                ),
                "checkpointer_prompt": "Log welke hoofdstukken en vraagtypes beoordeeld zijn.",
                "profiler_prompt": "Werk alleen de examenvoorbereiding-status bij, geen hints.",
                "instructor_actor": exam_actor,
                "profiler_actor": exam_actor,
                "checkpointer_actor": exam_actor,
            },
        )

        self.stdout.write("Linking personas…")
        CourseInstructorProfile.objects.get_or_create(
            course=tutor_course,
            actor=tutor_actor,
            defaults={
                "name": "Embedded Systems Tutor",
                "description": "Geduldige docent die voorbeelden uit het dictaat gebruikt.",
                "persona_prompt": "Blijf binnen de stof van het dictaat en leg uit met concrete voorbeelden en tussenstappen.",
            },
        )
        CourseInstructorProfile.objects.get_or_create(
            course=exam_course,
            actor=exam_actor,
            defaults={
                "name": "Exam Proctor",
                "description": "Strenge toezichthouder die antwoorden niet weggeeft.",
                "persona_prompt": "Geef geen antwoorden; stel controlevragen, beoordeel kort en blijf neutraal.",
            },
        )

        self.stdout.write("Generating learning goals from dictaat…")
        tutor_goals = [
            {
                "goal": "H1: Inleiding en kenmerken van embedded systems",
                "specs": [
                    "Beschrijf kernkenmerken van een embedded system en voorbeelden uit de dagelijkse praktijk.",
                    "Leg uit hoe sensor–verwerking–actuator ketens werken in een embedded systeem.",
                ],
            },
            {
                "goal": "H2: Talstelsels en omrekenen",
                "specs": [
                    "Toon notatie en leesbaarheid voor decimale, binaire, octale en hexadecimale getallen.",
                    "Reken getallen om tussen decimaal, binair, octaal en hex zonder en met shortcuts.",
                ],
            },
            {
                "goal": "H3: Toepassingen van talstelsels",
                "specs": [
                    "Pas talstelsels toe in contexten zoals FLAGS-registers, IPv4/IPv6, chmod en MAC-adressen.",
                    "Analyseer hoe representaties invloed hebben op interpretatie in hardware/software.",
                ],
            },
            {
                "goal": "H4: Negatieve getallen",
                "specs": [
                    "Vergelijk unsigned, signed magnitude, 1’s complement, 2’s complement en bias representaties.",
                    "Bepaal decimale waarde van een binaire code in verschillende representaties.",
                ],
            },
            {
                "goal": "H5: Integer berekeningen en hardware",
                "specs": [
                    "Herken overflow/onderflow in integer-operaties en hoe hardware dit signaleert.",
                    "Pas bitmanipulaties toe (shift, AND, OR, XOR, clear) in rekenvoorbeelden.",
                ],
            },
            {
                "goal": "H6: Gebroken getallen",
                "specs": [
                    "Leg fixed-point representatie uit en positioneer de binaire punt.",
                    "Herken fouten en beperkingen bij gebroken getallen in hardware.",
                ],
            },
            {
                "goal": "H7: Digitale poorten",
                "specs": [
                    "Herken symbolen en waarheidstabellen voor AND, OR, NOT, EXOR, NAND, NOR, EXNOR.",
                    "Pas De Morgan en universele bouwstenen toe om poortnetwerken te herschrijven.",
                ],
            },
            {
                "goal": "H8: Combinatorische schakelingen",
                "specs": [
                    "Analyseer en synthesize combinatorische logica; bouw waarheidstabellen en minimaliseer.",
                    "Gebruik kaart/algoritmen om logische expressies te vereenvoudigen.",
                ],
            },
            {
                "goal": "H9: Microcontrollers programmeren",
                "specs": [
                    "Lees en wijzig hardware registers; pas bitmaskers toe.",
                    "Schrijf korte codefragmenten voor bitoperaties (shifts, set/clear/toggle bits).",
                ],
            },
        ]

        exam_goals = [
            {
                "goal": "Examenvragen over talstelsels en negatieve getallen",
                "specs": [
                    "Beantwoord conversie- en representatievragen (decimaal/binair/octa/hex, 2’s complement) zonder hints.",
                    "Onderbouw of een gegeven antwoord correct is en waarom.",
                ],
            },
            {
                "goal": "Examenvragen over logica en schakelingen",
                "specs": [
                    "Analyseer waarheidstabellen en poortnetwerken; minimaliseer expressies onder tijdsdruk.",
                    "Controleer stap-voor-stap redeneringen zonder zelf de oplossing te geven.",
                ],
            },
            {
                "goal": "Examenvragen over microcontroller-bitoperaties",
                "specs": [
                    "Evalueer registermanipulaties (set/clear/shift) en detecteer fouten.",
                    "Vraag door totdat de student de juiste bitoperatie zelf formuleert.",
                ],
            },
        ]

        self._seed_learning_goals_with_specs(tutor_course, tutor_goals)
        self._seed_learning_goals_with_specs(exam_course, exam_goals)

        self.stdout.write("Configuring prerequisites…")
        Prerequisite.objects.get_or_create(
            prerequisite_course=tutor_course,
            dependant_course=exam_course,
            defaults={"uses_profile": True, "updates_profile": False},
        )

        self.stdout.write(self.style.SUCCESS("Seeding complete."))

    def _seed_learning_goals_with_specs(self, course: Course, goal_data: list[dict]):
        for item in goal_data:
            goal, _ = LearningGoal.objects.get_or_create(course=course, description=item["goal"])
            for spec_desc in item["specs"]:
                Specification.objects.get_or_create(
                    learning_goal=goal,
                    description=spec_desc,
                )
