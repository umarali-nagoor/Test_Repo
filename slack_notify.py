from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import requests
import os

# ------------------------- Configuration -------------------------

# Slack
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
CHANNEL_ID = "D090B5SU5E0"  # Replace with your actual Slack channel ID
client = WebClient(token=SLACK_BOT_TOKEN)

# GitHub
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
print()
# GitHub username → Slack user ID map
user_map = {
    "umarali-nagoor": "U0904J11V3R",
    "geethasm": "U090MA8AR1Q",
    "Praharsha-1024": "U09035MMZJA"
}

# ------------------------- Slack Message Builder -------------------------

def build_issue_blocks(slack_user_id, issue_link):
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<@{slack_user_id}> Would you like to close the issue? If yes, click *Yes*, else click *No*."
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Yes"},
                    "style": "primary",
                    "value": issue_link,
                    "action_id": "button_yes"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "No"},
                    "style": "danger",
                    "value": issue_link,
                    "action_id": "button_no"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Would you like to review the issue? <{issue_link}|Click here to go to the issue>"
            }
        }
    ]

# ------------------------- Send Slack Message -------------------------

def send_issue_message(slack_user_id, issue_link):
    blocks = build_issue_blocks(slack_user_id, issue_link)
    fallback_text = f"<@{slack_user_id}> Please respond to the GitHub issue."

    try:
        response = client.chat_postMessage(
            channel=slack_user_id,  # send directly as DM to user
            text=fallback_text,
            blocks=blocks
        )
        print(f"✅ Sent message for {issue_link} to {slack_user_id}")
    except SlackApiError as e:
        print(f"❌ Error sending message to {slack_user_id}: {e.response['error']}")

# ------------------------- Notify from Issue List -------------------------

def notify_assignees_from_issue_list(filepath):
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    with open(filepath, "r") as f:
        issue_links = [line.strip() for line in f if line.strip()]

    for issue_link in issue_links:
        try:
            parts = issue_link.split("/")
            owner, repo, issue_number = parts[3], parts[4], parts[-1]
        except IndexError:
            print(f"❌ Invalid issue URL format: {issue_link}")
            continue

        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"❌ Failed to fetch issue #{issue_number}: {response.status_code}")
            continue

        issue = response.json()
        assignees = [a["login"] for a in issue.get("assignees", [])]

        if assignees:
            for github_user in assignees:
                if github_user in user_map:
                    slack_user_id = user_map[github_user]
                    send_issue_message(slack_user_id, issue_link)
                else:
                    print(f"⚠️ No Slack ID mapped for GitHub user: {github_user}")
        else:
            creator = issue.get("user", {}).get("login")
            if creator in user_map:
                slack_user_id = user_map[creator]
                send_issue_message(slack_user_id, issue_link)
                print(f"ℹ️ No assignee — sent to issue creator: {creator}")
            else:
                print(f"⚠️ No assignees or Slack ID mapped for issue creator: {creator}")

# ------------------------- Trigger -------------------------

if __name__ == "__main__":
    notify_assignees_from_issue_list("/Users/praharsha/Desktop/Test_Repo/issues_to_notify.txt")
