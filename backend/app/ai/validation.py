import logging
from typing import List, Dict, Any, Set, Tuple
from uuid import UUID

from app.ai.schemas import SecurityAnalysis, ScanAnalysis, VulnerabilityType, SeverityAssessment, ExploitabilityAssessment, EvidenceCertainty
from app.ai.safety import validate_ai_output_references

logger = logging.getLogger(__name__)


class AIValidationError(Exception):
    """Raised when AI output validation fails."""

    def __init__(self, message: str, errors: List[str]):
        self.message = message
        self.errors = errors
        super().__init__(message)


MAX_SUMMARY_LENGTH = 500
MAX_EXPLANATION_LENGTH = 2000
MAX_IMPACT_LENGTH = 2000
MAX_UNCERTAINTY_LENGTH = 1000
MAX_PRECONDITIONS_LENGTH = 1000
MAX_REASONING_LENGTH = 2000
MAX_AFFECTED_COMPONENT_LENGTH = 200
MAX_SUPPORTING_EVIDENCE = 20
MAX_RECOMMENDED_STEPS = 10


def validate_security_analysis(
    analysis: SecurityAnalysis,
    provided_evidence_ids: Set[str],
) -> Tuple[bool, List[str]]:
    """
    Validate a SecurityAnalysis object.

    Returns (is_valid, list_of_errors).
    """
    errors = []

    # Validate summary
    if not analysis.summary or len(analysis.summary.strip()) < 10:
        errors.append("Summary must be at least 10 characters")
    elif len(analysis.summary) > MAX_SUMMARY_LENGTH:
        errors.append(f"Summary exceeds maximum length of {MAX_SUMMARY_LENGTH}")

    # Validate vulnerability_type
    if analysis.vulnerability_type not in VulnerabilityType:
        errors.append(f"Invalid vulnerability_type: {analysis.vulnerability_type}")

    # Validate severity_assessment
    if analysis.severity_assessment not in SeverityAssessment:
        errors.append(f"Invalid severity_assessment: {analysis.severity_assessment}")

    # Validate confidence range
    if not (0.0 <= analysis.confidence <= 1.0):
        errors.append("Confidence must be between 0.0 and 1.0")

    # Validate exploitability_assessment
    if analysis.exploitability_assessment not in ExploitabilityAssessment:
        errors.append(f"Invalid exploitability_assessment: {analysis.exploitability_assessment}")

    # Validate impact_assessment
    if not analysis.impact_assessment or len(analysis.impact_assessment.strip()) < 20:
        errors.append("Impact assessment must be at least 20 characters")
    elif len(analysis.impact_assessment) > MAX_IMPACT_LENGTH:
        errors.append(f"Impact assessment exceeds maximum length of {MAX_IMPACT_LENGTH}")

    # Validate affected_component
    if not analysis.affected_component or len(analysis.affected_component.strip()) < 1:
        errors.append("Affected component must not be empty")
    elif len(analysis.affected_component) > MAX_AFFECTED_COMPONENT_LENGTH:
        errors.append(f"Affected component exceeds maximum length of {MAX_AFFECTED_COMPONENT_LENGTH}")

    # Validate attack_preconditions length
    if analysis.attack_preconditions and len(analysis.attack_preconditions) > MAX_PRECONDITIONS_LENGTH:
        errors.append(f"Attack preconditions exceeds maximum length of {MAX_PRECONDITIONS_LENGTH}")

    # Validate evidence_interpretation
    if not analysis.evidence_interpretation or len(analysis.evidence_interpretation.strip()) < 20:
        errors.append("Evidence interpretation must be at least 20 characters")
    elif len(analysis.evidence_interpretation) > MAX_EXPLANATION_LENGTH:
        errors.append(f"Evidence interpretation exceeds maximum length of {MAX_EXPLANATION_LENGTH}")

    # Validate reasoning
    if not analysis.reasoning or len(analysis.reasoning.strip()) < 20:
        errors.append("Reasoning must be at least 20 characters")
    elif len(analysis.reasoning) > MAX_REASONING_LENGTH:
        errors.append(f"Reasoning exceeds maximum length of {MAX_REASONING_LENGTH}")

    # Validate recommended_next_steps
    if len(analysis.recommended_next_steps) > MAX_RECOMMENDED_STEPS:
        errors.append(f"Too many recommended next steps (max {MAX_RECOMMENDED_STEPS})")
    for i, step in enumerate(analysis.recommended_next_steps):
        if not step or len(step.strip()) < 5:
            errors.append(f"Recommended step {i} too short")

    # Validate uncertainty length
    if analysis.uncertainty and len(analysis.uncertainty) > MAX_UNCERTAINTY_LENGTH:
        errors.append(f"Uncertainty exceeds maximum length of {MAX_UNCERTAINTY_LENGTH}")

    # Validate supporting evidence
    if len(analysis.supporting_evidence) > MAX_SUPPORTING_EVIDENCE:
        errors.append(f"Too many supporting evidence references (max {MAX_SUPPORTING_EVIDENCE})")

    # Validate evidence references
    refs_valid, ref_errors = validate_ai_output_references(
        [ref.model_dump() for ref in analysis.supporting_evidence],
        provided_evidence_ids,
    )
    if not refs_valid:
        errors.extend(ref_errors)

    # Validate certainty values in supporting evidence
    for ref in analysis.supporting_evidence:
        if ref.certainty not in EvidenceCertainty:
            errors.append(f"Invalid certainty value: {ref.certainty}")

    return len(errors) == 0, errors


def validate_scan_analysis(
    analysis: ScanAnalysis,
    provided_finding_ids: Set[str],
) -> Tuple[bool, List[str]]:
    """
    Validate a ScanAnalysis object.

    Returns (is_valid, list_of_errors).
    """
    errors = []

    # Validate executive_summary
    if not analysis.executive_summary or len(analysis.executive_summary.strip()) < 50:
        errors.append("Executive summary must be at least 50 characters")
    elif len(analysis.executive_summary) > 1000:
        errors.append("Executive summary exceeds maximum length of 1000")

    # Validate key_findings
    if len(analysis.key_findings) > 20:
        errors.append("Too many key findings (max 20)")

    for i, finding in enumerate(analysis.key_findings):
        finding_errors = validate_security_analysis_structure(finding)
        for err in finding_errors:
            errors.append(f"Key finding {i}: {err}")

    # Validate overall_risk_assessment
    if not analysis.overall_risk_assessment or len(analysis.overall_risk_assessment.strip()) < 20:
        errors.append("Overall risk assessment must be at least 20 characters")
    elif len(analysis.overall_risk_assessment) > 2000:
        errors.append("Overall risk assessment exceeds maximum length of 2000")

    # Validate recommended_priorities
    if len(analysis.recommended_priorities) > 10:
        errors.append("Too many recommended priorities (max 10)")

    # Validate confidence
    if not (0.0 <= analysis.confidence <= 1.0):
        errors.append("Confidence must be between 0.0 and 1.0")

    return len(errors) == 0, errors


def validate_security_analysis_structure(analysis: SecurityAnalysis) -> List[str]:
    """Validate SecurityAnalysis structure without evidence reference check."""
    errors = []

    if not analysis.summary or len(analysis.summary.strip()) < 10:
        errors.append("Summary too short")
    if not analysis.evidence_interpretation or len(analysis.evidence_interpretation.strip()) < 20:
        errors.append("Evidence interpretation too short")
    if not analysis.reasoning or len(analysis.reasoning.strip()) < 20:
        errors.append("Reasoning too short")
    if not analysis.impact_assessment or len(analysis.impact_assessment.strip()) < 20:
        errors.append("Impact assessment too short")
    if not (0.0 <= analysis.confidence <= 1.0):
        errors.append("Confidence out of range")
    if analysis.vulnerability_type not in VulnerabilityType:
        errors.append(f"Invalid vulnerability_type: {analysis.vulnerability_type}")
    if analysis.severity_assessment not in SeverityAssessment:
        errors.append(f"Invalid severity_assessment: {analysis.severity_assessment}")
    if analysis.exploitability_assessment not in ExploitabilityAssessment:
        errors.append(f"Invalid exploitability_assessment: {analysis.exploitability_assessment}")

    return errors


def sanitize_analysis_output(analysis: SecurityAnalysis) -> SecurityAnalysis:
    """
    Sanitize analysis output to ensure it meets constraints.
    Truncates fields that are too long.
    """
    return SecurityAnalysis(
        summary=analysis.summary[:MAX_SUMMARY_LENGTH],
        vulnerability_type=analysis.vulnerability_type,
        severity_assessment=analysis.severity_assessment,
        confidence=max(0.0, min(1.0, analysis.confidence)),
        exploitability_assessment=analysis.exploitability_assessment,
        impact_assessment=analysis.impact_assessment[:MAX_IMPACT_LENGTH],
        affected_component=analysis.affected_component[:MAX_AFFECTED_COMPONENT_LENGTH],
        attack_preconditions=analysis.attack_preconditions[:MAX_PRECONDITIONS_LENGTH] if analysis.attack_preconditions else "",
        evidence_interpretation=analysis.evidence_interpretation[:MAX_EXPLANATION_LENGTH],
        reasoning=analysis.reasoning[:MAX_REASONING_LENGTH],
        recommended_next_steps=analysis.recommended_next_steps[:MAX_RECOMMENDED_STEPS],
        uncertainty=analysis.uncertainty[:MAX_UNCERTAINTY_LENGTH] if analysis.uncertainty else "",
        supporting_evidence=analysis.supporting_evidence[:MAX_SUPPORTING_EVIDENCE],
    )