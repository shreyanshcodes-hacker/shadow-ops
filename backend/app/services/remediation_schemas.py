from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class RemediationFixType(str, Enum):
    CODE_CHANGE = "code_change"
    CONFIG_CHANGE = "config_change"
    DEPENDENCY_UPDATE = "dependency_update"
    INFRASTRUCTURE_CHANGE = "infrastructure_change"
    WAF_RULE = "waf_rule"
    NETWORK_POLICY = "network_policy"
    SECRET_ROTATION = "secret_rotation"


class FileChangeOutput(BaseModel):
    """Single file change in the remediation patch."""
    file_path: str = Field(min_length=1, max_length=500)
    unified_diff: str = Field(min_length=1, max_length=10000)
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    additions: int = Field(ge=0, default=0)
    deletions: int = Field(ge=0, default=0)
    language: Optional[str] = None


class SuggestedTestOutput(BaseModel):
    """Suggested test for verification."""
    test_type: str  # unit, integration, security, regression
    description: str = Field(min_length=5, max_length=500)
    command: Optional[str] = None


class RemediationProposalOutput(BaseModel):
    """Structured AI output for remediation proposal."""

    proposal_title: str = Field(
        min_length=5,
        max_length=255,
        description="Concise title for the remediation proposal"
    )
    problem_summary: str = Field(
        min_length=20,
        max_length=1000,
        description="Summary of the vulnerability and root cause"
    )
    proposed_solution: str = Field(
        min_length=20,
        max_length=2000,
        description="Description of the proposed fix approach"
    )
    rationale: str = Field(
        min_length=20,
        max_length=2000,
        description="Why this fix approach was chosen"
    )
    fix_type: RemediationFixType = Field(
        default=RemediationFixType.CODE_CHANGE,
        description="Type of fix being proposed"
    )
    file_changes: List[FileChangeOutput] = Field(
        default_factory=list,
        max_length=10,
        description="List of file changes with unified diffs"
    )
    expected_security_benefit: str = Field(
        min_length=10,
        max_length=1000,
        description="What security improvement this fix provides"
    )
    compatibility_risks: str = Field(
        default="",
        max_length=1000,
        description="Potential compatibility or regression risks"
    )
    assumptions: str = Field(
        default="",
        max_length=1000,
        description="Assumptions made about the codebase/context"
    )
    limitations: str = Field(
        default="",
        max_length=1000,
        description="Limitations of this fix"
    )
    suggested_tests: List[SuggestedTestOutput] = Field(
        default_factory=list,
        max_length=10,
        description="Tests that should be run to verify the fix"
    )