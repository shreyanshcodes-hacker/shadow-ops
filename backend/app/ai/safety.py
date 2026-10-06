import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Secret patterns to detect and redact
SECRET_PATTERNS = [
    # API Keys (generic)
    (re.compile(r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?'), "API_KEY"),
    # AWS
    (re.compile(r'(?i)aws[_-]?access[_-]?key\s*[:=]\s*["\']?([A-Z0-9]{20})["\']?'), "AWS_ACCESS_KEY"),
    (re.compile(r'(?i)aws[_-]?secret[_-]?key\s*[:=]\s*["\']?([a-zA-Z0-9/+=]{40})["\']?'), "AWS_SECRET_KEY"),
    # GitHub
    (re.compile(r'(?i)github[_-]?token\s*[:=]\s*["\']?(gh[pousr]_[a-zA-Z0-9]{36,})["\']?'), "GITHUB_TOKEN"),
    (re.compile(r'(?i)gh[pousr]_[a-zA-Z0-9]{36,}'), "GITHUB_TOKEN"),
    # Supabase
    (re.compile(r'(?i)supabase[_-]?(service[_-]?role[_-]?key|anon[_-]?key)\s*[:=]\s*["\']?(eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+)["\']?'), "SUPABASE_KEY"),
    (re.compile(r'eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+'), "JWT_TOKEN"),
    # Firebase
    (re.compile(r'(?i)firebase[_-]?(private[_-]?key|api[_-]?key)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?'), "FIREBASE_KEY"),
    # Generic password/secret assignments
    (re.compile(r'(?i)(password|passwd|pwd|secret|token)\s*[:=]\s*["\']([^"\']{8,})["\']'), "SECRET"),
    # Database URLs with credentials
    (re.compile(r'(postgresql|mysql|mongodb)://[^:]+:([^@]+)@'), "DB_CREDENTIALS"),
    # Private keys
    (re.compile(r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'), "PRIVATE_KEY"),
    # Slack tokens
    (re.compile(r'xox[baprs]-[a-zA-Z0-9-]+'), "SLACK_TOKEN"),
    # Stripe keys
    (re.compile(r'(?i)sk_live_[a-zA-Z0-9]{24,}'), "STRIPE_SECRET_KEY"),
    (re.compile(r'(?i)pk_live_[a-zA-Z0-9]{24,}'), "STRIPE_PUBLIC_KEY"),
    # Generic bearer tokens
    (re.compile(r'(?i)bearer\s+([a-zA-Z0-9_\-]{20,})'), "BEARER_TOKEN"),
    # Heroku
    (re.compile(r'(?i)heroku[_-]?api[_-]?key\s*[:=]\s*["\']?([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})["\']?'), "HEROKU_API_KEY"),
    # Generic long alphanumeric strings that look like keys
    (re.compile(r'(?i)(key|token|secret)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{32,})["\']?'), "GENERIC_SECRET"),
]


@dataclass
class RedactionResult:
    content: str
    redacted_count: int
    redacted_types: List[str]


def redact_secrets(content: str) -> RedactionResult:
    """
    Redact obvious secrets from content.

    Returns redacted content and metadata about what was redacted.
    """
    if not content:
        return RedactionResult(content="", redacted_count=0, redacted_types=[])

    redacted_content = content
    redacted_types = set()
    total_redactions = 0

    for pattern, secret_type in SECRET_PATTERNS:
        matches = list(pattern.finditer(redacted_content))
        if matches:
            redacted_types.add(secret_type)
            total_redactions += len(matches)
            # Replace each match with placeholder
            for match in reversed(matches):
                start, end = match.span()
                # Keep the key name but redact the value
                matched_text = match.group()
                if ':' in matched_text or '=' in matched_text:
                    # Has key:value or key=value format
                    parts = re.split(r'[:=]', matched_text, 1)
                    replacement = f"{parts[0]}: [REDACTED_{secret_type}]"
                else:
                    replacement = f"[REDACTED_{secret_type}]"
                redacted_content = redacted_content[:start] + replacement + redacted_content[end:]

    return RedactionResult(
        content=redacted_content,
        redacted_count=total_redactions,
        redacted_types=list(redacted_types),
    )


def sanitize_for_ai(content: str, max_chars: int = 50000) -> str:
    """
    Sanitize content for AI transmission.

    - Redact secrets
    - Truncate to max_chars
    - Remove excessive whitespace
    """
    if not content:
        return ""

    # First redact secrets
    result = redact_secrets(content)
    sanitized = result.content

    # Truncate if needed
    if len(sanitized) > max_chars:
        sanitized = sanitized[:max_chars] + f"\n\n[TRUNCATED: {len(content)} total chars, showing first {max_chars}]"

    # Normalize whitespace
    sanitized = re.sub(r'\n{3,}', '\n\n', sanitized)
    sanitized = re.sub(r' {2,}', ' ', sanitized)

    if result.redacted_count > 0:
        logger.info(f"Redacted {result.redacted_count} secrets of types: {result.redacted_types}")

    return sanitized


def sanitize_evidence_dict(evidence: Dict[str, Any], max_chars: int = 10000) -> Dict[str, Any]:
    """
    Sanitize a finding evidence dictionary for AI transmission.

    Recursively processes string values.
    """
    if not isinstance(evidence, dict):
        return evidence

    sanitized = {}
    for key, value in evidence.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_for_ai(value, max_chars)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_evidence_dict(value, max_chars)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_evidence_dict(item, max_chars) if isinstance(item, dict)
                else sanitize_for_ai(str(item), max_chars) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            sanitized[key] = value

    return sanitized


# Prompt injection defense delimiters
TRUSTED_SYSTEM_START = "<TRUSTED_SYSTEM_INSTRUCTIONS>"
TRUSTED_SYSTEM_END = "</TRUSTED_SYSTEM_INSTRUCTIONS>"
UNTRUSTED_EVIDENCE_START = "<UNTRUSTED_SECURITY_EVIDENCE>"
UNTRUSTED_EVIDENCE_END = "</UNTRUSTED_SECURITY_EVIDENCE>"


def build_safe_prompt(system_instructions: str, evidence: str, user_query: str = "") -> str:
    """
    Build a prompt with clear separation between trusted instructions and untrusted evidence.

    This helps prevent prompt injection by making it clear to the model
    that evidence content is data, not instructions.
    """
    parts = [
        TRUSTED_SYSTEM_START,
        system_instructions.strip(),
        TRUSTED_SYSTEM_END,
        "",
        UNTRUSTED_EVIDENCE_START,
        evidence.strip(),
        UNTRUSTED_EVIDENCE_END,
    ]

    if user_query:
        parts.extend(["", user_query.strip()])

    return "\n".join(parts)


def validate_ai_output_references(
    supporting_evidence: List[Dict[str, Any]],
    provided_evidence_ids: set,
) -> tuple[bool, List[str]]:
    """
    Validate that all evidence IDs referenced in AI output actually exist.

    Returns (is_valid, list_of_errors).
    """
    errors = []
    for ref in supporting_evidence:
        if not isinstance(ref, dict):
            errors.append("Supporting evidence reference must be an object")
            continue

        evidence_id = ref.get("evidence_id")
        if not evidence_id:
            errors.append("Supporting evidence reference missing evidence_id")
            continue

        if evidence_id not in provided_evidence_ids:
            errors.append(f"Referenced evidence_id {evidence_id} not found in provided evidence")

    return len(errors) == 0, errors


def is_provider_configured() -> Dict[str, bool]:
    """Check which AI providers are configured."""
    from app.core.config import settings
    return {
        "gemini": bool(settings.GEMINI_API_KEY),
        "grok": bool(settings.GROK_API_KEY),
    }