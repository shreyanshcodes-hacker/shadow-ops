# SEMGREP INTEGRATION

## Overview

Semgrep is the primary static analysis engine for ShadowOps Stage 3. This document describes the integration architecture, configuration, and security considerations.

## Semgrep Version

- **Version**: 1.45.0 (pinned)
- **Installation**: `pip install semgrep==1.45.0`
- **Binary**: `semgrep` (available in PATH)
- **Output Format**: JSON (`--json`)

## Integration Architecture

### High-Level Flow

```
Target Path
     │
     ▼
SemgrepRunner._build_command()
     │
     ▼
asyncio.create_subprocess_exec()
     │
     ▼
Semgrep JSON Output
     │
     ▼
SemgrepOutput Pydantic Model
     │
     ▼
FindingNormalizer.normalize()
     │
     ▼
List[NormalizedFinding]
     │
     ▼
ScanJobRunner._persist_findings()
```

## Command Construction

### Secure Command Building

```python
def _build_command(self, target_path: str) -> List[str]:
    cmd = [
        "semgrep",
        "scan",
        "--json",
        "--max-target-bytes", str(self.config.max_file_size_mb * 1024 * 1024),
    ]

    for ruleset in self.config.rulesets:
        cmd.extend(["--config", ruleset])

    for custom_rule in self.config.custom_rules:
        cmd.extend(["--config", custom_rule])

    for exclude in self.config.excluded_paths:
        cmd.extend(["--exclude", exclude])

    cmd.append(target_path)
    return cmd
```

### Security Properties

| Property | Implementation |
|----------|----------------|
| No shell injection | `asyncio.create_subprocess_exec(*cmd)` (not `shell=True`) |
| Argument validation | Each arg is a separate list element |
| Path validation | Target path validated before command |
| Timeout | `asyncio.wait_for(process.communicate(), timeout=config.timeout)` |
| Resource limits | `--max-target-bytes` limits file size |

### Execution

```python
async def scan(self, target_path: str) -> SemgrepOutput:
    cmd = self._build_command(target_path)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await asyncio.wait_for(
        process.communicate(),
        timeout=self.config.timeout,
    )

    if process.returncode not in (0, 1):
        raise RuntimeError(f"Semgrep failed with code {process.returncode}: {stderr.decode()}")

    output = json.loads(stdout.decode())
    return SemgrepOutput(**output)
```

### Return Codes

| Code | Meaning |
|------|---------|
| 0 | No findings |
| 1 | Findings found |
| >1 | Error |

## Configuration

### SemgrepConfig

```python
class SemgrepConfig(BaseModel):
    rulesets: List[str] = [
        "p/security-audit",
        "p/secrets",
        "p/owasp-top-ten",
    ]
    custom_rules: List[str] = []
    timeout: int = 1800  # 30 minutes
    max_file_size_mb: int = 10
    excluded_paths: List[str] = [
        "**/node_modules/**",
        "**/.git/**",
        "**/vendor/**",
        "**/dist/**",
        "**/build/**",
        "**/__pycache__/**",
        "**/*.min.js",
    ]
```

### Ruleset Descriptions

| Ruleset | Description | Language Coverage |
|---------|-------------|-------------------|
| `p/security-audit` | Security vulnerability patterns | 20+ languages |
| `p/secrets` | API keys, tokens, passwords | All (pattern-based) |
| `p/owasp-top-ten` | OWASP Top 10 patterns | Web-focused |
| `p/ci` | Dependency vulnerabilities | Package managers |

### Custom Rules

Custom rules can be added via:

```python
config = SemgrepConfig(
    custom_rules=[
        "/path/to/custom-rules/",
        "https://github.com/org/custom-rules",
    ]
)
```

## Output Parsing

### Semgrep JSON Structure

```json
{
  "results": [
    {
      "check_id": "python.lang.security.audit.sql-injection.sql-injection",
      "path": "app/models.py",
      "start": {"line": 42, "col": 10},
      "end": {"line": 42, "col": 50},
      "extra": {
        "message": "SQL injection via string formatting",
        "severity": "ERROR",
        "metadata": {
          "cwe": ["CWE-89"],
          "owasp": ["A03:2021"],
          "references": ["https://owasp.org/..."]
        },
        "lines": "query = f\"SELECT * FROM users WHERE id = {user_id}\""
      }
    }
  ],
  "errors": [],
  "skipped": [],
  "paths": {}
}
```

### Pydantic Models

```python
class SemgrepFinding(BaseModel):
    check_id: str
    path: str
    start: Dict[str, int]
    end: Dict[str, int]
    extra: Dict[str, Any]


class SemgrepOutput(BaseModel):
    results: List[SemgrepFinding]
    errors: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    paths: Dict[str, Any] = {}
```

## Finding Normalization

### NormalizedFinding

```python
@dataclass
class NormalizedFinding:
    source: str                    # "semgrep"
    source_rule_id: str            # Semgrep check_id
    title: str                     # Human-readable title
    description: str               # Detailed description
    severity: str                  # critical, high, medium, low, info
    confidence: str                # low, medium, high
    cwe_ids: List[str]             # CWE identifiers
    cve_ids: List[str]             # CVE identifiers
    owasp_categories: List[str]    # OWASP categories
    location: Dict[str, Any]       # File, line, column info
    code_snippet: Optional[str]    # Relevant code
    remediation_guidance: Optional[str]
    evidence: Dict[str, Any]       # Raw data + metadata
```

### Severity Mapping

| Semgrep Severity | ShadowOps Severity |
|------------------|-------------------|
| ERROR | critical |
| WARNING | high |
| INFO | medium |
| (missing) | medium |

### Metadata Extraction

```python
metadata = result.extra.get("metadata", {})

# CWE IDs
if "cwe" in metadata:
    cwe_val = metadata["cwe"]
    if isinstance(cwe_val, list):
        cwe_ids = [str(c) for c in cwe_val if c]
    elif isinstance(cwe_val, str):
        cwe_ids = [cwe_val] if cwe_val else []

# CVE IDs
if "cve" in metadata:
    # Similar extraction

# OWASP Categories
if "owasp" in metadata:
    # Similar extraction
```

### Deduplication

```python
def _deduplicate(self, findings: List[NormalizedFinding]) -> List[NormalizedFinding]:
    seen = {}
    for finding in findings:
        key = (
            finding.source,
            finding.source_rule_id,
            finding.location.get("file"),
            finding.location.get("line_start")
        )
        if key not in seen:
            seen[key] = finding
        else:
            # Merge evidence
            existing = seen[key]
            existing.evidence.setdefault("duplicates", []).append(finding.evidence)

    return list(seen.values())
```

## Evidence Preservation

### Raw Evidence Storage

Each finding preserves the original Semgrep output:

```python
evidence = {
    "raw_semgrep_output": result.model_dump(),
    "tool_version": "semgrep",
    "scanner_config": {
        "rulesets": self.config.rulesets,
        "timeout": self.config.timeout,
    }
}
```

### Evidence Types Created

| Type | Description |
|------|-------------|
| `STATIC_ANALYSIS` | Semgrep finding with rule match |
| `SOURCE_LOCATION` | File, line, column |
| `RULE_MATCH` | Rule ID and pattern |
| `SCAN_OUTPUT` | Full scanner output reference |

## Error Handling

### Timeout

```python
try:
    stdout, stderr = await asyncio.wait_for(
        process.communicate(),
        timeout=self.config.timeout,
    )
except asyncio.TimeoutError:
    raise TimeoutError(f"Semgrep scan timed out after {self.config.timeout} seconds")
```

### Non-Zero Exit

```python
if process.returncode not in (0, 1):
    raise RuntimeError(f"Semgrep failed with code {process.returncode}: {stderr.decode()}")
```

### JSON Parse Error

```python
try:
    output = json.loads(stdout.decode())
except json.JSONDecodeError as e:
    raise ValueError(f"Failed to parse Semgrep output: {e}")
```

## Dependency Scanning (SCA)

### Semgrep SCA

```python
class DependencyScanner:
    async def scan(self, target_path: str) -> SemgrepOutput:
        cmd = [
            "semgrep",
            "scan",
            "--config", "p/ci",
            "--json",
            target_path,
        ]
        # ... same execution pattern
```

### SCA Findings Normalization

SCA findings are normalized with:
- `source`: "dependency"
- `source_rule_id`: CVE ID or package advisory
- `severity`: Mapped from CVSS
- `location`: Package manifest file (package.json, requirements.txt, etc.)

## Security Considerations

### Input Validation

| Check | Implementation |
|-------|----------------|
| Target path exists | `Path(target_path).exists()` |
| Target within workspace | `target_path.resolve().relative_to(workspace_root.resolve())` |
| Target size limit | Walk directory, sum file sizes |
| No symlinks outside | `os.path.realpath()` validation |

### Output Sanitization

```python
# Before storing code snippets
def sanitize_snippet(snippet: str, max_len: int = 500) -> str:
    if len(snippet) > max_len:
        snippet = snippet[:max_len] + "..."
    # Redact potential secrets
    return redact_secrets(snippet)
```

### Process Isolation

- Semgrep runs as subprocess (not in-process)
- No access to parent process memory
- Separate PID, can be killed independently
- Stdout/stderr captured, not logged directly

## Performance

### Typical Performance

| Target Size | Files | Scan Time | Memory |
|-------------|-------|-----------|--------|
| Small (<100 files) | 50 | 5-15s | 200-500MB |
| Medium (100-1000) | 500 | 30-90s | 500MB-1GB |
| Large (1000+) | 5000 | 2-10min | 1-3GB |

### Optimization

- Exclude patterns reduce file count
- `--max-target-bytes` skips large files
- Parallel execution via Semgrep internal
- Incremental scans (future)

## Testing

### Unit Tests

```python
# Mock Semgrep output
mock_output = SemgrepOutput(
    results=[
        SemgrepFinding(
            check_id="test-rule",
            path="test.py",
            start={"line": 10, "col": 5},
            end={"line": 10, "col": 30},
            extra={
                "message": "Test finding",
                "severity": "ERROR",
                "metadata": {"cwe": ["CWE-89"]},
                "lines": "query = f'SELECT * FROM users WHERE id = {user_id}'",
            }
        )
    ]
)

# Test normalization
normalizer = FindingNormalizer()
findings = normalizer.normalize(mock_output)
assert len(findings) == 1
assert findings[0].severity == "critical"
assert findings[0].cwe_ids == ["CWE-89"]
```

### Integration Tests

```python
# Test with real fixture
async def test_semgrep_on_fixture():
    runner = SemgrepRunner()
    findings = await runner.scan("/scan-workspace/demo-target")
    assert len(findings) > 0  # Fixture has intentional vulns
    assert any(f.severity == "critical" for f in findings)
```

## Future Enhancements

### Incremental Scanning

- Semgrep `--baseline-ref` for diff scans
- Only scan changed files
- Cache previous results

### Custom Rules

- Organization-specific rule packs
- Rule testing framework
- Rule performance profiling

### SARIF Output

- Export findings in SARIF 2.1.0 format
- Integration with GitHub Security tab
- Standardized tool output

---

**Document Version**: 1.0  
**Last Updated**: Stage 3 Implementation