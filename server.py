import json
from flask import Flask, request, jsonify
import requests
from slack_sdk import WebClient
from datetime import datetime
import pytz
import os

app = Flask(__name__)

# Secrets and tokens
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
OWNER = "umarali-nagoor"
REPO = "Test_Repo"

client = WebClient(token=SLACK_BOT_TOKEN)

# Format timestamp in IST
def get_ist_timestamp():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')

# Get issue title from GitHub
def get_issue_title(issue_number):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/issues/{issue_number}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("title", "Issue")
    return "Issue"

# Add comment
def comment_on_issue(issue_number, comment_text):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {"body": comment_text}
    response = requests.post(url, json=payload, headers=headers)
    print("Comment status:", response.status_code)
    return response.status_code == 201

# Close issue
def close_github_issue(issue_number):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/issues/{issue_number}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {"state": "closed"}
    response = requests.patch(url, json=payload, headers=headers)
    print("Issue close status:", response.status_code)
    return response.status_code == 200

@app.route('/slack/interactions', methods=['POST'])
def slack_interactions():
    payload = request.form.get('payload')
    if not payload:
        return "No payload received", 400

    data = json.loads(payload)

    if data.get("type") == "block_actions":
        action = data["actions"][0]
        user_id = data["user"]["id"]
        action_id = action["action_id"]

        if action_id == "button_yes":
            issue_link = action["value"]
            issue_number = issue_link.rstrip("/").split("/")[-1]

            # Open modal
            client.views_open(
                trigger_id=data["trigger_id"],
                view={
                    "type": "modal",
                    "callback_id": "close_issue_modal",
                    "private_metadata": issue_link,
                    "title": {"type": "plain_text", "text": "Close Issue"},
                    "submit": {"type": "plain_text", "text": "Submit"},
                    "close": {"type": "plain_text", "text": "Cancel"},
                    "blocks": [
                        {
                            "type": "input",
                            "block_id": "comment_block",
                            "element": {
                                "type": "plain_text_input",
                                "multiline": True,
                                "action_id": "comment_input"
                            },
                            "label": {"type": "plain_text", "text": "Add a comment before closing"}
                        }
                    ]
                }
            )
            return "", 200

        elif action_id == "button_no":
            issue_link = action["value"]
            issue_number = issue_link.rstrip("/").split("/")[-1]
            issue_title = get_issue_title(issue_number)
            timestamp = get_ist_timestamp()

            comment = (
                f"Automated message: *{issue_title}* is in open status after the owner’s acknowledgement.\n"
                f"Please review/fix/close the issue as early as possible at `{timestamp}` IST.\n"
                f"Link: {issue_link}"
            )

            comment_on_issue(issue_number, comment)

            return jsonify({
                "replace_original": True,
                "text": f"<@{user_id}> noted. The issue remains open."
            })

    elif data.get("type") == "view_submission":
        callback_id = data["view"]["callback_id"]
        if callback_id == "close_issue_modal":
            user_id = data["user"]["id"]
            comment = data["view"]["state"]["values"]["comment_block"]["comment_input"]["value"]
            issue_link = data["view"]["private_metadata"]
            issue_number = issue_link.rstrip("/").split("/")[-1]
            issue_title = get_issue_title(issue_number)
            timestamp = get_ist_timestamp()

            formatted_comment = (
                f"Automated message: *{issue_title}* is closed after the owner’s review at `{timestamp}` IST.\n"
                f"Link: {issue_link}\n"
                f"Owner’s message: {comment}"
            )

            comment_on_issue(issue_number, formatted_comment)
            close_github_issue(issue_number)

            return jsonify({
                "response_action": "clear"
            })

    return "", 200

if __name__ == "__main__":
    app.run(port=3000)
