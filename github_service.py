import os
import requests
from dotenv import load_dotenv

class GitHubError(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message
        super().__init__(message)

load_dotenv()

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")


def get_repo_stars(owner: str, repo: str):
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

    response = requests.get(url, headers=headers)   # bez params - repo endpoint nema "state"

    if response.status_code != 200:
        raise GitHubError(response.status_code, response.json().get("message", ""))

    data = response.json()
    return data["stargazers_count"]


def fetch_open_issues(owner: str, repo: str, min_stars: int):
    stars = get_repo_stars(owner, repo)
    if stars < min_stars:
        return []                          

    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

    response = requests.get(url, headers=headers, params={"state": "open"})

    if response.status_code != 200:
        raise GitHubError(response.status_code, response.json().get("message", ""))

    issues = response.json()

    results = []
    for issue in issues:
        if "pull_request" in issue:
            continue
        if issue["assignee"] is None:
            results.append({
                "title": issue["title"],
                "number": issue["number"],
                "url": issue["html_url"],
            })
    return results