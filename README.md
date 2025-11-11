# A.L.E.R.S. – Django Edition

This repository contains a full rewrite of the Adaptive Learning Environment Research Suite (A.L.E.R.S.) on top of Django 5.1. The port keeps the core ideas of the FastAPI prototype – personalized courses, OpenAI-powered chat sessions, dashboards for teachers, and role-based administration – while adopting Django best practices (custom user model, environment-driven settings, migrations, and seed scripts).

## Key Features

- **Secure auth & roles** – custom `User` model with assignable roles (student/teacher/admin/GPT-4 privileged). Registration automatically assigns student role, and admins can update roles via the UI.
- **Course + enrollment lifecycle** – same domain models as the FastAPI version (courses, learning goals, specifications, prerequisites, enrollments, checkpoints, dashboards) exposed through Django views.
- **ChatGPT integration** – students can open a course chat, send a message, and receive responses from OpenAI. Conversations persist to `ChatSession`/`Message` tables and feed the dashboards.
- **Teacher dashboards** – instructors/admins get per-student dashboards with login timestamps and mean session duration.
- **Login activity dashboard** – admins can view per-user login counts and last-seen timestamps at `/admin-tools/login-activity/`, powered by Django's built-in `user_logged_in` signal.
- **Seeding workflow** – `python manage.py seed_alers` provisions roles, actors, example courses, learning goals, and prerequisites so a fresh database mirrors the demo data.
- **12-factor settings** – `.env` controls secrets, database URLs, OpenAI credentials, and allowed hosts; no secrets are committed to git.

## Getting Started

1. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # on Windows use .venv\Scripts\activate
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**

   ```bash
   cp .env.example .env
   # edit .env with your SECRET_KEY, DATABASE_URL (or stay on sqlite), and OPENAI_API_KEY
   ```

4. **Run migrations and seed demo data**

   ```bash
   python manage.py migrate
   python manage.py seed_alers
   ```

5. **Create an admin account**

   ```bash
   python manage.py createsuperuser
   ```

6. **Start the dev server**

   ```bash
   python manage.py runserver
   ```

Visit `http://127.0.0.1:8000/`, register as a new student, enroll in a course, and open a chat to talk to the AI instructor. To use GPT‑4 level models, assign yourself the `gpt_4_privileged` role via the admin interface or the built-in user management page.

## Security Notes

- Secrets (Django key, DB credentials, OpenAI key) are **only** read from the environment.
- No default admin is created anymore; use `createsuperuser` or the admin UI to manage privileged accounts.
- Dashboard updates now operate on real ORM models and leverage atomic transactions, removing the bugs listed in `REVIEW.md`.

## Tests / Linting

For brevity this rewrite focuses on parity with the FastAPI behaviour. Add your preferred linters/tests before deploying to production.
