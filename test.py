import os
import json
import base64
import requests
from datetime import datetime
import openai
​
# --- CONFIG ---
GITHUB_REPO = "umarali-nagoor/Test_Repo"
REPO_OWNER = "umarali-nagoor"
REPO_NAME = "Test_Repo"
BRANCH = "master"
RELEASE_NOTES_PATH = "release.md"
ROADMAP_PATH = "product_roadmap.md"
​
# API KEYS
openai.api_key = os.getenv("OPENAI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}
​
# --- FETCHING UTILITIES ---
​
def fetch_github_file(path, branch={BRANCH}):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}?ref={branch}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        content = response.json()["content"]
        return base64.b64decode(content).decode("utf-8")
    else:
        raise Exception(f"❌ Failed to fetch file {path}: {response.status_code}")
​
def fetch_open_issues():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues?state=open&per_page=100"
    issues = []
    page = 1
    while True:
        response = requests.get(f"{url}&page={page}", headers=HEADERS)
        if response.status_code != 200:
            raise Exception(f"❌ Failed to fetch issues: {response.status_code}")
        page_issues = response.json()
        page_issues = [i for i in page_issues if "pull_request" not in i]
        if not page_issues:
            break
        issues.extend(page_issues)
        page += 1
    return issues
​
# --- LLM ANALYSIS UTILITIES ---
​
def detect_issues_to_close(release_notes, issues):
    issue_summary = "\n".join([f"- #{i['number']}: {i['title']}" for i in issues])
    prompt = f"""
You are an assistant identifying which GitHub issues have already been addressed in the release notes.
​
GitHub Issues:
{issue_summary}
​
Release Notes:
\"\"\"{release_notes}\"\"\"
​
List only the issue numbers (e.g. #123) that are clearly referenced in the release notes using formats like:
#123, (#123), or full URL.
​
Output format:
#123
#456
"""
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return [line.strip() for line in response.choices[0].message.content.splitlines() if line.strip().startswith("#")]
​
def get_irrelevant_issues_based_on_roadmap(roadmap_text, issues):
    def extract_status_from_labels(labels):
        for label in labels:
            name = label.get("name", "").lower()
            if "[status]" in name:
                return name.replace("[status]", "").strip()
        return "unknown"
​
    def format_issue(issue):
        aha_link_present = 'Yes' if 'aha.io' in (issue.get('body') or '').lower() else 'No'
        labels = issue.get('labels', [])
        status = extract_status_from_labels(labels)
        last_updated = issue.get('updated_at')
        days_since_update = (
            (datetime.utcnow() - datetime.strptime(last_updated, "%Y-%m-%dT%H:%M:%SZ")).days
            if last_updated else "Unknown"
        )
        return f"""Issue #{issue['number']}: {issue['title']}
Description: {issue.get('body', '[No description]')}
AHA Link Present: {aha_link_present}
Status: {status}
Days Since Last Update: {days_since_update}"""
​
    issue_texts = "\n\n".join(format_issue(issue) for issue in issues)
​
    prompt = f"""
You are an AI assistant helping triage GitHub issues in relation to a product roadmap.
​
Below is the roadmap:
{roadmap_text}
​
Here are the GitHub issues:
{issue_texts}
​
Rules for irrelevance:
1. If the issue has an AHA link, it's **relevant**.
2. If no AHA link:
   - If in-progress and updated in last 30 days → **relevant**
   - If in-progress but not updated in 30+ days → **irrelevant**
   - If in backlog or to-do → **irrelevant**
​
Return a list of **irrelevant** issues only. Format:
- Issue #{{number}}: {{title}}
"""
​
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content.strip()
def main():
    print("Fetching release notes...")
    release_notes = fetch_github_file(RELEASE_NOTES_PATH, BRANCH)
​
    print("Fetching roadmap...")
    roadmap = fetch_github_file(ROADMAP_PATH, BRANCH)
​
    print("Fetching open issues...")
    issues = fetch_open_issues()
​
    print("Detecting issues that can be closed based on release notes...")
    closed_issue_refs = detect_issues_to_close(release_notes, issues)  # like ['#12', '#34']
    print(closed_issue_refs)
​
    print("Identifying irrelevant issues based on roadmap and issue metadata...")
    irrelevant_issues_report = get_irrelevant_issues_based_on_roadmap(roadmap, issues)
    print(irrelevant_issues_report)
​
    # Extract irrelevant issue numbers from LLM output (e.g., "- Issue #123: Something")
    irrelevant_issue_nums = [
        int(line.split("#")[1].split(":")[0])
        for line in irrelevant_issues_report.splitlines()
        if line.strip().startswith("- Issue #")
    ]
​
    # Convert closed issue refs (e.g., "#12") to numbers
    closed_issue_nums = [int(ref.lstrip("#")) for ref in closed_issue_refs]
​
    # Combine both
    all_to_deprioritize_or_close = set(closed_issue_nums + irrelevant_issue_nums)
​
    print("\n Issues to Close Based on Roadmap & Release Notes")
    for issue in issues:
        if issue["number"] in all_to_deprioritize_or_close:
            print(f"- {issue['html_url']}")
    with open("issues_to_notify.txt", "w") as f:
        for issue in issues:
            if issue["number"] in all_to_deprioritize_or_close:
                url = issue["html_url"]
                print(f"- {url}")
                f.write(url + "\n")
​
    # Optional: list remaining open issues (still under consideration)
    # print("\n📌 Issues Still Open (Not Closed or Deprioritized):")
    # for issue in issues:
    #     if issue["number"] not in all_to_deprioritize_or_close:
    #         print(f"- {issue['html_url']}")
​
if __name__ == "__main__":
    main()
