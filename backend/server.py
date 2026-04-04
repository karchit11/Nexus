import asyncio
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# This is your MCP server
# It gives AI tools to read your live sprint data
app = Server("nexus-sprint-intelligence")

BACKEND = "http://localhost:8008"

@app.list_tools()
async def list_tools():
    return [
        types.Tool(
            name="get_sprint_health",
            description="""Get complete sprint health analysis.
            Returns all tickets with risk levels, AI insights,
            named engineer recommendations, and sprint forecast.
            Use this when asked about sprint status, blockers,
            or overall team health.""",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="get_stale_prs",
            description="""Get GitHub pull requests that are
            at risk. Returns open PR count, stale reviews,
            and CI failures. Use when asked about code reviews,
            PRs, or GitHub activity.""",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="get_team_workload",
            description="""Get team workload analysis showing
            who is overloaded, who has capacity, and AI
            recommendations for rebalancing. Use when asked
            about team members, workload, or who to assign.""",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="ask_nexus",
            description="""Ask any natural language question
            about the sprint, team, or blockers. The AI reads
            all live data and answers specifically. Use for
            any question not covered by other tools.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask"
                    }
                },
                "required": ["question"]
            }
        ),
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    async with httpx.AsyncClient(timeout=30) as client:
        
        if name == "get_sprint_health":
            resp = await client.get(
                f"{BACKEND}/api/sprint-health"
            )
            data = resp.json()
            
            # Format it nicely for the AI
            tickets = data.get("tickets", [])
            summary = data.get("summary", {})
            
            result = f"""
SPRINT HEALTH REPORT
====================
Points at Risk: {summary.get('points_at_risk', 0)}
Days Remaining: {summary.get('days_remaining', 0)}
Completion Forecast: {summary.get('completion_pct', 0)}%
Prediction: {summary.get('prediction', 'N/A')}

TICKET BREAKDOWN:
"""
            for t in tickets:
                result += f"""
{t['id']} — {t['title']}
Risk: {t['risk'].upper()}
Assignee: {t.get('assignee', 'Unassigned')}
Status: {t['status']}
AI Insight: {t['insight']}
Recommended Action: {t.get('action', 'Monitor closely')}
---"""
            
            return [types.TextContent(
                type="text", text=result
            )]

        elif name == "get_stale_prs":
            resp = await client.get(
                f"{BACKEND}/api/github-stats"
            )
            data = resp.json()
            
            result = f"""
GITHUB PR STATUS
================
Open PRs: {data.get('open_prs', 0)}
Stale Reviews (24h+): {data.get('stale_reviews', 0)}
PRs with No Reviewer: {data.get('failing_ci', 0)}

STATUS: {'CRITICAL — PRs are blocking sprint' 
         if data.get('stale_reviews', 0) > 0 
         else 'Healthy'}
"""
            return [types.TextContent(
                type="text", text=result
            )]

        elif name == "get_team_workload":
            resp = await client.get(
                f"{BACKEND}/api/team-workload"
            )
            data = resp.json()
            team = data.get("team", [])
            
            result = f"""
TEAM WORKLOAD ANALYSIS
======================
Critical Person: {data.get('critical_person', 'N/A')}
Available Person: {data.get('available_person', 'N/A')}

INDIVIDUAL STATUS:
"""
            for member in team:
                bar = "■" * member.get('load_score', 0) + \
                      "□" * (10 - member.get('load_score', 0))
                result += f"""
{member['name']} ({member['role']})
Load: [{bar}] {member.get('load_score', 0)}/10
Status: {member['status'].upper()}
Meetings today: {member.get('meetings_today', 0)}
AI Recommendation: {member.get('ai_recommendation', 'N/A')}
---"""

            result += f"\nREBALANCING ACTIONS:\n"
            for action in data.get("rebalancing", []):
                result += f"• {action}\n"
                
            return [types.TextContent(
                type="text", text=result
            )]

        elif name == "ask_nexus":
            question = arguments.get("question", "")
            resp = await client.post(
                f"{BACKEND}/api/chat",
                json={"question": question}
            )
            data = resp.json()
            return [types.TextContent(
                type="text",
                text=data.get("answer", "No response")
            )]

        else:
            return [types.TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]

async def main():
    async with stdio_server() as (read, write):
        await app.run(
            read, write,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    print("Nexus MCP Server starting...")
    print("Tools available:")
    print("  - get_sprint_health")
    print("  - get_stale_prs") 
    print("  - get_team_workload")
    print("  - ask_nexus")
    asyncio.run(main())