"""
Nexus Health Check  ·  Run: python health_check.py
Loads keys from backend/.env (local) OR env vars (Railway).
Never prints secrets.
"""
import os, sys, requests

# ── Load .env ──────────────────────────────────────────────────────────────
env_path = os.path.join(os.path.dirname(__file__), "backend", ".env")
if os.path.isfile(env_path):
    # PowerShell sometimes saves as UTF-16-LE without BOM — detect via null bytes
    raw_head = open(env_path, "rb").read(8)
    if b'\x00' in raw_head:
        enc = "utf-16-le"
    elif raw_head[:2] in (b'\xff\xfe', b'\xfe\xff'):
        enc = "utf-16"
    else:
        enc = "utf-8"
    with open(env_path, encoding=enc, errors="ignore") as f:
        for line in f:
            line = line.strip().replace("\x00", "").replace("\ufeff", "")
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip().replace("\x00", "")
            v = v.strip().strip('"').strip("'").replace("\x00", "")
            if k and k not in os.environ:
                os.environ[k] = v

# ── Helpers ────────────────────────────────────────────────────────────────
OK  = "  ✅"
ERR = "  ❌"

def check(label: str, ok: bool, detail: str = ""):
    icon = OK if ok else ERR
    print(f"{icon}  {label}" + (f"  →  {detail}" if detail else ""))
    return ok

def env(key: str) -> str:
    return os.environ.get(key, "").strip()

# ── 1. Groq ────────────────────────────────────────────────────────────────
print("\n🔎  GROQ")
key = env("GROQ_API_KEY")
if not key:
    check("GROQ_API_KEY set", False, "missing from .env")
else:
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile",
                  "messages": [{"role": "user", "content": "ping"}],
                  "max_tokens": 1},
            timeout=10
        )
        check("Groq API", r.status_code == 200, f"HTTP {r.status_code}")
    except Exception as e:
        check("Groq API", False, str(e))

# ── 2. GitHub ─────────────────────────────────────────────────────────────
print("\n🔎  GITHUB")
gh_token = env("GITHUB_TOKEN")
gh_owner = env("GITHUB_OWNER")
gh_repo  = env("GITHUB_REPO")
check("GITHUB_TOKEN set", bool(gh_token))
check("GITHUB_OWNER set", bool(gh_owner), gh_owner or "missing")
check("GITHUB_REPO set",  bool(gh_repo),  gh_repo  or "missing")
if gh_token and gh_owner and gh_repo:
    try:
        r = requests.get(
            f"https://api.github.com/repos/{gh_owner}/{gh_repo}/pulls",
            headers={"Authorization": f"token {gh_token}"},
            timeout=8
        )
        check("GitHub PRs fetch", r.status_code == 200,
              f"HTTP {r.status_code}" + (f" – {r.json().get('message','')}" if r.status_code != 200 else f", {len(r.json())} open PRs"))
    except Exception as e:
        check("GitHub PRs fetch", False, str(e))

# ── 3. Jira ───────────────────────────────────────────────────────────────
print("\n🔎  JIRA")
domain = env("JIRA_DOMAIN")
email  = env("JIRA_EMAIL")
token  = env("JIRA_TOKEN")
check("JIRA_DOMAIN set", bool(domain), domain or "missing")
check("JIRA_EMAIL set",  bool(email))
check("JIRA_TOKEN set",  bool(token))
if domain and email and token:
    try:
        r = requests.get(
            f"https://{domain}/rest/api/3/search/jql",
            params={"jql": "project=SCRUM ORDER BY created DESC", "maxResults": 5},
            auth=(email, token),
            timeout=10
        )
        seraph = r.headers.get("X-Seraph-Loginreason", "")
        authed = "AUTHENTICATED_FAILED" not in seraph
        check("Jira token valid (no AUTHENTICATED_FAILED)", authed,
              seraph if not authed else "token accepted by Jira")
        if authed:
            data = r.json()
            n = len(data.get("issues", []))
            check("Jira SCRUM tickets visible",
                  n > 0 or "errorMessages" not in data,
                  f"{n} tickets returned" if n > 0 else ", ".join(data.get("errorMessages", ["0 tickets returned - check project permissions"])))
    except Exception as e:
        check("Jira request", False, str(e))

# ── 4. Slack ──────────────────────────────────────────────────────────────
print("\n🔎  SLACK")
slack_token = env("SLACK_TOKEN")
check("SLACK_TOKEN set", bool(slack_token))
if slack_token:
    try:
        r = requests.get(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {slack_token}"},
            timeout=8
        )
        data = r.json()
        check("Slack auth", data.get("ok", False), data.get("error", "ok"))
    except Exception as e:
        check("Slack auth", False, str(e))

# ── 5. Google Calendar (token.json presence only) ──────────────────────────
print("\n🔎  GOOGLE CALENDAR")
token_exists = os.path.exists(os.path.join("backend", "token.json"))
b64_token    = bool(env("GOOGLE_TOKEN_JSON_B64"))
check("token.json present (local) OR GOOGLE_TOKEN_JSON_B64 set (Railway)",
      token_exists or b64_token,
      "local token.json found" if token_exists else ("B64 env var set" if b64_token else "MISSING – calendar will return empty"))

# ── Summary ────────────────────────────────────────────────────────────────
print("\n" + "─" * 52)
print("✅ = working correctly   ❌ = needs fixing")
print("See ACTION items above to fix any ❌ items.")
print("─" * 52 + "\n")
