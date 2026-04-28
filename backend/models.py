from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class Organization(Base):
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    workspaces = relationship("Workspace", back_populates="organization")

class Workspace(Base):
    __tablename__ = "workspaces"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Store settings/credentials JSON securely in real prod, keeping it simple here
    settings = Column(JSON, default={})
    
    organization = relationship("Organization", back_populates="workspaces")
    sprint_snapshots = relationship("SprintSnapshot", back_populates="workspace")

class SprintSnapshot(Base):
    __tablename__ = "sprint_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"))
    date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Aggregated metrics for velocity trending
    points_at_risk = Column(Integer, default=0)
    completion_pct = Column(Float, default=0.0)
    total_tickets = Column(Integer, default=0)
    done_tickets = Column(Integer, default=0)
    blocked_tickets = Column(Integer, default=0)
    open_prs = Column(Integer, default=0)
    unanswered_slack_msgs = Column(Integer, default=0)
    
    # Raw snapshot data (optional, can be normalized further)
    jira_snapshot = Column(JSON, default={})
    github_snapshot = Column(JSON, default={})
    slack_snapshot = Column(JSON, default={})
    
    workspace = relationship("Workspace", back_populates="sprint_snapshots")

# Optional: Granular historical tables for specific analytics
class JiraTicketHistory(Base):
    __tablename__ = "jira_ticket_history"
    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"))
    ticket_key = Column(String, index=True) # e.g. SCRUM-1
    title = Column(String)
    status = Column(String)
    assignee = Column(String)
    due_date = Column(String, nullable=True)
    is_blocked = Column(Boolean, default=False)
    snapshot_date = Column(DateTime(timezone=True), server_default=func.now())

class GitHubPRHistory(Base):
    __tablename__ = "github_pr_history"
    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"))
    pr_number = Column(Integer, index=True)
    author = Column(String)
    is_stale = Column(Boolean, default=False)
    needs_review = Column(Boolean, default=False)
    snapshot_date = Column(DateTime(timezone=True), server_default=func.now())
