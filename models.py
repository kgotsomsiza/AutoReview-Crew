"""Shared data structures used across the agents.

Keeping these in one place means every agent describes a 'finding' the same way,
which makes it easy for the Lead Reviewer to read them all as shared context.
"""
from dataclasses import dataclass, field


@dataclass
class Finding:
    """One issue (or note) raised by a reviewer agent about the code."""
    agent: str           # which agent found it, e.g. "Correctness Reviewer"
    severity: str        # "info" | "low" | "medium" | "high" | "critical"
    title: str           # short summary
    detail: str          # explanation of the issue
    location: str = ""   # file/line if known, e.g. "calc.py:7"


@dataclass
class ReviewResult:
    """The Lead Reviewer's final decision after reading everyone's findings."""
    decision: str                            # "APPROVE" | "REQUEST_CHANGES" | "ESCALATE_TO_HUMAN"
    rationale: str                           # short reason for the decision
    findings: list[Finding] = field(default_factory=list)
