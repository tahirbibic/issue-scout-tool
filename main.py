from fastapi import FastAPI, HTTPException
from github_service import fetch_open_issues, GitHubError

app = FastAPI()


@app.get("/issues/{owner}/{repo}")
def get_issues(owner: str, repo: str, min_stars: int = 0):
    try:
        return fetch_open_issues(owner, repo, min_stars)
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)