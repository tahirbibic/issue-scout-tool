# Issue Scout

Finds **real, contributable** GitHub issues by filtering out the noise.

## The Problem

Finding a good open-source issue to contribute to is painful. Existing tools list
repos by language and "good first issue" labels — but they don't tell you which
repos are actually *alive*. You end up drowning in:

- **farms** — repos stuffed with `good first issue` labels but no real activity
- **dead maintainers** — repos where PRs pile up and nobody merges them
- **taken work** — issues already assigned to someone, or already covered by an open PR

You waste hours opening repos one by one to check all this manually.

## How It Works

Issue Scout applies quality filters at **two levels**:

**Repo-level** (rejects the whole repo if it fails):
- **Star floor** — skips repos below a minimum star count
- **Ghost-maintainer check** — counts recent (last 90 days) merged PRs from
  *external* contributors; rejects repos where the maintainer isn't actively
  accepting outside work

**Issue-level** (filters individual issues):
- **No pull requests** — GitHub's API mixes PRs into the issues list; these are removed
- **No assignees** — only returns issues nobody is already working on

It returns only the issues that survive all four checks.

## Why It's Different

Tools like goodfirstissue.dev and EddieHub **list** repos. Issue Scout **scores
quality** — it checks whether a repo is alive and whether an issue is actually
available, instead of just filtering by language.

## Setup

```bash
# 1. Clone
git clone https://github.com/tahirbibic/issue-scout.git
cd issue-scout

# 2. Create a virtual environment
python -m venv venv

# 3. Activate it
#    Windows (PowerShell):
.\venv\Scripts\Activate.ps1
#    Mac/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Add your GitHub token
#    Create a .env file with:
#    GITHUB_TOKEN=your_token_here

# 6. Run
uvicorn main:app --reload
```

Then open `http://127.0.0.1:8000/docs` and try the `/issues/{owner}/{repo}` endpoint.

## Example
GET /issues/encode/httpx?min_stars=100

Returns open, unassigned, non-PR issues — but only if `encode/httpx` passes the
star floor and ghost-maintainer checks.