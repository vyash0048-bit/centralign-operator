"""Core domain models for the CentrAlign Autonomous AI Employee Runtime."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class RunPhase(str, Enum):
    """Immutable state machine phases for task execution."""
    GOAL = "GOAL"
    UNDERSTAND = "UNDERSTAND"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    OBSERVE = "OBSERVE"
    ADAPT = "ADAPT"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    VERIFY = "VERIFY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RiskLevel(str, Enum):
    """Blast-radius classification for tool actions."""
    READ_ONLY = "READ_ONLY"
    LOW_MUTATION = "LOW_MUTATION"
    HIGH_FINANCIAL = "HIGH_FINANCIAL"


class EpisodicLesson(BaseModel):
    """A self-learned operational rule persisted across runs."""
    lesson_id: str
    tool_name: str
    error_signature: str
    parameter_name: str
    transformation_rule: str  # e.g., "strip_hyphens_and_spaces_uppercase"
    explanation: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PlanStep(BaseModel):
    """A single step in the execution plan."""
    step_id: str
    title: str
    tool_name: str
    params: Dict[str, Any]
    risk_level: RiskLevel
    expected_postcondition: str
    status: Literal["PENDING", "IN_PROGRESS", "COMPLETED", "SKIPPED", "FAILED", "ABORTED"] = "PENDING"
    attempts: int = 0
    output: Optional[Dict[str, Any]] = None
    error_history: List[str] = Field(default_factory=list)
    screenshot_paths: List[str] = Field(default_factory=list)


class AdaptationDecision(BaseModel):
    """Structured output from the reasoning engine's failure diagnosis."""
    recoverable: bool
    root_cause: str
    parameter_name: str
    repaired_value: Any
    transformation_rule: str
    lesson_explanation: str


class VerificationCheck(BaseModel):
    """Result of an independent post-condition verification check."""
    check_name: str
    passed: bool
    expected: Any
    actual: Any
    evidence_source: str


class AuditEvent(BaseModel):
    """An immutable audit log entry."""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    phase: str
    event_type: str
    message: str
    details: Optional[Dict[str, Any]] = None


class TaskRunState(BaseModel):
    """The complete, serializable state of a single task execution run."""
    run_id: str
    goal: str
    current_phase: RunPhase
    resolved_context: Dict[str, Any] = Field(default_factory=dict)
    plan: List[PlanStep] = Field(default_factory=list)
    working_memory: Dict[str, Any] = Field(default_factory=dict)
    audit_log: List[AuditEvent] = Field(default_factory=list)
    verification_checks: List[VerificationCheck] = Field(default_factory=list)
    evidence_dir: str = ""
