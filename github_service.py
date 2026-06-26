import os
import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

def fetch_open_issues(owner: str, repo: str):
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    
    response = requests.get(url, headers=headers, params={"state": "open"})

    if response.status_code != 200:
        raise Exception(f"GitHub API error: {response.status_code} - {response.json().get('message', '')}")

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