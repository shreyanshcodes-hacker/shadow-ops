from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class VulnerabilityType(str, Enum):
    INJECTION = "injection"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    CRYPTOGRAPHY = "cryptography"
    DATA_EXPOSURE = "data_exposure"
    CONFIGURATION = "configuration"
    DEPENDENCY = "dependency"
    DENIAL_OF_SERVICE = "denial_of_service"
    BUSINESS_LOGIC = "business_logic"
    UNKNOWN = "unknown"


class SeverityAssessment(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    UNKNOWN = "unknown"


class ExploitabilityAssessment(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class EvidenceCertainty(str, Enum):
    OBSERVED = "observed"
    INFERRED = "inferred"
    UNCERTAIN = "uncertain"


class SupportingEvidenceRef(BaseModel):
    evidence_id: str
    reason: str
    certainty: EvidenceCertainty = EvidenceCertainty.OBSERVED


class SecurityAnalysis(BaseModel):
    """Structured AI analysis output for a security finding (Stage 5 SecurityAnalysis)."""

    summary: str = Field(
        min_length=10,
        max_length=500,
        description="Concise 1-2 sentence summary of the finding"
    )
    vulnerability_type: VulnerabilityType = Field(
        default=VulnerabilityType.UNKNOWN,
        description="Category of vulnerability"
    )
    severity_assessment: SeverityAssessment = Field(
        default=SeverityAssessment.UNKNOWN,
        description="AI assessment of severity (separate from scanner severity)"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the analysis (0.0-1.0), separate from scanner severity"
    )
    exploitability_assessment: ExploitabilityAssessment = Field(
        default=ExploitabilityAssessment.UNKNOWN,
        description="Assessment of exploitability likelihood"
    )
    impact_assessment: str = Field(
        min_length=20,
        max_length=2000,
        description="Potential impact if exploited, including affected assets and data"
    )
    affected_component: str = Field(
        min_length=1,
        max_length=200,
        description="Component, file, or module affected"
    )
    attack_preconditions: str = Field(
        default="",
        max_length=1000,
        description="Conditions that must exist for exploitation"
    )
    evidence_interpretation: str = Field(
        min_length=20,
        max_length=2000,
        description="Interpretation of what the evidence shows (OBSERVED/INFERRED/UNCERTAIN)"
    )
    reasoning: str = Field(
        min_length=20,
        max_length=2000,
        description="Step-by-step reasoning linking evidence to conclusions"
    )
    recommended_next_steps: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Recommended investigation or remediation steps for human reviewer"
    )
    uncertainty: str = Field(
        default="",
        max_length=1000,
        description="Areas where analysis is uncertain or requires additional context"
    )
    supporting_evidence: List[SupportingEvidenceRef] = Field(
        default_factory=list,
        max_length=20,
        description="References to specific evidence IDs with reasoning and certainty"
    )


class ScanAnalysis(BaseModel):
    """Structured AI analysis output for an entire scan."""

    executive_summary: str = Field(
        min_length=50,
        max_length=1000,
        description="High-level summary of the scan results"
    )
    key_findings: List[SecurityAnalysis] = Field(
        default_factory=list,
        max_length=20,
        description="Analysis of the most critical findings"
    )
    overall_risk_assessment: str = Field(
        min_length=20,
        max_length=2000,
        description="Overall risk assessment of the scanned asset"
    )
    recommended_priorities: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Recommended priority areas for remediation"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall confidence in the scan analysis"
    )