import os
import requests
from groq import Groq
from slack_sdk import WebClient

# Keys from backend.py
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
SLACK_TOKEN   = os.environ.get("SLACK_TOKEN", "")
JIRA_DOMAIN   = os.environ.get("JIRA_DOMAIN", "")
JIRA_EMAIL    = os.environ.get("JIRA_EMAIL", "")
JIRA_TOKEN    = os.environ.get("JIRA_TOKEN", "")

GROQ_KEY = "gsk_..."
if os.path.exists('tokens.txt'):
    with open('tokens.txt', 'r') as f:
        for line in f:
            if 'GROQ_API_KEY=' in line:
                GROQ_KEY = line.split('=')[1].strip()

print("--- Checking API Keys ---")

# 1. GitHub
try:
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get("https://api.github.com/user", headers=headers)
    if r.status_code == 200:
        print("[OK] GitHub Token valid.")
    else:
        print(f"[FAIL] GitHub Token: {r.status_code} {r.text}")
except Exception as e:
    print(f"[FAIL] GitHub Token Error: {e}")

# 2. Slack
try:
    slack = WebClient(token=SLACK_TOKEN)
    res = slack.auth_test()
    if res["ok"]:
        print("[OK] Slack Token valid.")
    else:
        print(f"[FAIL] Slack Token: {res}")
except Exception as e:
    print(f"[FAIL] Slack Token Error: {e}")

# 3. Jira
try:
    auth = (JIRA_EMAIL, JIRA_TOKEN)
    r = requests.get(f"https://{JIRA_DOMAIN}/rest/api/3/myself", auth=auth)
    if r.status_code == 200:
        print("[OK] Jira Token valid.")
    else:
        print(f"[FAIL] Jira Token: {r.status_code} {r.text}")
except Exception as e:
    print(f"[FAIL] Jira Token Error: {e}")

# 4. Groq
try:
    groq_client = Groq(api_key=GROQ_KEY)
    # just listing models is a good auth check
    models = groq_client.models.list()
    print("[OK] Groq API Key valid.")
except Exception as e:
    print(f"[FAIL] Groq API Key Error: {e}")

# 5. Google Calendar Token Exists?
if os.path.exists('token.json'):
    print("[INFO] Google Calendar token.json exists.")
else:
    print("[WARN] Google Calendar token.json missing.")
