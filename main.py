from fastapi import FastAPI, HTTPException
from github_service import (
    fetch_open_issues,
    get_issues_batch,
    search_repos,
    GitHubError,
    RepoRequest,
)

app = FastAPI()


@app.get("/issues/{owner}/{repo}")
def get_issues(owner: str, repo: str, min_stars: int = 0):
    try:
        return fetch_open_issues(owner, repo, min_stars)
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@app.post("/issues/batch")
def issues_batch(repos: list[RepoRequest], min_stars: int = 0):
    return get_issues_batch(repos, min_stars)


@app.post("/discover")
def discover(language: str, min_stars: int = 100):
    try:
        found = search_repos(language, min_stars)
        found = found[:10]
        batch_result = get_issues_batch(found, min_stars)

        non_empty = [repo for repo in batch_result["results"] if repo.get("issues")]

        return {"results": non_empty, "failed": batch_result["failed"]}
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)