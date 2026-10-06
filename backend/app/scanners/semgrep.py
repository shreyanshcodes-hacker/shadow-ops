from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
import subprocess
import json
import asyncio
import tempfile
import os


class SemgrepConfig(BaseModel):
    rulesets: List[str] = ["p/security-audit", "p/secrets", "p/owasp-top-ten"]
    custom_rules: List[str] = []
    timeout: int = 1800
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


@dataclass
class NormalizedFinding:
    source: str
    source_rule_id: str
    title: str
    description: str
    severity: str
    confidence: str
    cwe_ids: List[str]
    cve_ids: List[str]
    owasp_categories: List[str]
    location: Dict[str, Any]
    code_snippet: Optional[str]
    remediation_guidance: Optional[str]
    evidence: Dict[str, Any]


class SemgrepRunner:
    def __init__(self, config: Optional[SemgrepConfig] = None):
        self.config = config or SemgrepConfig()

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

    async def scan(self, target_path: str) -> SemgrepOutput:
        cmd = self._build_command(target_path)

        try:
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

        except asyncio.TimeoutError:
            raise TimeoutError(f"Semgrep scan timed out after {self.config.timeout} seconds")
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Semgrep output: {e}")


class FindingNormalizer:
    SEVERITY_MAP = {
        "ERROR": "critical",
        "WARNING": "high",
        "INFO": "medium",
    }

    def __init__(self):
        pass

    def normalize(self, semgrep_output: SemgrepOutput, repo_context: Optional[Dict[str, Any]] = None) -> List[NormalizedFinding]:
        findings = []

        for result in semgrep_output.results:
            finding = self._normalize_finding(result, repo_context)
            findings.append(finding)

        # Deduplicate findings
        return self._deduplicate(findings)

    def _normalize_finding(self, result: SemgrepFinding, repo_context: Optional[Dict[str, Any]]) -> NormalizedFinding:
        severity = self.SEVERITY_MAP.get(result.extra.get("severity", "").upper(), "medium")

        # Extract CWE IDs
        cwe_ids = []
        metadata = result.extra.get("metadata", {})
        if "cwe" in metadata:
            cwe_val = metadata["cwe"]
            if isinstance(cwe_val, list):
                cwe_ids = [str(c) for c in cwe_val if c]
            elif isinstance(cwe_val, str):
                cwe_ids = [cwe_val] if cwe_val else []

        # Extract CVE IDs
        cve_ids = []
        if "cve" in metadata:
            cve_val = metadata["cve"]
            if isinstance(cve_val, list):
                cve_ids = [str(c) for c in cve_val if c]
            elif isinstance(cve_val, str):
                cve_ids = [cve_val] if cve_val else []

        # Extract OWASP categories
        owasp_categories = []
        if "owasp" in metadata:
            owasp_val = metadata["owasp"]
            if isinstance(owasp_val, list):
                owasp_categories = [str(c) for c in owasp_val if c]
            elif isinstance(owasp_val, str):
                owasp_categories = [owasp_val] if owasp_val else []

        # Extract code snippet
        code_snippet = result.extra.get("lines", "")

        # Location info
        location = {
            "file": result.path,
            "line_start": result.start.get("line", 0),
            "line_end": result.end.get("line", 0),
            "col_start": result.start.get("col", 0),
            "col_end": result.end.get("col", 0),
        }

        return NormalizedFinding(
            source="semgrep",
            source_rule_id=result.check_id,
            title=result.extra.get("message", "Security issue detected"),
            description=result.extra.get("message", "Security issue detected"),
            severity=severity,
            confidence="high",
            cwe_ids=cwe_ids,
            cve_ids=cve_ids,
            owasp_categories=owasp_categories,
            location=location,
            code_snippet=code_snippet,
            remediation_guidance=metadata.get("remediation"),
            evidence={
                "raw_semgrep_output": result.model_dump(),
                "tool_version": "semgrep",
            },
        )

    def _deduplicate(self, findings: List[NormalizedFinding]) -> List[NormalizedFinding]:
        seen = {}
        for finding in findings:
            key = (finding.source, finding.source_rule_id, finding.location.get("file"), finding.location.get("line_start"))
            if key not in seen:
                seen[key] = finding
            else:
                # Merge evidence
                existing = seen[key]
                existing.evidence.setdefault("duplicates", []).append(finding.evidence)

        return list(seen.values())


class DependencyScanner:
    """SCA scanner using Semgrep's dependency scanning capabilities."""

    def __init__(self, config: Optional[SemgrepConfig] = None):
        self.config = config or SemgrepConfig()

    async def scan(self, target_path: str) -> SemgrepOutput:
        cmd = [
            "semgrep",
            "scan",
            "--config", "p/ci",
            "--json",
            target_path,
        ]

        try:
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
                raise RuntimeError(f"Semgrep SCA failed with code {process.returncode}: {stderr.decode()}")

            output = json.loads(stdout.decode())
            return SemgrepOutput(**output)

        except asyncio.TimeoutError:
            raise TimeoutError(f"Semgrep SCA scan timed out after {self.config.timeout} seconds")


class SemgrepManager:
    """High-level manager for Semgrep operations."""

    def __init__(self, config: Optional[SemgrepConfig] = None):
        self.config = config or SemgrepConfig()
        self.sast_runner = SemgrepRunner(self.config)
        self.sca_runner = DependencyScanner(self.config)
        self.normalizer = FindingNormalizer()

    async def scan_code(self, repo_path: str) -> List[NormalizedFinding]:
        output = await self.sast_runner.scan(repo_path)
        return self.normalizer.normalize(output)

    async def scan_dependencies(self, repo_path: str) -> List[NormalizedFinding]:
        output = await self.sca_runner.scan(repo_path)
        return self.normalizer.normalize(output)

    async def scan(self, repo_path: str) -> Dict[str, List[NormalizedFinding]]:
        sast_findings = await self.scan_code(repo_path)
        sca_findings = await self.scan_dependencies(repo_path)
        return {
            "sast": sast_findings,
            "sca": sca_findings,
        }