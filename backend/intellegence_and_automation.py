"""
intelligence_and_automation.py
================================
FastAPI APIRouter for all AI-driven automation features.

Mount in backend.py with:
    from intellegence_and_automation import router as ia_router
    app.include_router(ia_router)

Features:
  1. Predictive Sprint Planning  — GET  /api/intelligence/predictive-planning
  2. Automated Blocker Resolution— GET  /api/intelligence/blocker-resolution/{ticket_id}
  3. Smart Rebalancing Engine    — GET  /api/intelligence/smart-rebalance
"""

import os
import json
import concurrent.futures
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from groq import Groq

# ── Router ─────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api/intelligence", tags=["Intelligence & Automation"])

# ── Shared config (mirrors backend.py; reads same .env) ────────────────────
BACKEND_DIR  = os.path.dirname(os.path.abspath(__file__))
SPRINT_HISTORY_PATH = os.path.join(BACKEND_DIR, "sprint_history.json")

def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()

GROQ_KEY     = _env("GROQ_API_KEY")
GROQ_MODEL   = "llama-3.3-70b-versatile"
GITHUB_TOKEN = _env("GITHUB_TOKEN")
GITHUB_OWNER = _env("GITHUB_OWNER")
GITHUB_REPO  = _env("GITHUB_REPO")
JIRA_DOMAIN  = _env("JIRA_DOMAIN")
JIRA_EMAIL   = _env("JIRA_EMAIL")
JIRA_TOKEN   = _env("JIRA_TOKEN", _env("JIRA_API_TOKEN"))
SLACK_TOKEN  = _env("SLACK_TOKEN")

groq_client  = Groq(api_key=GROQ_KEY) if GROQ_KEY else None


# ── Helpers ────────────────────────────────────────────────────────────────

def _groq(prompt: str, json_mode: bool = False, max_tokens: int = 1500) -> str:
    """Call Groq LLM; raises HTTPException 503 if key is missing."""
    if not groq_client:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY not set. Add it to backend/.env and restart.",
        )
    messages = [{"role": "user", "content": prompt}]
    params: dict = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    if json_mode:
        params["response_format"] = {"type": "json_object"}
        params["messages"].insert(
            0,
            {"role": "system", "content": "You are a sprint AI. Always reply with valid JSON only."},
        )
    resp = groq_client.chat.completions.create(**params)
    return resp.choices[0].message.content or ""


def _hours_ago(date_str: str) -> float:
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return round((datetime.now(timezone.utc) - dt).total_seconds() / 3600, 1)


def _gh_headers() -> dict:
    return {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}


def _jira_auth():
    return (JIRA_EMAIL, JIRA_TOKEN)


# ── Data fetchers (self-contained, so no circular import from backend.py) ──

def _fetch_github() -> dict:
    try:
        url  = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls"
        prs  = requests.get(url, headers=_gh_headers(), timeout=8).json()
        if not isinstance(prs, list):
            return {"open_prs": 0, "stale_reviews": 0, "no_reviewer": 0, "prs": [], "error": str(prs)}
        stale = [p for p in prs if _hours_ago(p["created_at"]) > 24]
        return {
            "open_prs":     len(prs),
            "stale_reviews": len(stale),
            "no_reviewer":  sum(1 for p in prs if not p.get("requested_reviewers")),
            "prs": [
                {
                    "number":    p["number"],
                    "title":     p["title"],
                    "author":    p.get("user", {}).get("login", "unknown"),
                    "age_hours": _hours_ago(p["created_at"]),
                    "has_reviewer": bool(p.get("requested_reviewers")),
                    "url":       p.get("html_url", ""),
                }
                for p in prs
            ],
        }
    except Exception as exc:
        return {"open_prs": 0, "stale_reviews": 0, "no_reviewer": 0, "prs": [], "error": str(exc)}


def _fetch_jira() -> dict:
    try:
        url = f"https://{JIRA_DOMAIN}/rest/api/3/search/jql"
        params = {
            "jql":        "project=SCRUM ORDER BY created DESC",
            "maxResults": 50,
            "fields":     "summary,status,assignee,duedate,priority,issuetype",
        }
        raw    = requests.get(url, params=params, auth=_jira_auth(), timeout=10)
        issues = raw.json().get("issues", [])

        def assignee(i):
            a = i.get("fields", {}).get("assignee")
            return (a.get("displayName") or a.get("name") or "Unassigned") if a else "Unassigned"

        def status_name(i):
            s = i.get("fields", {}).get("status", {})
            return s.get("name", "Unknown") if isinstance(s, dict) else "Unknown"

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tickets = []
        for i in issues:
            due = i.get("fields", {}).get("duedate") or "TBD"
            tickets.append({
                "id":         i["key"],
                "title":      i.get("fields", {}).get("summary", ""),
                "status":     status_name(i),
                "assignee":   assignee(i),
                "due":        due,
                "is_overdue": due != "TBD" and due < today,
            })

        done_count = sum(1 for t in tickets if t["status"] == "Done")
        return {
            "total":       len(tickets),
            "in_progress": sum(1 for t in tickets if t["status"] == "In Progress"),
            "done":        done_count,
            "blocked":     sum(1 for t in tickets if t["status"] in ("Blocked", "Impediment")),
            "tickets":     tickets,
        }
    except Exception as exc:
        return {"total": 0, "in_progress": 0, "done": 0, "blocked": 0, "tickets": [], "error": str(exc)}


def _fetch_slack_unanswered() -> int:
    try:
        from slack_sdk import WebClient
        client   = WebClient(token=SLACK_TOKEN)
        channels = ["dev-help", "backend"]
        count    = 0
        for ch_name in channels:
            result = client.conversations_list()
            ch_id = next((c["id"] for c in result["channels"] if c["name"] == ch_name), None)
            if ch_id:
                msgs = client.conversations_history(channel=ch_id, limit=20)
                count += sum(
                    1 for m in msgs["messages"]
                    if "?" in m.get("text", "") and not m.get("reply_count", 0)
                )
        return count
    except Exception:
        return 0


def _load_sprint_history() -> list[dict]:
    """Load historical sprint health snapshots from sprint_history.json."""
    if not os.path.exists(SPRINT_HISTORY_PATH):
        return []
    try:
        with open(SPRINT_HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_sprint_history(history: list[dict]) -> None:
    """Persist sprint history back to disk."""
    try:
        with open(SPRINT_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, default=str)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 1 — Predictive Sprint Planning
# GET /api/intelligence/predictive-planning
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/predictive-planning")
def predictive_sprint_planning():
    """
    Analyses the *current* sprint snapshot + historical sprint_history.json
    and returns an AI forecast:
      - Predicted completion % by sprint end
      - Capacity score for next sprint
      - Risk warnings (OOO, heavy meetings, overloaded engineers)
      - Concrete recommendations before the next sprint starts
    """
    # Fetch current data in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        f_gh   = ex.submit(_fetch_github)
        f_jira = ex.submit(_fetch_jira)
        gh, jira = f_gh.result(), f_jira.result()

    history  = _load_sprint_history()
    today    = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Snapshot current state into history (keep last 10)
    snapshot = {
        "date":        today,
        "total":       jira["total"],
        "done":        jira["done"],
        "in_progress": jira["in_progress"],
        "blocked":     jira["blocked"],
        "open_prs":    gh["open_prs"],
        "stale_prs":   gh["stale_reviews"],
        "completion_pct": round(jira["done"] / max(jira["total"], 1) * 100),
    }
    history.append(snapshot)
    history = history[-10:]
    _save_sprint_history(history)

    # Build velocity trend text for the AI
    if len(history) >= 2:
        trend_lines = []
        for h in history[-5:]:
            trend_lines.append(
                f"  {h['date']}: {h['completion_pct']}% done "
                f"({h['done']}/{h['total']} tickets, {h.get('blocked', 0)} blocked)"
            )
        trend_text = "\n".join(trend_lines)
        avg_done_per_day = sum(h["done"] for h in history) / max(len(history), 1)
    else:
        trend_text = "  No historical data yet — this is the first snapshot."
        avg_done_per_day = 0

    prompt = f"""You are a sprint planning AI. Analyze these REAL metrics and return a predictive plan.

TODAY: {today}

=== CURRENT SPRINT (live) ===
- Total tickets: {jira['total']}
- Done: {jira['done']}  |  In Progress: {jira['in_progress']}  |  Blocked: {jira['blocked']}
- Completion so far: {snapshot['completion_pct']}%
- Open GitHub PRs: {gh['open_prs']}  |  Stale PRs (>24h): {gh['stale_reviews']}  |  No Reviewer: {gh['no_reviewer']}

=== HISTORICAL SNAPSHOTS (past sprints / days) ===
{trend_text}
Average tickets done per snapshot: {round(avg_done_per_day, 1)}

=== TICKETS (status summary) ===
{json.dumps([{{ "id": t["id"], "status": t["status"], "assignee": t["assignee"], "due": t["due"], "overdue": t["is_overdue"] }} for t in jira["tickets"][:20]], indent=2)}

Based on this data, return ONLY this JSON:
{{
  "predicted_completion_pct": <integer 0-100, where sprint will likely end>,
  "confidence": "<high|medium|low>",
  "capacity_score_next_sprint": <integer 1-10, recommended ticket capacity>,
  "sprint_outcome": "<one sentence: will you finish or not, and why>",
  "risk_warnings": [
    "<specific risk 1 with real ticket IDs or engineer names>",
    "<specific risk 2>",
    "<specific risk 3 if any>"
  ],
  "recommendations": [
    "<actionable recommendation 1 for this or next sprint>",
    "<actionable recommendation 2>",
    "<actionable recommendation 3>"
  ],
  "velocity_trend": "<improving|declining|stable>",
  "days_to_completion_estimate": <integer, days from today to likely finish all tickets>
}}"""

    raw = _groq(prompt, json_mode=True)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"error": "AI response could not be parsed", "raw": raw}

    return {
        "feature":    "Predictive Sprint Planning",
        "generated":  today,
        "live_snapshot": snapshot,
        "history_snapshots_used": len(history),
        "prediction": result,
    }


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 2 — Automated Blocker Resolution
# GET /api/intelligence/blocker-resolution/{ticket_id}
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/blocker-resolution/{ticket_id}")
def automated_blocker_resolution(ticket_id: str):
    """
    For a given Jira ticket ID (e.g. SCRUM-12), Nexus:
      - Finds the ticket details
      - Cross-correlates with open PRs on GitHub
      - Identifies the exact blocker cause
      - Suggests a specific, actionable fix including who should do it
      - Drafts a ready-to-post Slack message to unblock the team
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        f_gh   = ex.submit(_fetch_github)
        f_jira = ex.submit(_fetch_jira)
        gh, jira = f_gh.result(), f_jira.result()

    # Find the specific ticket
    ticket = next((t for t in jira["tickets"] if t["id"].upper() == ticket_id.upper()), None)
    if not ticket:
        raise HTTPException(
            status_code=404,
            detail=f"Ticket {ticket_id} not found in the current Jira sprint (top 50 tickets checked).",
        )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Find related PRs (title overlap or same author as assignee)
    assignee_lower = ticket["assignee"].lower()
    related_prs = [
        p for p in gh["prs"]
        if ticket_id.upper() in p["title"].upper()
        or any(word in p["title"].lower() for word in ticket["title"].lower().split()[:3] if len(word) > 4)
        or assignee_lower in p["author"].lower()
    ]

    # Build Slack unanswered count
    unanswered_slack = _fetch_slack_unanswered()

    prompt = f"""You are Nexus, an engineering blocker resolution AI. Diagnose and resolve this specific blocker.

TODAY: {today}

=== BLOCKED TICKET ===
ID: {ticket['id']}
Title: {ticket['title']}
Status: {ticket['status']}
Assignee: {ticket['assignee']}
Due Date: {ticket['due']}
Overdue: {ticket['is_overdue']}

=== RELATED GITHUB PRs ===
{json.dumps(related_prs, indent=2) if related_prs else "No related PRs found."}

=== SPRINT CONTEXT ===
- Total open PRs: {gh['open_prs']}
- Stale PRs (>24h): {gh['stale_reviews']}
- PRs with no reviewer: {gh['no_reviewer']}
- Unanswered Slack questions: {unanswered_slack}

=== ALL OPEN TICKETS (for cross-reference) ===
{json.dumps([{{ "id": t["id"], "status": t["status"], "assignee": t["assignee"] }} for t in jira["tickets"][:15]], indent=2)}

Diagnose the blocker and return ONLY this JSON:
{{
  "blocker_diagnosis": "<1-2 sentences: exactly what is blocking this ticket and why>",
  "root_cause": "<technical root cause: missing reviewer / overdue dependency / unassigned / etc.>",
  "severity": "<critical|high|medium|low>",
  "estimated_unblock_time": "<e.g. 2 hours, 1 day>",
  "resolution_steps": [
    {{
      "step": 1,
      "action": "<specific action>",
      "owner": "<who should do this — use real assignee name if known>",
      "time_estimate": "<e.g. 15 min>"
    }},
    {{
      "step": 2,
      "action": "<next action>",
      "owner": "<owner>",
      "time_estimate": "<time>"
    }}
  ],
  "pr_action": "<specific PR action if a PR is involved, else null>",
  "slack_message_draft": "<ready-to-paste Slack message to unblock the team — mention ticket ID, assignee, and ask for specific help>",
  "prevent_recurrence": "<one sentence on how to prevent this type of blocker in future sprints>"
}}"""

    raw = _groq(prompt, json_mode=True)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"error": "AI response could not be parsed", "raw": raw}

    return {
        "feature":      "Automated Blocker Resolution",
        "ticket_id":    ticket["id"],
        "ticket_title": ticket["title"],
        "ticket_data":  ticket,
        "related_prs":  related_prs,
        "resolution":   result,
    }


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE 3 — Smart Rebalancing Engine
# GET /api/intelligence/smart-rebalance
# ══════════════════════════════════════════════════════════════════════════════

class RebalancePlan(BaseModel):
    from_engineer: str
    to_engineer: str
    ticket_id: str
    reason: str


@router.get("/smart-rebalance")
def smart_rebalancing_engine():
    """
    Analyses team workload from Jira + GitHub and suggests an optimal
    redistribution of tickets:
      - Identifies overloaded and underloaded engineers
      - Recommends specific ticket moves with justification
      - Drafts a Slack announcement for the team
      - Estimates the improvement in sprint completion after rebalancing
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        f_gh   = ex.submit(_fetch_github)
        f_jira = ex.submit(_fetch_jira)
        gh, jira = f_gh.result(), f_jira.result()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Build per-engineer workload
    team: dict[str, dict] = {}

    for ticket in jira["tickets"]:
        name = ticket.get("assignee", "Unassigned")
        if name not in team:
            team[name] = {"tickets": [], "prs": 0, "status": "available"}
        team[name]["tickets"].append({
            "id":        ticket["id"],
            "title":     ticket["title"],
            "status":    ticket["status"],
            "due":       ticket["due"],
            "overdue":   ticket["is_overdue"],
        })

    # Overlay GitHub PR counts
    for pr in gh["prs"]:
        author = pr["author"]
        if author in team:
            team[author]["prs"] += 1
        else:
            team[author] = {"tickets": [], "prs": 1, "status": "available"}

    # Compute composite load score per engineer
    scored = []
    for name, data in team.items():
        if name == "Unassigned":
            continue
        nt    = len(data["tickets"])
        pr    = data["prs"]
        score = nt * 2 + pr
        status = "overloaded" if score >= 6 else ("busy" if score >= 3 else "available")
        team[name]["status"] = status
        scored.append({
            "name":         name,
            "ticket_count": nt,
            "pr_count":     pr,
            "load_score":   score,
            "status":       status,
            "tickets":      data["tickets"],
        })

    scored.sort(key=lambda x: -x["load_score"])
    unassigned_tickets = [
        t for t in jira["tickets"] if t["assignee"] == "Unassigned"
    ]

    prompt = f"""You are Nexus, a sprint rebalancing AI. Suggest an optimal rebalancing of work.

TODAY: {today}
SPRINT STATS: {jira['total']} total, {jira['done']} done, {jira['blocked']} blocked

=== TEAM WORKLOAD (sorted busiest first) ===
{json.dumps(scored, indent=2)}

=== UNASSIGNED TICKETS ({len(unassigned_tickets)}) ===
{json.dumps(unassigned_tickets, indent=2)}

Rules:
- Only move tickets that are NOT "Done"
- Never move to "Unassigned"
- Overloaded = load_score >= 6, Available = load_score <= 2
- Prioritize unblocking overdue tickets first
- Max 3 ticket moves to keep changes manageable

Return ONLY this JSON:
{{
  "team_summary": [
    {{
      "name": "<engineer name>",
      "current_load": <load_score>,
      "status": "<overloaded|busy|available>",
      "ticket_count": <number>
    }}
  ],
  "rebalancing_moves": [
    {{
      "ticket_id": "<SCRUM-X>",
      "ticket_title": "<title>",
      "from_engineer": "<current assignee or Unassigned>",
      "to_engineer": "<target engineer name>",
      "reason": "<why this specific move helps the sprint>"
    }}
  ],
  "projected_improvement": "<one sentence: how completion % or velocity improves after these moves>",
  "completion_pct_before": <integer>,
  "completion_pct_after_estimate": <integer>,
  "slack_announcement": "<ready-to-paste Slack message announcing the rebalancing — mention each move with @names>",
  "warning": "<any risk to flag, e.g. if no available engineers exist, else null>"
}}"""

    raw = _groq(prompt, json_mode=True)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"error": "AI response could not be parsed", "raw": raw}

    return {
        "feature":            "Smart Rebalancing Engine",
        "generated":          today,
        "engineers_analysed": len(scored),
        "unassigned_tickets": len(unassigned_tickets),
        "team_workload":      scored,
        "rebalancing_plan":   result,
    }


# ══════════════════════════════════════════════════════════════════════════════
# BONUS — Combined Intelligence Dashboard
# GET /api/intelligence/dashboard
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard")
def intelligence_dashboard():
    """
    Runs all 3 intelligence features in parallel and returns a combined
    overview for a single-call summary.

    Useful for a dedicated 'AI Insights' panel in the frontend.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        f_plan     = ex.submit(predictive_sprint_planning)
        f_rebalance = ex.submit(smart_rebalancing_engine)
        plan      = f_plan.result()
        rebalance = f_rebalance.result()

    # Grab the first high-risk ticket for a quick blocker resolution sample
    blocker_sample = None
    jira = _fetch_jira()
    for ticket in jira.get("tickets", []):
        if ticket["is_overdue"] or ticket["status"] in ("Blocked", "Impediment"):
            try:
                blocker_sample = automated_blocker_resolution(ticket["id"])
            except Exception:
                pass
            break

    return {
        "feature": "Intelligence Dashboard (All 3 Features)",
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "predictive_planning":       plan,
        "smart_rebalancing":         rebalance,
        "blocker_resolution_sample": blocker_sample,
    }
