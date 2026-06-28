# Issue Scout

A backend service that finds **real and contributable** GitHub issues and notifies you when new ones appear — filtering out the noise that other "good first issue" lists leave in.

## Problem

Finding a good open-source issue to contribute to is painful and hard. Existing tools list repos by language and `good first issue` labels, but they don't tell you which repos are actually *alive*. You end up drowning in:

- **farms** — repos stuffed with labels but no real activity
- **dead maintainers** — repos where PRs pile up and nobody merges them
- **taken work** — issues already assigned, or already covered by an open PR

Issue Scout scores repository quality instead of just filtering by language, and can run on a schedule to email you only the *new* issues that match your saved preferences.

## How It Works

### Quality engine (four filters)

Applied at two levels:

**Repo-level** (rejects the whole repo):
- **Star floor** — skips repos below a minimum star count.
- **Ghost-maintainer check** — counts merged PRs from *external* contributors in the last 90 days; rejects repos where the maintainer isn't actively accepting outside work.

**Issue-level** (filters individual issues):
- **No pull requests** — GitHub's issues endpoint mixes PRs into the list; these are removed.
- **No assignees** — only issues nobody is already working on.

A repo must pass both repo-level checks before its issues are even fetched (fail-fast: cheap checks first, to conserve the GitHub API rate limit).

### Push flow

1. A user registers, logs in (JWT), and saves a preference (language + minimum stars).
2. A background scheduler runs hourly, executes discovery for every saved preference, and emails the user any **new** matching issues.
3. Sent issues are tracked per user, so the same issue is never emailed twice.

## Features

- JWT authentication (register / login) with bcrypt-hashed passwords
- Saved per-user preferences with ownership checks (you can only run your own)
- Repository search across GitHub by language + star threshold
- Batch processing of multiple repos with graceful degradation (one failing repo doesn't break the request)
- Redis caching (cache-aside with TTL) to reduce GitHub API calls and survive restarts
- Hourly background scheduler (APScheduler) running discovery automatically
- Email notifications (SMTP) with per-user deduplication
- PostgreSQL with Alembic migrations
- Custom exceptions that return honest HTTP status codes (404 / 403 instead of a generic 500)

## Tech Stack

FastAPI · PostgreSQL · SQLAlchemy · Alembic · Redis · Docker Compose · APScheduler · PyJWT · bcrypt · SMTP

## API Overview

  Method  Endpoint  Description
 -----------------------------------
  POST   `/register`   Create an account
  POST   `/login`   Get a JWT access token
  POST   `/preferences`   Save a search preference (auth)
  POST   `/discover`   Search + filter repos by language/stars (auth)
  POST   `/discover/from-preference/{id}`   Run discovery from a saved preference (auth)
  POST   `/issues/batch`   Filter a provided list of repos
  GET    `/issues/{owner}/{repo}`   Filter a single repo's issues

## Setup (local)

```bash
# 1. Clone
git clone https://github.com/tahirbibic/issue-scout.git
cd issue-scout

# 2. Virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1        # Windows PowerShell
# source venv/bin/activate         # macOS / Linux

# 3. Dependencies
pip install -r requirements.txt

# 4. Start Postgres + Redis
docker compose up -d

# 5. Environment variables — create a .env file:
#    DATABASE_URL=postgresql://postgres:PASSWORD@localhost:5432/issue_scout
#    JWT_SECRET=your_long_random_secret
#    ALGORITHM=HS256
#    GITHUB_TOKEN=your_github_token
#    SMTP_EMAIL=you@gmail.com
#    SMTP_PASSWORD=your_gmail_app_password

# 6. Run database migrations
alembic upgrade head

# 7. Start the API
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` to explore the API.