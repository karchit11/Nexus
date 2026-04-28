import os
import json
import requests
from datetime import datetime, timezone, timedelta
import concurrent.futures
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from groq import Groq
from slack_sdk import WebClient
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from pydantic import BaseModel
from intellegence_and_automation import router as ia_router

app = FastAPI(title="Nexus AI")
app.include_router(ia_router)

# ── Paths ──────────────────────────────────────────────────────────────
BACKEND_DIR  = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "frontend")

def _load_env_file(path: str) -> None:
    """Parse KEY=value from .env without extra dependencies (venv-safe)."""
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip().replace("\x00", "")
            val = val.strip().strip('"').strip("'").replace("\x00", "")
            if key and key not in os.environ:
                os.environ[key] = val


_load_env_file(os.path.join(BACKEND_DIR, ".env"))

# ── Database Initialization ────────────────────────────────────────────
try:
    from database import engine
    import models
    models.Base.metadata.create_all(bind=engine)
    print("[NEXUS DB] Database initialized successfully.")
except Exception as e:
    print(f"[NEXUS DB ERROR] Failed to initialize database: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Nexus-Guide"],
)

# ── Root & HTML page routes (BEFORE StaticFiles mount) ─────────────────
@app.get("/", include_in_schema=False)
def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/dashboard", include_in_schema=False)
@app.get("/dashboard.html", include_in_schema=False)
def dashboard_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "dashboard.html"))

# Groq: GROQ_API_KEY in backend/.env (or tokens.txt for backward compatibility)
def _load_groq_key() -> str:
    env_key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if env_key:
        return env_key
    token_path = os.path.join(BACKEND_DIR, "tokens.txt")
    if os.path.exists(token_path):
        with open(token_path, "r", encoding="utf-8") as f:
            for line in f:
                if "GROQ_API_KEY=" in line:
                    return line.split("=", 1)[1].strip()
    return ""


import base64

GROQ_KEY = _load_groq_key()

GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
SLACK_TOKEN   = os.environ.get("SLACK_TOKEN", "")
JIRA_DOMAIN   = os.environ.get("JIRA_DOMAIN", "")
JIRA_EMAIL    = os.environ.get("JIRA_EMAIL", "")
JIRA_TOKEN    = os.environ.get("JIRA_TOKEN", "")
GITHUB_OWNER  = os.environ.get("GITHUB_OWNER", "")
GITHUB_REPO   = os.environ.get("GITHUB_REPO", "")


# ── Team Calendar ──────────────────────────────────────────────────────
# token.json is issued for architkumar2928@gmail.com.
# "primary" queries that account's calendar. Add other calendar IDs only
# if they have been shared with the authenticated account.
TEAM_CALENDAR_EMAILS = [
    "primary",                          # = authenticated user (architkumar2928)
    # "imthedangersaymyname@gmail.com", # 404 — not shared yet; re-enable after sharing
]

# GitHub login → real name mapping (add yours here so the AI can
# mention names instead of GitHub handles)
GITHUB_NAME_MAP: dict[str, str] = {
    # "github-login": "Display Name",
}

groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
GROQ_MODEL  = "llama-3.3-70b-versatile"
slack = WebClient(token=SLACK_TOKEN)

NEXUS_GUIDE_SYSTEM = """You are the Nexus AI Guide. You speak for the LIVE dashboard data in the JSON below — not as a help manual.

ABSOLUTE RULES (violations are failures):
1. NEVER tell the user to "check the dashboard", "open Nexus", "look at the UI", "click Run Health Check", or "go see the calendar". They already have the app open. YOU must report the numbers and names here.
2. NEVER answer workload or "who is busiest" / "today" / "tomorrow" with generic instructions. Answer with CONCRETE facts from the JSON: people names, ticket counts, PR counts, meeting counts, ticket keys from jira.tickets when relevant.
3. The field dashboard_answer_skeleton.START_HERE is pre-computed from the same APIs as the dashboard. Your FIRST 1-2 sentences MUST include those facts (you may rephrase but MUST keep every number and name accurate).
4. "Busiest" for engineering load = workload_ranking_for_chat (Jira tickets + GitHub PRs), current snapshot. For "tomorrow": give calendar.events_tomorrow + meetings_count_tomorrow; if events have no attendee names in JSON, say meeting load is calendar-wide, not per person.
5. If a section has "error" or data is empty, say exactly that integration failed or returned nothing — do not invent filler.

Product context (only when asked "what is Nexus / MCP?"):
- Nexus pulls live Jira, GitHub, Slack, Calendar; no database. MCP-style = tools give the model real context. FastAPI on port 8008.

Tone: concise senior engineering lead. Use bullets for long answers."""

def ask_gemini(prompt, json_mode=False):
    if not groq_client:
        raise RuntimeError(
            "Groq API key not configured. Set GROQ_API_KEY in backend/.env (see .env.example)."
        )
    params = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }
    if json_mode:
        params["response_format"] = {"type": "json_object"}
        params["messages"].insert(0, {"role": "system", "content": "You are a sprint health AI. Always respond with valid JSON only, no markdown, no explanation."})
    
    chat = groq_client.chat.completions.create(**params)
    return chat.choices[0].message.content

def hours_ago(date_str):
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    diff = datetime.now(timezone.utc) - dt
    return round(diff.total_seconds() / 3600, 1)

@app.get("/api/github-stats")
def github_stats():
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls"
        response = requests.get(url, headers=headers, timeout=5)
        prs = response.json()
        if not isinstance(prs, list):
            return {"open_prs": 0, "failing_ci": 0,
                    "stale_reviews": 0, "authors": {}, "error": str(prs)}
        open_prs    = len(prs)
        stale       = sum(1 for pr in prs
                          if hours_ago(pr["created_at"]) > 24)
        no_reviewer = sum(1 for pr in prs
                          if not pr.get("requested_reviewers"))

        # Count open PRs per author (GitHub login → real name if mapped)
        authors: dict[str, int] = {}
        for pr in prs:
            login = pr.get("user", {}).get("login", "unknown")
            name  = GITHUB_NAME_MAP.get(login, login)
            authors[name] = authors.get(name, 0) + 1

        return {
            "open_prs":      open_prs,
            "failing_ci":    no_reviewer,
            "stale_reviews": stale,
            "authors":       authors,   # {name: pr_count}
        }
    except Exception as e:
        return {"open_prs": 0, "failing_ci": 0, "stale_reviews": 0, "authors": {}, "error": str(e)}

@app.get("/api/slack-stats")
def slack_stats():
    try:
        channels = ["dev-help", "backend"]
        unanswered = 0
        for ch_name in channels:
            result = slack.conversations_list()
            ch_id = next((c["id"] for c in result["channels"]
                          if c["name"] == ch_name), None)
            if ch_id:
                msgs = slack.conversations_history(channel=ch_id, limit=20)
                unanswered += sum(1 for m in msgs["messages"]
                                  if "?" in m.get("text","")
                                  and not m.get("reply_count", 0))
        return {
            "unanswered_messages": unanswered,
            "blocked_devs": 1 if unanswered > 1 else 0,
            "channels_monitored": len(channels)
        }
    except Exception as e:
        return {"unanswered_messages": 0, "blocked_devs": 0,
                "channels_monitored": 0, "error": str(e)}

@app.get("/api/jira-stats")
def jira_stats():
    try:
        # Atlassian removed /rest/api/3/search (HTTP 410).
        # New endpoint: /rest/api/3/search/jql
        url = f"https://{JIRA_DOMAIN}/rest/api/3/search/jql"
        params = {
            "jql":        "project=SCRUM ORDER BY created DESC",
            # TODO: restore sprint filter once confirmed working:
            # "jql":      "project=SCRUM AND sprint in openSprints()",
            "maxResults": 50,
            "fields":     "summary,status,assignee,duedate,priority,issuetype"
        }
        auth = (JIRA_EMAIL, JIRA_TOKEN)
        raw = requests.get(url, params=params, auth=auth, timeout=10)
        print(f"[JIRA DEBUG] HTTP {raw.status_code}")
        resp = raw.json()
        print(f"[JIRA DEBUG] Response keys: {list(resp.keys())}")
        issues = resp.get("issues", [])
        print(f"[JIRA DEBUG] Issues found: {len(issues)}")
        if issues:
            print(f"[JIRA DEBUG] First issue keys: {list(issues[0].keys())}")
            print(f"[JIRA DEBUG] First issue fields: {list(issues[0].get('fields', {}).keys())}")

        def _assignee(i):
            a = i.get("fields", {}).get("assignee")
            if a and isinstance(a, dict):
                return a.get("displayName") or a.get("name") or "Unassigned"
            return "Unassigned"

        def _role(i):
            itype = i.get("fields", {}).get("issuetype", {})
            if isinstance(itype, dict):
                return itype.get("name", "Task") or "Task"
            return "Task"

        def _status_name(i):
            s = i.get("fields", {}).get("status", {})
            if isinstance(s, dict):
                return s.get("name", "Unknown")
            return "Unknown"

        tickets = [{
            "id":       i["key"],
            "title":    i.get("fields", {}).get("summary", "No title"),
            "status":   _status_name(i),
            "assignee": _assignee(i),
            "role":     _role(i),
            "due":      (i.get("fields", {}).get("duedate") or "TBD"),
        } for i in issues]

        # Build a lookup: ticket_id → assignee name
        assignee_map = {t["id"]: t["assignee"] for t in tickets}

        return {
            "total":        len(issues),
            "in_progress":  sum(1 for t in tickets if t["status"] == "In Progress"),
            "done":         sum(1 for t in tickets if t["status"] == "Done"),
            "blocked":      sum(1 for t in tickets
                               if t["status"] in ("Blocked", "Impediment")),
            "tickets":      tickets,
            "assignee_map": assignee_map,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"total": 0, "in_progress": 0, "done": 0, "blocked": 0,
                "tickets": [], "assignee_map": {}, "error": str(e)}

def get_all_stats():
    """Fetch GitHub, Jira, and Slack in parallel."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_gh    = executor.submit(github_stats)
        future_jira  = executor.submit(jira_stats)
        future_slack = executor.submit(slack_stats)
        return (future_gh.result(), future_jira.result(), future_slack.result())


def compute_live_team(gh: dict, jira: dict, slack_data: dict) -> dict:
    """
    Build a per-person workload dict from REAL API data.
    - Assignees come from Jira ticket `assignee.displayName`
    - PR count per person comes from GitHub PR `user.login` (mapped via GITHUB_NAME_MAP)
    - Status is computed from tickets + PRs combined
    - Unassigned tickets are tracked separately so the AI can flag them
    """
    team: dict[str, dict] = {}

    # 1. Seed from Jira assignees (including Unassigned bucket)
    for ticket in jira.get("tickets", []):
        name = ticket.get("assignee", "Unassigned")
        if name not in team:
            team[name] = {
                "role":                   ticket.get("role", "Team Member"),
                "prs_open":               0,
                "meetings_today":         0,
                "tickets_assigned":       [],
                "slack_messages_unanswered": 0,
                "status":                 "available",
            }
        team[name]["tickets_assigned"].append(ticket["id"])

    # 2. Overlay GitHub PR authors
    for gh_name, pr_count in gh.get("authors", {}).items():
        if gh_name in team:
            team[gh_name]["prs_open"] = pr_count
        else:
            team[gh_name] = {
                "role":                   "Engineer",
                "prs_open":               pr_count,
                "meetings_today":         0,
                "tickets_assigned":       [],
                "slack_messages_unanswered": 0,
                "status":                 "busy",
            }

    # 3. Compute status from workload
    for name, data in team.items():
        n = len(data["tickets_assigned"])
        p = data["prs_open"]
        if name == "Unassigned":
            data["status"] = "at_risk"  # unassigned = risk
        elif n >= 3 or p >= 2:
            data["status"] = "overloaded"
        elif n >= 2 or p >= 1:
            data["status"] = "busy"
        else:
            data["status"] = "available"

    return team


def compute_workload_ranking(live_team: dict) -> dict:
    """
    Deterministic busiest → lightest ordering for the AI (same inputs as dashboard team cards).
    Score = 2 * Jira tickets + open PRs for that person.
    """
    rows: list[dict] = []
    for name, d in live_team.items():
        if name == "Unassigned":
            continue
        nt = len(d.get("tickets_assigned") or [])
        pr = int(d.get("prs_open") or 0)
        score = nt * 2 + pr
        rows.append({
            "name": name,
            "jira_ticket_count": nt,
            "open_github_prs": pr,
            "composite_load_score": score,
            "nexus_status_flag": d.get("status"),
        })
    rows.sort(
        key=lambda x: (-x["composite_load_score"], -x["jira_ticket_count"], -x["open_github_prs"])
    )
    unassigned_n = len(live_team.get("Unassigned", {}).get("tickets_assigned") or [])
    return {
        "order_busiest_first": [r["name"] for r in rows],
        "order_lightest_first": [r["name"] for r in reversed(rows)],
        "explicit_busiest_person": rows[0]["name"] if rows else None,
        "explicit_lightest_load_person": rows[-1]["name"] if rows else None,
        "per_person": rows,
        "unassigned_jira_ticket_count": unassigned_n,
        "ranking_legend": "composite_load_score = jira_ticket_count*2 + open_github_prs",
    }


def fetch_guide_integration_snapshot():
    """GitHub + Jira + Slack + Calendar in parallel — same philosophy as the dashboard."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        f_gh = ex.submit(github_stats)
        f_ji = ex.submit(jira_stats)
        f_sl = ex.submit(slack_stats)
        f_ca = ex.submit(calendar_stats)
        gh, jira, slack_data, cal = f_gh.result(), f_ji.result(), f_sl.result(), f_ca.result()
    live_team = compute_live_team(gh, jira, slack_data)
    ranking = compute_workload_ranking(live_team)
    return gh, jira, slack_data, cal, live_team, ranking


def build_dashboard_answer_skeleton(
    gh: dict, jira: dict, slack_data: dict, cal: dict, ranking: dict
) -> dict:
    """Pre-written facts the LLM must lead with (stops generic 'check the UI' replies)."""
    lines: list[str] = []
    ppl = list(ranking.get("per_person") or [])
    busiest = ranking.get("explicit_busiest_person")
    lightest = ranking.get("explicit_lightest_load_person")
    ua = int(ranking.get("unassigned_jira_ticket_count") or 0)

    if busiest:
        row = next((x for x in ppl if x.get("name") == busiest), None)
        if row:
            lines.append(
                f"Busiest by Jira + GitHub load: {busiest} — "
                f"{row.get('jira_ticket_count', 0)} Jira tickets, "
                f"{row.get('open_github_prs', 0)} open PR(s), "
                f"composite score {row.get('composite_load_score', 0)} "
                f"(status flag: {row.get('nexus_status_flag', 'n/a')})."
            )
    if lightest and lightest != busiest:
        row = next((x for x in ppl if x.get("name") == lightest), None)
        if row:
            lines.append(
                f"Lightest load: {lightest} — "
                f"{row.get('jira_ticket_count', 0)} Jira tickets, "
                f"{row.get('open_github_prs', 0)} open PR(s)."
            )
    if ua > 0:
        lines.append(f"Unassigned Jira work: {ua} ticket(s) with no assignee.")

    lines.append(
        f"GitHub snapshot: {gh.get('open_prs', 0)} open PRs; "
        f"{gh.get('failing_ci', 0)} with no reviewer; "
        f"{gh.get('stale_reviews', 0)} stale >24h."
    )
    lines.append(
        f"Jira snapshot: {jira.get('total', 0)} total, "
        f"{jira.get('in_progress', 0)} in progress, "
        f"{jira.get('done', 0)} done, {jira.get('blocked', 0)} blocked."
    )
    lines.append(
        f"Slack snapshot: {slack_data.get('unanswered_messages', 0)} unanswered question(s) "
        f"in monitored channels."
    )

    mct = cal.get("meetings_count")
    mht = cal.get("meetings_today")
    idt = cal.get("ist_date_today") or "n/a"
    idtm = cal.get("ist_date_tomorrow") or "n/a"
    lines.append(
        f"Calendar today ({idt}): "
        f"{mct if mct is not None else 0} event(s), "
        f"~{mht if mht is not None else 0}h timed meetings, "
        f"~{cal.get('focus_hours', 0)}h focus estimate."
    )
    mctm = cal.get("meetings_count_tomorrow")
    mhtm = cal.get("meetings_tomorrow")
    lines.append(
        f"Calendar tomorrow ({idtm}): "
        f"{mctm if mctm is not None else 0} event(s), "
        f"~{mhtm if mhtm is not None else 0}h timed meetings "
        f"(aggregate for linked calendar(s); per-person only if calendars are shared)."
    )
    hm = cal.get("heavy_meeting_days")
    if isinstance(hm, str) and "not authenticated" in hm.lower():
        lines.append("Calendar OAuth: not connected — meeting counts may be zero; connect Google in backend for real schedule data.")

    start_here = " ".join(lines) if lines else "No team ranking could be built (check integration errors in JSON)."

    return {
        "START_HERE": start_here,
        "ordered_busiest_first": ranking.get("order_busiest_first") or [],
        "ordered_lightest_first": ranking.get("order_lightest_first") or [],
    }


def build_guide_live_context_json(
    gh: dict, jira: dict, slack_data: dict, cal: dict, live_team: dict, ranking: dict
) -> str:
    tickets = list(jira.get("tickets") or [])
    if len(tickets) > 48:
        tickets = tickets[:48]
    skeleton = build_dashboard_answer_skeleton(gh, jira, slack_data, cal, ranking)
    snap = {
        "dashboard_answer_skeleton": skeleton,
        "github": {
            "open_prs": gh.get("open_prs"),
            "prs_with_no_reviewer_count": gh.get("failing_ci"),
            "stale_prs_over_24h": gh.get("stale_reviews"),
            "open_prs_by_author_display_or_login": gh.get("authors"),
            "error": gh.get("error"),
        },
        "jira": {
            "total": jira.get("total"),
            "in_progress": jira.get("in_progress"),
            "done": jira.get("done"),
            "blocked": jira.get("blocked"),
            "tickets": tickets,
            "error": jira.get("error"),
        },
        "slack": {
            "unanswered_questions": slack_data.get("unanswered_messages"),
            "blocked_devs_signal": slack_data.get("blocked_devs"),
            "channels_monitored": slack_data.get("channels_monitored"),
            "error": slack_data.get("error"),
        },
        "calendar": {
            "ist_date_today": cal.get("ist_date_today"),
            "ist_date_tomorrow": cal.get("ist_date_tomorrow"),
            "ooo_events_this_week": cal.get("ooo_count"),
            "meeting_hours_today": cal.get("meetings_today"),
            "focus_hours_estimate": cal.get("focus_hours"),
            "heavy_meeting_days_label": cal.get("heavy_meeting_days"),
            "meetings_count_today": cal.get("meetings_count"),
            "meetings_count_tomorrow": cal.get("meetings_count_tomorrow"),
            "meeting_hours_tomorrow": cal.get("meetings_tomorrow"),
            "events_today": cal.get("events_today"),
            "events_tomorrow": cal.get("events_tomorrow"),
        },
        "team_workload_merged_jira_github": live_team,
        "workload_ranking_for_chat": ranking,
    }
    return json.dumps(snap, indent=2, default=str)


@app.get("/api/sprint-health")
def sprint_health():
    import json
    gh, jira, slack_data = get_all_stats()
    live_team    = compute_live_team(gh, jira, slack_data)
    assignee_map = jira.get("assignee_map", {})

    # Build per-ticket context block for the AI
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ticket_lines = []
    unassigned_ids = []
    overdue_ids = []
    for t in jira.get("tickets", []):
        due = t.get("due", "TBD")
        is_overdue = (due != "TBD" and due < today_str and t["status"] != "Done")
        is_unassigned = (t["assignee"] == "Unassigned")
        flags = []
        if is_unassigned:
            flags.append("⚠ UNASSIGNED")
            unassigned_ids.append(t["id"])
        if is_overdue:
            flags.append("⚠ OVERDUE")
            overdue_ids.append(t["id"])
        flag_str = " | ".join(flags) if flags else "OK"
        ticket_lines.append(
            f"  - {t['id']}: \"{t['title']}\" | Status: {t['status']} | "
            f"Assignee: {t['assignee']} | Due: {due} | Flags: {flag_str}"
        )
    tickets_block = "\n".join(ticket_lines)

    prompt = f"""You are a sprint health AI analyzing REAL-TIME data. Today is {today_str}.

GitHub (live):
- Open PRs: {gh['open_prs']}
- Stale PRs (>24h without merge): {gh['stale_reviews']}
- PRs with no reviewer assigned: {gh['failing_ci']}
- PR authors: {gh.get('authors', {})}

Jira Sprint (live):
- Total: {jira['total']} | In Progress: {jira['in_progress']} | Done: {jira['done']}
- Unassigned tickets: {len(unassigned_ids)} ({', '.join(unassigned_ids) if unassigned_ids else 'none'})
- Overdue tickets: {len(overdue_ids)} ({', '.join(overdue_ids) if overdue_ids else 'none'})

Detailed tickets:
{tickets_block}

Slack (live):
- Unanswered questions: {slack_data['unanswered_messages']}
- Blocked developers: {slack_data['blocked_devs']}

Team workload:
{json.dumps(live_team, indent=2)}

IMPORTANT RULES:
1. For each ticket, write a SPECIFIC insight mentioning the ticket ID, actual assignee (or "Unassigned"), due date, and concrete risk reason.
2. Mark unassigned tickets as "high" risk — they need an owner immediately.
3. Mark overdue tickets as "high" risk — they are past deadline.
4. If a ticket is "In Progress" with no assignee, say exactly who needs to pick it up (or say it needs assignment).
5. If the assignee is a real name, mention them by name. If "Unassigned", say "No owner assigned — needs immediate assignment".
6. Do NOT invent team member names. Only use names that appear in the data above.
7. Completion percentage = (done / total) * 100.

Return ONLY this JSON:
{{
  "summary": {{
    "points_at_risk": <count of high+medium risk tickets>,
    "days_remaining": 4,
    "completion_pct": <integer 0-100>
  }},
  "tickets": [
    {{
      "id": "<exact Jira key like SCRUM-1>",
      "title": "<exact title from data above>",
      "risk": "<high|medium|low>",
      "sources": ["Jira"],
      "insight": "<specific one-sentence insight referencing assignee, due date, and risk>",
      "status": "<exact Jira status>",
      "assignee": "<exact assignee name or Unassigned>",
      "due": "<due date or TBD>"
    }}
  ]
}}
"""
    try:
        text = ask_gemini(prompt, json_mode=True)
        text = text.replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        # Inject assignee + due from real Jira data (AI might hallucinate names)
        jira_lookup = {t["id"]: t for t in jira.get("tickets", [])}
        for ticket in result.get("tickets", []):
            real = jira_lookup.get(ticket["id"])
            if real:
                ticket["assignee"] = real["assignee"]
                ticket["due"] = real["due"]
                ticket["status"] = real["status"]
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Fallback: return tickets from Jira directly with basic risk assessment
        fallback_tickets = []
        for t in jira.get("tickets", []):
            due = t.get("due", "TBD")
            is_overdue = (due != "TBD" and due < today_str and t["status"] != "Done")
            is_unassigned = (t["assignee"] == "Unassigned")
            if is_unassigned or is_overdue:
                risk = "high"
            elif t["status"] == "In Progress":
                risk = "medium"
            else:
                risk = "low"
            insight = ""
            if is_unassigned and is_overdue:
                insight = f"{t['id']} is unassigned AND overdue (due {due}) — critical risk."
            elif is_unassigned:
                insight = f"{t['id']} has no owner assigned — needs immediate assignment."
            elif is_overdue:
                insight = f"{t['id']} is past its {due} deadline, assigned to {t['assignee']}."
            else:
                insight = f"{t['id']} assigned to {t['assignee']}, status: {t['status']}."
            fallback_tickets.append({
                "id": t["id"], "title": t["title"],
                "risk": risk, "sources": ["Jira"],
                "insight": insight, "status": t["status"],
                "assignee": t["assignee"], "due": due,
            })
        done_count = jira.get("done", 0)
        total = jira.get("total", 1)
        return {
            "summary": {
                "points_at_risk": sum(1 for t in fallback_tickets if t["risk"] in ("high", "medium")),
                "days_remaining": 4,
                "completion_pct": round(done_count / max(total, 1) * 100),
            },
            "tickets": fallback_tickets,
            "error": str(e),
        }

@app.get("/api/sprint-summary")
def sprint_summary():
    health = sprint_health()
    alerts = []
    summary = health.get("summary", {})
    tickets = health.get("tickets", [])
    high_risk = [t for t in tickets if t["risk"] == "high"]
    if high_risk:
        alerts.append({"type": "danger",
                        "message": f"{len(high_risk)} ticket(s) at critical risk"})
    mid_risk = [t for t in tickets if t["risk"] == "medium"]
    if mid_risk:
        alerts.append({"type": "warning",
                        "message": f"{len(mid_risk)} ticket(s) need attention"})
    pct = summary.get("completion_pct", 0)
    if pct >= 60:
        alerts.append({"type": "success", "message": "Team velocity on track"})
    return {"alerts": alerts}

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# IST offset for correct "today" boundaries in India
IST = timezone(timedelta(hours=5, minutes=30))

def _get_calendar_creds():
    """Load, refresh and return valid Google Calendar credentials."""
    token_path = os.path.join(BACKEND_DIR, 'token.json')
    creds_path = os.path.join(BACKEND_DIR, 'credentials.json')

    # Base64 Env Var injection for Railway
    b64_token = os.environ.get("GOOGLE_TOKEN_JSON_B64")
    if b64_token and not os.path.exists(token_path):
        try:
            with open(token_path, "wb") as f:
                f.write(base64.b64decode(b64_token))
        except Exception as e:
            print(f"[CALENDAR DEBUG] Failed to decode GOOGLE_TOKEN_JSON_B64: {e}")

    b64_creds = os.environ.get("GOOGLE_CREDENTIALS_JSON_B64")
    if b64_creds and not os.path.exists(creds_path):
        try:
            with open(creds_path, "wb") as f:
                f.write(base64.b64decode(b64_creds))
        except Exception as e:
            print(f"[CALENDAR DEBUG] Failed to decode GOOGLE_CREDENTIALS_JSON_B64: {e}")

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, 'w') as f:
                    f.write(creds.to_json())
                print("[CALENDAR DEBUG] Token refreshed successfully")
            except Exception as e:
                print(f"[CALENDAR DEBUG] Token refresh failed: {e}")
                return None
        else:
            print("[CALENDAR DEBUG] No valid creds and cannot refresh")
            return None
    return creds

def _read_calendar_events(service, calendar_id: str, time_min: str, time_max: str) -> list:
    """Safely fetch events for a calendar id; returns [] on error."""
    try:
        result = service.events().list(
            calendarId=calendar_id, timeMin=time_min, timeMax=time_max,
            singleEvents=True, orderBy='startTime'
        ).execute()
        events = result.get('items', [])
        print(f"[CALENDAR DEBUG] {calendar_id}: {len(events)} events ({time_min} → {time_max})")
        return events
    except Exception as e:
        print(f"[CALENDAR DEBUG] Error fetching '{calendar_id}': {e}")
        return []

@app.get("/api/calendar-stats")
def calendar_stats():
    creds = _get_calendar_creds()
    if not creds:
        return {
            "ooo_count": 0, "heavy_meeting_days": "Not authenticated",
            "focus_hours": 0, "team_meetings": {}, "meetings_today": 0,
            "meetings_count": 0, "events_today": [],
            "ist_date_today": None, "ist_date_tomorrow": None,
            "meetings_tomorrow": 0, "meetings_count_tomorrow": 0, "events_tomorrow": [],
        }
    try:
        service = build('calendar', 'v3', credentials=creds)

        # Use IST-aware "today" so we match the user's local day
        now_ist       = datetime.now(IST)
        start_of_today = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_today   = start_of_today + timedelta(days=1)
        end_of_week    = start_of_today + timedelta(days=7)

        # Convert to ISO format strings for the Google API
        sot_iso  = start_of_today.isoformat()
        eot_iso  = end_of_today.isoformat()
        eow_iso  = end_of_week.isoformat()

        print(f"[CALENDAR DEBUG] IST now: {now_ist.isoformat()}")
        print(f"[CALENDAR DEBUG] Query range today: {sot_iso} → {eot_iso}")
        print(f"[CALENDAR DEBUG] Query range week:  {sot_iso} → {eow_iso}")

        # ── Week events (for OOO detection) ──────────────────────────
        all_week_events: list = []
        for cal_id in TEAM_CALENDAR_EMAILS:
            all_week_events.extend(
                _read_calendar_events(service, cal_id, sot_iso, eow_iso)
            )

        ooo_keywords = ('out of office', 'ooo', 'vacation', 'leave', 'pto', 'holiday')
        ooo_count = sum(
            1 for e in all_week_events
            if any(kw in e.get('summary', '').lower() for kw in ooo_keywords)
        )

        # ── Today's events per calendar ──────────────────────────────
        team_meetings: dict[str, float] = {}
        total_meeting_minutes = 0
        today_event_count = 0
        events_today_list: list[dict] = []

        for cal_id in TEAM_CALENDAR_EMAILS:
            events = _read_calendar_events(service, cal_id, sot_iso, eot_iso)
            mins = 0
            for e in events:
                summary = e.get('summary', '(no title)')
                start_raw = e.get('start', {})
                end_raw   = e.get('end', {})

                # Count every event (timed or all-day)
                today_event_count += 1

                # For duration calc, only use timed events (not all-day)
                start_dt_str = start_raw.get('dateTime')
                end_dt_str   = end_raw.get('dateTime')
                if start_dt_str and end_dt_str:
                    try:
                        s  = datetime.fromisoformat(start_dt_str.replace('Z', '+00:00'))
                        en = datetime.fromisoformat(end_dt_str.replace('Z', '+00:00'))
                        dur = (en - s).total_seconds() / 60
                        mins += dur
                        events_today_list.append({
                            "title":    summary,
                            "start":    start_dt_str,
                            "end":      end_dt_str,
                            "duration_min": round(dur),
                        })
                    except Exception as ex:
                        print(f"[CALENDAR DEBUG] Parse error for '{summary}': {ex}")
                else:
                    # All-day event
                    events_today_list.append({
                        "title":    summary,
                        "start":    start_raw.get('date', ''),
                        "end":      end_raw.get('date', ''),
                        "duration_min": 0,
                        "all_day":  True,
                    })

            team_meetings[cal_id] = round(mins / 60, 1)
            total_meeting_minutes += mins

        meetings_today_hrs = round(total_meeting_minutes / 60, 1)
        focus_hours = max(0, 8 - round(total_meeting_minutes / (60 * max(len(TEAM_CALENDAR_EMAILS), 1))))
        heavy_meeting_days = "Today" if total_meeting_minutes > 120 else "None"

        # ── Tomorrow (IST calendar day after today) ─────────────────
        start_tomorrow = end_of_today
        end_tomorrow = start_tomorrow + timedelta(days=1)
        sotm_iso = start_tomorrow.isoformat()
        eotm_iso = end_tomorrow.isoformat()
        events_tomorrow_list: list[dict] = []
        total_meeting_minutes_tm = 0.0
        tomorrow_event_count = 0

        for cal_id in TEAM_CALENDAR_EMAILS:
            for e in _read_calendar_events(service, cal_id, sotm_iso, eotm_iso):
                summary = e.get('summary', '(no title)')
                start_raw = e.get('start', {})
                end_raw = e.get('end', {})
                tomorrow_event_count += 1
                start_dt_str = start_raw.get('dateTime')
                end_dt_str = end_raw.get('dateTime')
                if start_dt_str and end_dt_str:
                    try:
                        s = datetime.fromisoformat(start_dt_str.replace('Z', '+00:00'))
                        en = datetime.fromisoformat(end_dt_str.replace('Z', '+00:00'))
                        dur = (en - s).total_seconds() / 60
                        total_meeting_minutes_tm += dur
                        events_tomorrow_list.append({
                            "title": summary,
                            "start": start_dt_str,
                            "end": end_dt_str,
                            "duration_min": round(dur),
                        })
                    except Exception as ex:
                        print(f"[CALENDAR DEBUG] Tomorrow parse error '{summary}': {ex}")
                        events_tomorrow_list.append({
                            "title": summary,
                            "start": start_dt_str,
                            "end": end_dt_str,
                            "duration_min": 0,
                        })
                else:
                    events_tomorrow_list.append({
                        "title": summary,
                        "start": start_raw.get('date', ''),
                        "end": end_raw.get('date', ''),
                        "duration_min": 0,
                        "all_day": True,
                    })

        meetings_tomorrow_hrs = round(total_meeting_minutes_tm / 60, 1)
        ist_date_today = start_of_today.strftime('%Y-%m-%d')
        ist_date_tomorrow = start_tomorrow.strftime('%Y-%m-%d')

        print(f"[CALENDAR DEBUG] Today: {today_event_count} events, {meetings_today_hrs}h meetings, OOO={ooo_count}")
        print(f"[CALENDAR DEBUG] Tomorrow: {tomorrow_event_count} events, {meetings_tomorrow_hrs}h timed meetings")

        return {
            "ooo_count":          ooo_count,
            "heavy_meeting_days": heavy_meeting_days,
            "focus_hours":        focus_hours,
            "meetings_today":     meetings_today_hrs,
            "meetings_count":     today_event_count,
            "team_meetings":      team_meetings,
            "events_today":       events_today_list,
            "ist_date_today":     ist_date_today,
            "ist_date_tomorrow":  ist_date_tomorrow,
            "meetings_tomorrow":  meetings_tomorrow_hrs,
            "meetings_count_tomorrow": tomorrow_event_count,
            "events_tomorrow":    events_tomorrow_list,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "ooo_count": 0, "heavy_meeting_days": str(e), "focus_hours": 0,
            "meetings_today": 0, "meetings_count": 0, "team_meetings": {},
            "events_today": [],
            "ist_date_today": None, "ist_date_tomorrow": None,
            "meetings_tomorrow": 0, "meetings_count_tomorrow": 0, "events_tomorrow": [],
        }

# (BaseModel already imported at top)

class ChatRequest(BaseModel):
    question: str


class GuideChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class GuideChatRequest(BaseModel):
    messages: list[GuideChatMessage]


def _guide_chat_deflection(text: str) -> bool:
    """True if the model ignored instructions and sent the user back to the UI."""
    if not text or len(text) < 30:
        return False
    t = text.lower()
    tells_to_go = any(
        p in t
        for p in (
            "check the dashboard",
            "check the nexus",
            "nexus dashboard",
            "run health check",
            "click ",
            "you can check",
            "you can see",
            "look at the",
            "open the dashboard",
            "go to the dashboard",
            "will display",
            "displays the team",
            "via oauth",
        )
    )
    if not tells_to_go:
        return False
    return any(
        p in t
        for p in ("dashboard", "health check", "calendar", "oauth", "schedule", "refresh")
    )


def _format_tomorrow_events_for_chat(cal: dict) -> str:
    ev = cal.get("events_tomorrow") if isinstance(cal, dict) else None
    if not ev:
        return ""
    lines = ["Tomorrow's scheduled items (from linked calendar(s), titles only):"]
    for e in ev[:20]:
        if not isinstance(e, dict):
            continue
        title = (e.get("title") or "(no title)").strip()
        dm = e.get("duration_min")
        if e.get("all_day"):
            lines.append(f"  • {title} (all-day)")
        else:
            lines.append(f"  • {title} ({dm} min)" if dm is not None else f"  • {title}")
    if len(ev) > 20:
        lines.append(f"  … and {len(ev) - 20} more")
    return "\n".join(lines)


# Helper to format tomorrow's schedule for the AI context
def _user_thread_context_lower(messages: list[GuideChatMessage]) -> str:
    parts = [m.content.strip().lower() for m in messages if m.role == "user"]
    return " ".join(parts)[-4000:]


@app.post("/api/guide-chat")
def guide_chat(request: GuideChatRequest):
    """Nexus AI Guide with live Jira/GitHub/Slack/Calendar snapshot (dashboard-equivalent facts)."""
    if not groq_client:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not set. Add it to backend/.env and restart the server.",
        )
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")
    last = request.messages[-1]
    if last.role != "user":
        raise HTTPException(status_code=400, detail="Last message must be from the user")

    live_dict: dict
    try:
        _gh, _ji, _sl, _ca, _team, _rank = fetch_guide_integration_snapshot()
        live_dict = json.loads(build_guide_live_context_json(_gh, _ji, _sl, _ca, _team, _rank))
    except Exception as e:
        er = str(e)
        empty_rank = {
            "per_person": [],
            "order_busiest_first": [],
            "order_lightest_first": [],
            "explicit_busiest_person": None,
            "explicit_lightest_load_person": None,
            "unassigned_jira_ticket_count": 0,
        }
        sk = build_dashboard_answer_skeleton(
            {"open_prs": 0, "failing_ci": 0, "stale_reviews": 0, "authors": {}, "error": er},
            {"total": 0, "in_progress": 0, "done": 0, "blocked": 0, "tickets": [], "error": er},
            {"unanswered_messages": 0, "blocked_devs": 0, "channels_monitored": 0, "error": er},
            {
                "meetings_today": 0,
                "meetings_count": 0,
                "focus_hours": 0,
                "events_today": [],
                "events_tomorrow": [],
                "meetings_tomorrow": 0,
                "meetings_count_tomorrow": 0,
                "ist_date_today": None,
                "ist_date_tomorrow": None,
                "heavy_meeting_days": er,
                "ooo_count": 0,
            },
            empty_rank,
        )
        sk["START_HERE"] = f"[Integration fetch failed] {er}\n" + sk["START_HERE"]
        live_dict = {
            "dashboard_answer_skeleton": sk,
            "github": {"error": er},
            "jira": {"error": er},
            "slack": {"error": er},
            "calendar": {"error": er},
            "workload_ranking_for_chat": empty_rank,
            "team_workload_merged_jira_github": {},
        }

    live_blob = json.dumps(live_dict, indent=2, default=str)
    _pre = (live_dict.get("dashboard_answer_skeleton") or {}).get("START_HERE", "").strip()
    _cal = live_dict.get("calendar") or {}
    _tomorrow_block = _format_tomorrow_events_for_chat(_cal)
    _rank = live_dict.get("workload_ranking_for_chat") or {}
    _order = _rank.get("order_busiest_first") or []

    snapshot_core = _pre
    if _tomorrow_block:
        snapshot_core = (snapshot_core + "\n\n" + _tomorrow_block).strip()
    snapshot_core += (
        "\n\nNote: Nexus does not receive per-attendee meeting counts from Google for each engineer — "
        "only the merged event list above for linked calendar(s). "
        "Who has the most *engineering* work right now is workload_ranking_for_chat (Jira + GitHub)."
    )

    system_content = (
        NEXUS_GUIDE_SYSTEM
        + "\n\n---\nCURRENT LIVE_DATA (JSON, refreshed this request):\n"
        + live_blob
        + "\n\n---\nFINAL: Answer in plain text. Copy the opening facts from dashboard_answer_skeleton.START_HERE "
        + "verbatim first, then add at most 4 short bullets. Never tell the user to open the app or dashboard."
    )
    groq_messages = [{"role": "system", "content": system_content}]
    for m in request.messages:
        groq_messages.append({"role": m.role, "content": m.content})

    try:
        chat = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=groq_messages,
            temperature=0.05,
            max_tokens=600,
        )
        llm = (chat.choices[0].message.content or "").strip()
        if _guide_chat_deflection(llm):
            llm = ""

        header = "Nexus live snapshot (same APIs as the dashboard, fetched for this message):\n\n"
        body = snapshot_core
        if llm:
            reply = (header + body + "\n\n—\n" + llm).strip()
        else:
            extra = ""
            if _order:
                extra = "\n\nBusiest → lightest (Jira+GitHub score): " + ", ".join(_order) + "."
            reply = (
                header
                + body
                + extra
                + "\n\n(The chat model tried to redirect you to the UI; that text was removed. "
                "Numbers above are from the server.)"
            ).strip()

        return {"reply": reply, "live_facts": snapshot_core}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.post("/api/chat")
def chat(request: ChatRequest):
    import json
    gh, jira, slack_data = get_all_stats()
    live_team    = compute_live_team(gh, jira, slack_data)
    assignee_map = jira.get("assignee_map", {})

    prompt = f"""
You are an expert engineering manager AI.
Analyze REAL-TIME data from GitHub, Jira, Slack and do 3 things:
1. DETECT cross-source blockers humans would miss
2. PREDICT sprint outcome with a confidence percentage
3. RECOMMEND specific actions with expected impact

Data:
- User Question: "{request.question}"
- GitHub: {gh['open_prs']} open PRs, {gh['stale_reviews']} stale 24h+,
  {gh['failing_ci']} with no reviewer
  PR authors: {gh.get('authors', {})}
- Jira tickets: {jira['tickets']}
- Slack: {slack_data['unanswered_messages']} unanswered help requests
- Days remaining in sprint: 4
- Real assignees (from Jira): {assignee_map}
- Real team workload: {live_team}

Rules:
- A ticket is HIGH risk if 2+ signals are bad simultaneously
- A ticket is MEDIUM risk if 1 signal is bad
- Always give a specific recommended action per ticket
- Predict sprint completion as a percentage
- Mention engineers BY REAL NAME from assignee_map

Return ONLY this JSON, no markdown:
{{
  "answer": "<Natural language response addressing the question directly>",
  "summary": {{
    "points_at_risk": <number>,
    "days_remaining": 4,
    "completion_pct": <0-100>,
    "prediction": "<one sentence sprint forecast>"
  }},
  "tickets": [
    {{
      "id": "<id>",
      "title": "<title>",
      "risk": "<high|medium|low>",
      "sources": ["GitHub","Jira","Slack"],
      "insight": "<why is this at risk with real assignee name>",
      "action": "<specific recommended action>",
      "status": "<jira status>"
    }}
  ]
}}
"""
    text = ask_gemini(prompt, json_mode=True)
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)

@app.get("/api/landing-stats")
def landing_stats():
    """
    Combined endpoint for the landing page — fetches all 4 data sources
    in parallel and returns a single JSON the frontend can drop into the UI.
    """
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        f_gh    = ex.submit(github_stats)
        f_jira  = ex.submit(jira_stats)
        f_slack = ex.submit(slack_stats)
        f_cal   = ex.submit(calendar_stats)
        gh      = f_gh.result()
        jira    = f_jira.result()
        sl      = f_slack.result()
        cal     = f_cal.result()

    return {
        "github": {
            "open_prs":      gh["open_prs"],
            "failing_ci":    gh["failing_ci"],
            "stale_reviews": gh["stale_reviews"],
        },
        "jira": {
            "total":       jira["total"],
            "in_progress": jira["in_progress"],
            "done":        jira["done"],
            "blocked":     jira.get("blocked", 0),
        },
        "slack": {
            "unanswered_messages": sl["unanswered_messages"],
            "blocked_devs":        sl["blocked_devs"],
            "channels_monitored":  sl["channels_monitored"],
        },
        "calendar": {
            "ooo_count":          cal["ooo_count"],
            "heavy_meeting_days": cal["heavy_meeting_days"],
            "focus_hours":        cal["focus_hours"],
            "meetings_today":     cal.get("meetings_today", 0),
        },
    }

# ── Serve static frontend files (MUST be last) ──────────────────────────
# All remaining requests that don't match an API route will be served
# from the ../frontend/ directory as static assets (CSS, JS, images, etc.)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")