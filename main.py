import json
import redis
from fastapi import FastAPI, HTTPException
from github_service import (
    fetch_open_issues,
    get_issues_batch,
    search_repos,
    GitHubError,
    RepoRequest,
)

app = FastAPI()

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

TTL = 20 * 60   # 20 minuta, u sekundama


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
    key = f"{language}:{min_stars}"

    cached = r.get(key)
    if cached is not None:
        print("CACHE HIT:", key)
        return json.loads(cached)

    print("CACHE MISS:", key)

    try:
        found = search_repos(language, min_stars)
        found = found[:10]
        batch_result = get_issues_batch(found, min_stars)
        non_empty = [x for x in batch_result["results"] if x.get("issues")]
        result = {"results": non_empty, "failed": batch_result["failed"]}

        # 3. SNIMI U REDIS sa TTL (Redis sam briše posle 20 min)
        r.setex(key, TTL, json.dumps(result))   # dict -> string za Redis

        return result
    except GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)