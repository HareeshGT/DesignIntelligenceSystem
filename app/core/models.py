from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentRole(str, Enum):
    DIRECTOR = "design_director"
    CREATIVE = "creative_director"
    UX = "ux_architect"
    VISUAL = "visual_designer"
    SYSTEMS = "design_systems_engineer"
    FRONTEND = "frontend_engineer"
    QA = "visual_qa_engineer"


class TaskStatus(str, Enum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    NEEDS_INPUT = "needs_input"


class DesignRequest(BaseModel):
    brief: str = Field(min_length=5, max_length=10000)
    product_context: str = Field(default="", max_length=10000)
    constraints: list[str] = Field(default_factory=list)
    target_platforms: list[str] = Field(default_factory=lambda: ["web"])
    autonomy: str = Field(default="high", pattern="^(low|medium|high)$")
    project_id: str = Field(default_factory=lambda: str(uuid4()))


class AgentTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    role: AgentRole
    objective: str
    context: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)


class AgentResult(BaseModel):
    task_id: str
    role: AgentRole
    status: TaskStatus = TaskStatus.COMPLETED
    summary: str
    findings: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    deliverables: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class DesignRun(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    status: TaskStatus
    brief: str
    plan: list[AgentTask]
    results: list[AgentResult]
    quality: dict[str, Any]
    created_at: datetime = Field(default_factory=utc_now)


class ApprovalRequest(BaseModel):
    action: str
    resource: str = ""
    reason: str = ""


class ApprovalDecision(BaseModel):
    allowed: bool
    requires_approval: bool
    explanation: str
