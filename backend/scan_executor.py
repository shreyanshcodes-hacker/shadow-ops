#!/usr/bin/env python3
"""
ShadowOps Scan Executor - Isolated Single Scan Execution

This script runs inside a hardened, isolated container with:
- No network access (--network=none)
- Read-only root filesystem
- All capabilities dropped
- Resource limits enforced by container runtime
- No access to host paths, secrets, or cloud metadata
- Read-only input directory (/scan-input)
- Bounded writable output directory (/scan-output)

The executor runs a single semgrep scan and exits.
"""

import asyncio
import json
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("scan_executor")


class ScanExecutorError(Exception):
    """Base exception for scan executor errors."""
    def __init__(self, message: str, error_code: str = "EXECUTOR_ERROR", details: dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class ScanExecutorTimeoutError(ScanExecutorError):
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "TIMEOUT", details)


class ScanExecutorValidationError(ScanExecutorError):
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "VALIDATION_FAILED", details)


class ScanExecutorExecutionError(ScanExecutorError):
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, "EXECUTION_FAILED", details)


class SemgrepConfig:
    """Semgrep configuration for scan execution."""
    def __init__(self):
        self.rulesets = [
            "p/security-audit",
            "p/secrets",
            "p/owasp-top-ten",
        ]
        self.custom_rules = []
        self.timeout = int(os.getenv("EXECUTOR_SEMGREP_TIMEOUT", "1800"))
        self.max_file_size_mb = int(os.getenv("EXECUTOR_MAX_FILE_SIZE_MB", "10"))
        self.excluded_paths = [
            "**/node_modules/**",
            "**/.git/**",
            "**/vendor/**",
            "**/dist/**",
            "**/build/**",
            "**/__pycache__/**",
            "**/*.min.js",
        ]


class ScanExecutor:
    """Executes a single semgrep scan in an isolated environment."""
    
    def __init__(self):
        self.config = SemgrepConfig()
        self.scan_input_dir = Path("/scan-input")
        self.scan_output_dir = Path("/scan-output")
        self.max_target_size_mb = int(os.getenv("EXECUTOR_MAX_TARGET_SIZE_MB", "1000"))
        self.semgrep_timeout = int(os.getenv("EXECUTOR_SEMGREP_TIMEOUT", "1800"))
        self.max_output_bytes = 10 * 1024 * 1024  # 10 MB limit
        
    def _build_semgrep_command(self, target_path: str, scan_type: str) -> List[str]:
        """Build semgrep command with security constraints."""
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
        
        for exclude in self.excluded_paths:
            cmd.extend(["--exclude", exclude])
        
        cmd.append(target_path)
        return cmd
    
    async def _run_semgrep(self, target_path: str, scan_type: str) -> Dict[str, Any]:
        """Run semgrep scan with timeout and output limits."""
        cmd = self._build_semgrep_command(target_path, scan_type)
        
        logger.info(f"Running semgrep: {' '.join(cmd[:5])}... [timeout={self.semgrep_timeout}s]")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.semgrep_timeout,
            )
            
            if process.returncode not in (0, 1):
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise ScanExecutorExecutionError(
                    f"Semgrep failed with code {process.returncode}: {error_msg}",
                    details={"returncode": process.returncode, "stderr": error_msg[:500]}
                )
            
            stdout_str = stdout.decode()
            # Limit output size
            if len(stdout_str) > self.max_output_bytes:
                logger.warning(f"Semgrep output truncated from {len(stdout_str)} to {self.max_output_bytes} bytes")
                stdout_str = stdout_str[:self.max_output_bytes]
            
            output = json.loads(stdout_str)
            return output
            
        except asyncio.TimeoutError:
            raise ScanExecutorTimeoutError(
                f"Semgrep scan timed out after {self.semgrep_timeout} seconds",
                details={"timeout": self.semgrep_timeout}
            )
        except json.JSONDecodeError as e:
            raise ScanExecutorExecutionError(
                f"Failed to parse Semgrep output: {e}",
                details={"parse_error": str(e)}
            )
        except Exception as e:
            raise ScanExecutorExecutionError(
                f"Semgrep execution failed: {e}",
                details={"error": str(e), "traceback": traceback.format_exc()}
            )
    
    def _normalize_finding(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a semgrep finding to our standard format."""
        SEVERITY_MAP = {
            "ERROR": "critical",
            "WARNING": "high",
            "INFO": "medium",
        }
        
        extra = result.get("extra", {})
        metadata = extra.get("metadata", {})
        
        # Extract CWE IDs
        cwe_ids = []
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
        
        severity = SEVERITY_MAP.get(extra.get("severity", "").upper(), "medium")
        
        return {
            "source": "semgrep",
            "source_rule_id": result.get("check_id", ""),
            "title": extra.get("message", "Security issue detected"),
            "description": extra.get("message", "Security issue detected"),
            "severity": severity,
            "confidence": "high",
            "cwe_ids": cwe_ids,
            "cve_ids": cve_ids,
            "owasp_categories": owasp_categories,
            "location": {
                "file": result.get("path", ""),
                "line_start": result.get("start", {}).get("line", 0),
                "line_end": result.get("end", {}).get("line", 0),
                "col_start": result.get("start", {}).get("col", 0),
                "col_end": result.get("end", {}).get("col", 0),
            },
            "code_snippet": extra.get("lines", ""),
            "remediation_guidance": metadata.get("remediation"),
            "evidence": {
                "raw_semgrep_output": result,
                "tool_version": "semgrep",
            },
        }
    
    def _deduplicate(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate findings by (source, rule_id, file, line)."""
        seen = {}
        for finding in findings:
            key = (
                finding["source"],
                finding["source_rule_id"],
                finding["location"].get("file"),
                finding["location"].get("line_start"),
            )
            if key not in seen:
                seen[key] = finding
            else:
                # Merge evidence
                existing = seen[key]
                existing["evidence"].setdefault("duplicates", []).append(finding["evidence"])
        
        return list(seen.values())
    
    def _generate_summary(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate deterministic summary from findings."""
        counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
        }
        
        for finding in findings:
            severity = finding["severity"].lower()
            if severity in counts:
                counts[severity] += 1
            else:
                counts["medium"] += 1  # Default fallback
        
        return {
            "total_findings": len(findings),
            **counts,
        }
    
    def _sanitize_output(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize output payload before writing."""
        sanitized = dict(payload)
        
        # Remove raw scanner output that might contain secrets
        if "findings" in sanitized:
            for finding in sanitized["findings"]:
                if "evidence" in finding and isinstance(finding["evidence"], dict):
                    safe_evidence = {}
                    for k, v in finding["evidence"].items():
                        if k in ("rule_id", "scanner", "original_severity"):
                            safe_evidence[k] = v
                    finding["evidence"] = safe_evidence
        
        # Truncate large fields
        json_str = json.dumps(sanitized, default=str)
        if len(json_str.encode()) > self.max_output_bytes:
            if "findings" in sanitized:
                sanitized["findings"] = sanitized["findings"][:100]
                sanitized["truncated"] = True
        
        return sanitized
    
    def _validate_input(self) -> None:
        """Validate input directory exists and is within bounds."""
        if not self.scan_input_dir.exists():
            raise ScanExecutorValidationError(
                f"Scan input directory does not exist: {self.scan_input_dir}"
            )
        
        # Check size
        total_size = 0
        file_count = 0
        for root, dirs, files in os.walk(self.scan_input_dir):
            for file in files:
                file_path = Path(root) / file
                try:
                    total_size += file_path.stat().st_size
                    file_count += 1
                    if file_count > 100000:
                        raise ScanExecutorValidationError("Target contains too many files")
                except OSError:
                    pass
        
        size_mb = total_size / (1024 * 1024)
        if size_mb > self.max_target_size_mb:
            raise ScanExecutorValidationError(
                f"Target size {size_mb:.1f} MB exceeds limit of {self.max_target_size_mb} MB"
            )
        
        logger.info(f"Input validation passed: {file_count} files, {size_mb:.1f} MB")
    
    def _write_output(self, result: Dict[str, Any]) -> None:
        """Write sanitized output to output directory."""
        self.scan_output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = self.scan_output_dir / "results.json"
        sanitized = self._sanitize_output(result)
        
        with open(output_file, "w") as f:
            json.dump(sanitized, f, default=str)
        
        logger.info(f"Results written to {output_file}")
    
    def _write_error(self, error: ScanExecutorError) -> None:
        """Write error output to output directory."""
        self.scan_output_dir.mkdir(parents=True, exist_ok=True)
        
        error_output = {
            "status": "failed",
            "error_code": error.error_code,
            "error_message": error.message,
            "details": error.details,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        error_file = self.scan_output_dir / "error.json"
        with open(error_file, "w") as f:
            json.dump(error_output, f, default=str)
        
        logger.error(f"Error written to {error_file}: {error.message}")
    
    async def execute(self) -> Dict[str, Any]:
        """Execute the scan."""
        logger.info("Starting isolated scan execution")
        
        # Read configuration from environment
        scan_id = os.getenv("SCAN_ID")
        workspace_id = os.getenv("WORKSPACE_ID")
        asset_id = os.getenv("ASSET_ID")
        scan_type = os.getenv("SCAN_TYPE", "code")
        scan_profile = os.getenv("SCAN_PROFILE", "CODE_SECURITY")
        
        if not all([scan_id, workspace_id, asset_id]):
            raise ScanExecutorValidationError(
                "Missing required environment variables: SCAN_ID, WORKSPACE_ID, ASSET_ID"
            )
        
        logger.info(f"Scan config: scan_id={scan_id}, workspace_id={workspace_id}, asset_id={asset_id}, type={scan_type}")
        
        # Validate input
        self._validate_input()
        
        # Determine target path
        target_path = self.scan_input_dir
        
        try:
            # Run semgrep scan
            logger.info(f"Running semgrep on {target_path}")
            semgrep_output = await self._run_semgrep(str(target_path), scan_type)
            
            # Normalize findings
            findings = []
            for result in semgrep_output.get("results", []):
                finding = self._normalize_finding(result)
                findings.append(finding)
            
            # Also run SCA scan for repository assets
            # Note: We'd need asset type info; for now skip SCA in executor
            # Can be added later if needed
            
            # Deduplicate
            findings = self._deduplicate(findings)
            
            # Generate summary
            summary = self._generate_summary(findings)
            
            # Build result
            result = {
                "scan_id": scan_id,
                "status": "completed",
                "summary": summary,
                "findings": findings,
                "findings_count": len(findings),
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            # Write output
            self._write_output(result)
            
            logger.info(f"Scan completed: {len(findings)} findings")
            return result
            
        except ScanExecutorError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error during scan execution: {e}")
            raise ScanExecutorExecutionError(
                f"Scan execution failed: {e}",
                details={"error": str(e), "traceback": traceback.format_exc()}
            )


async def main() -> int:
    """Main entry point."""
    executor = ScanExecutor()
    
    try:
        result = await executor.execute()
        logger.info("Scan execution completed successfully")
        return 0
        
    except ScanExecutorError as e:
        logger.error(f"Scan executor error: {e.message} (code: {e.error_code})")
        executor._write_error(e)
        return 1
        
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        error = ScanExecutorExecutionError(
            f"Unexpected error: {e}",
            details={"error": str(e), "traceback": traceback.format_exc()}
        )
        executor._write_error(error)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)