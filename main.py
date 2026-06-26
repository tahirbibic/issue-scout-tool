from fastapi import FastAPI, HTTPException
from github_service import fetch_open_issues

app = FastAPI()

@app.get("/issues/{owner}/{repo}")
def get_issues(owner: str, repo: str):
    try:
        return fetch_open_issues(owner, repo)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch issues: {str(e)}")