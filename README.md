# Nexus — Sprint Intelligence Platform

## What is Nexus?

Nexus is an AI-powered sprint intelligence platform built on Anthropic's Model Context Protocol. It monitors **GitHub**, **Jira**, **Slack**, and **Google Calendar** simultaneously — cross-correlating signals across all four tools to detect sprint blockers before they surface at standup.

Instead of telling teams what already happened, Nexus tells them **what is about to go wrong** — and exactly **who needs to act right now**.

---

## The Problem

Engineering teams lose **40% of their working time** to coordination overhead. The average blocker sits undetected for **48 hours** before someone mentions it at standup. By then the sprint is already failing.

The signals were always there:
- A PR aging without a reviewer
- A Jira ticket stuck in progress past its due date
- An engineer asking for help twice in Slack with no response
- A key assignee buried in back-to-back meetings

No human can monitor four tools simultaneously for an entire team. **Nexus can.**

---

## Live Demo

**Production URL:** https://nexus-production-103d.up.railway.app/

**Dashboard:** https://nexus-production-103d.up.railway.app/dashboard

---

## Features

### Cross-Source Blocker Detection
AI reasons across GitHub, Jira, Slack, and Calendar simultaneously to find connections no single tool would catch.

```
PR open 38h with no reviewer
+  Jira ticket due tomorrow
+  Engineer asked for help twice in Slack
+  Assignee has 4 meetings today
= CRITICAL BLOCKER — Nexus catches this. Standup doesn't.
```

### Live Sprint Dashboard
Real-time ticket cards with AI-generated risk levels:
- 🔴 **AT RISK** — Critical blockers needing immediate action
- 🟡 **WATCH** — Items trending toward problems
- 🟢 **ON TRACK** — Everything moving smoothly

### Named Engineer Recommendations
Every insight identifies a specific engineer and recommends a specific action:

> *"Priya Sharma is overloaded with 4 meetings today and 2 open PRs. Assign Karan Singh as reviewer for AUTH-412 immediately — he has the most availability."*

### Sprint Outcome Prediction
AI forecasts sprint completion probability based on current velocity, remaining tickets, and team availability.

### Ask Nexus — Natural Language Chat
Team members ask any question in plain English and receive specific data-driven answers:

> *"Who is most overloaded right now?"*
> *"Will we finish the sprint?"*
> *"What's blocking AUTH-412?"*

### Automated Slack Alerts
When a critical blocker is detected, Nexus automatically posts an alert to your team's Slack channel — no human monitoring required.

### Sprint Velocity Trending
Historical health score tracking shows the sprint trajectory over time so teams see problems developing before they explode.

### Team Workload Analysis
Visual breakdown of each engineer's load score with AI recommendations for rebalancing work across the team.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Backend | Python FastAPI |
| AI Model | Groq API — Llama 3.3 70B |
| MCP Server | TypeScript, Node.js, Anthropic MCP SDK |
| GitHub Integration | GitHub REST API |
| Jira Integration | Atlassian REST API v3 |
| Slack Integration | Slack SDK for Python |
| Calendar Integration | Google Calendar API |
| Backend Deployment | Railway |
| Frontend Deployment | Vercel |

---

## MCP Architecture

Nexus is built on Anthropic's Model Context Protocol as its **core architecture** — not as an afterthought.

### Why MCP?

Without MCP, AI answers from static training data. With MCP, our AI calls **live tools** and reasons across real data fetched seconds ago. It's the difference between an AI that *knows things* and an AI that *sees things*.

### MCP Tools

```typescript
get_sprint_health()
// Returns all Jira tickets with AI risk scores,
// named insights, and recommended actions.
// Cross-correlates GitHub + Jira + Slack + Calendar.

get_stale_prs()
// Returns open GitHub PRs with age, reviewer status,
// CI pipeline results, and commit recency.

get_team_workload()
// Returns engineer availability scores based on
// GitHub commits, Slack activity, and Calendar load.
// Includes AI rebalancing recommendations.

ask_nexus(question: string)
// Accepts any natural language question about
// the sprint and returns a specific, data-driven
// answer using live data from all four sources.
```

### Transport Support
- **Streamable HTTP** — for modern MCP clients
- **Server-Sent Events (SSE)** — for legacy compatibility

### What Makes Nexus MCP Different

| Feature | Typical MCP Server | Nexus MCP Server |
|---------|-------------------|-----------------|
| Tools connected | 1 | 4 simultaneously |
| Reasoning | Single source | Cross-source |
| Output | Raw data | Named recommendations |
| Behavior | Reactive | Proactive |
| Alerts | None | Automatic Slack posts |

---

## System Architecture

```
┌─────────────────────────────────┐
│     React Frontend              │
│     nexus.vercel.app            │
└──────────────┬──────────────────┘
               │ fetch()
┌──────────────▼──────────────────┐
│     TypeScript MCP Server       │
│     Anthropic MCP SDK           │
│     SSE + Streamable HTTP       │
└──────────────┬──────────────────┘
               │ HTTP
┌──────────────▼──────────────────┐
│     Python FastAPI Backend      │
│     nexus-backend.railway.app   │
└──────┬───────┬──────┬───────┬───┘
       │       │      │       │
   GitHub   Jira   Slack  Calendar
   REST     REST   SDK    OAuth2
   API      API v3        
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/github-stats` | Open PRs, stale reviews, CI failures |
| GET | `/api/jira-stats` | Sprint tickets, due dates, status |
| GET | `/api/slack-stats` | Unanswered messages, blocked devs |
| GET | `/api/calendar-stats` | OOO count, meeting load, focus hours |
| GET | `/api/sprint-health` | Full AI analysis across all 4 tools |
| GET | `/api/team-workload` | Engineer load scores + recommendations |
| GET | `/api/sprint-history` | Historical health score snapshots |
| GET | `/api/sprint-summary` | Hero section alert bullets |
| POST | `/api/chat` | Natural language Q&A about sprint |

---

## Getting Started

### Prerequisites

```
Python 3.10+
Node.js 18+
npm or yarn
```

### 1. Clone the repository

```bash
git clone https://github.com/PARASAMANI-DEV/nexus-backend
cd nexus-backend
```

### 2. Set up Python backend

```bash
cd backend
pip install -r requirements.txt
```

Create a `.env` file in the backend folder:

```env
GITHUB_TOKEN=ghp_your_github_token
SLACK_TOKEN=xoxb_your_slack_bot_token
GROQ_API_KEY=gsk_your_groq_api_key
JIRA_API_TOKEN=your_jira_api_token
JIRA_EMAIL=your@email.com
JIRA_DOMAIN=yourworkspace.atlassian.net
GITHUB_OWNER=your_github_username
GITHUB_REPO=your_repo_name
```

Run the backend:

```bash
python -m uvicorn backend:app --reload --port 8008
```

### 3. Set up MCP Server

```bash
cd mcp-server
npm install
npm run dev
```

### 4. Set up Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`

### 5. Configure Google Calendar

Place your `credentials.json` file (downloaded from Google Cloud Console) in the backend folder.

On first run, a browser window will open asking you to authorize Calendar access. This happens once — the token is saved automatically.

---

## Environment Variables

### Backend (.env)

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub Personal Access Token (repo scope) |
| `SLACK_TOKEN` | Slack Bot Token (xoxb-...) |
| `GROQ_API_KEY` | Groq API key (gsk-...) |
| `JIRA_API_TOKEN` | Atlassian API token |
| `JIRA_EMAIL` | Email associated with Jira account |
| `JIRA_DOMAIN` | Your Jira domain (workspace.atlassian.net) |
| `GITHUB_OWNER` | GitHub username or org name |
| `GITHUB_REPO` | Repository name to monitor |

---

## Deployment

### Backend — Railway

1. Push backend folder to GitHub
2. Go to [railway.app](https://railway.app)
3. New Project → Deploy from GitHub repo
4. Add all environment variables in Railway Variables tab
5. Railway auto-detects Python and deploys

### Frontend — Vercel

1. Push frontend folder to GitHub
2. Go to [vercel.com](https://vercel.com)
3. Add New Project → Import from GitHub
4. Vercel auto-detects React/Vite
5. Deploy — live in 2 minutes

---

## Project Structure

```
nexus/
├── backend/
│   ├── backend.py          # FastAPI server + all integrations
│   ├── requirements.txt    # Python dependencies
│   ├── Procfile           # Railway startup command
│   ├── credentials.json   # Google OAuth (not in repo)
│   └── sprint_history.json # Health score snapshots
│
├── mcp-server/
│   ├── src/
│   │   ├── index.ts       # MCP server entry point
│   │   ├── tools/         # MCP tool definitions
│   │   └── modules/       # Auth + session handling
│   └── package.json
│
└── frontend/
    ├── src/
    │   ├── components/    # React components
    │   ├── pages/         # Landing + Dashboard
    │   └── App.tsx        # Main app + routing
    └── package.json
```

---

## Team

| Member | Role |
|--------|------|
| Parasamani | Backend, API integrations, Architecture |
| Archit | Frontend, UI/UX, Dashboard |
| Thanush | MCP Server, TypeScript, Anthropic Certified |
| Harsh | Demo, Pitch, Research |

**Thanush T S** holds the official **Anthropic MCP Certification** — issued March 29, 2026.

---

## How We Built This

Built in **5 days** for the MCP-Based AI Work Assistant Hackathon — April 2026.

- Day 1 — API setup, demo data seeding, Slack + GitHub + Jira + Calendar configured
- Day 2 — Python FastAPI backend, all 4 integrations working, Groq AI connected
- Day 3 — MCP server built, chat interface, automated Slack alerts
- Day 4 — Frontend connected to backend, full demo flow working
- Day 5 — Deployment, polish, demo rehearsal, submission

**Total development time: ~87 hours across 4 team members**

---

## What's Next

- **Predictive sprint planning** — AI recommends realistic sprint capacity before the sprint starts based on historical velocity
- **Automated blocker resolution** — Nexus reassigns tickets, posts Slack messages, and updates Jira status automatically
- **Linear + Asana + Microsoft Teams** — expand beyond GitHub-Jira-Slack ecosystem
- **PostgreSQL integration** — full historical analytics and trend reporting
- **Multi-workspace support** — monitor multiple teams and projects simultaneously

---

## The Differentiator

> *"Other MCP servers give AI a window into one tool. Nexus gives AI eyes across your entire engineering operation — simultaneously."*

Most MCP servers connect AI to one data source. Nexus connects four — and the AI reasons across all of them together. The insight that catches blockers comes from the **intersection** of GitHub, Jira, Slack, and Calendar — not any single one.

**Other tools tell you what happened. Nexus tells you what's about to happen.**

---

## License

MIT License — built for MCP Hackathon 2026.

---

*Built with by Team Nexus — April 2026*
