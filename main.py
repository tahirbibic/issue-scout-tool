from fastapi import FastAPI, HTTPException
from github_service import fetch_open_issues, GitHubError
from pydantic import BaseModel

class RepoRequest(BaseModel):
    owner: str
    repo: str

app = FastAPI()

@app.post("/issues/batch")
def get_issues_batch(repos: list[RepoRequest], min_stars: int = 0):
    results = []
    failed = []
    for repo in repos:
        try:
            data = fetch_open_issues(repo.owner, repo.repo, min_stars)
            results.append({
                "repo": f"{repo.owner}/{repo.repo}",
                "issues": data,
            })
        except GitHubError as e:
            failed.append({"repo": f"{repo.owner}/{repo.repo}", "error": e.message})
            continue
    return {
    "results": results,
    "failed": failed
    }

@app.get("/issues/{owner}/{repo}")
def get_issues(owner: str, repo: str, min_stars: int = 0):
    try:
        return fetch_open_issues(owner, repo, min_stars)
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)