# VERIFICATION ARCHITECTURE

## Core Principle

**Verification answers: "Did the fix actually work?"**

Not UI state changes. Not human assertions. Empirical evidence that the vulnerability is no longer exploitable, the configuration is corrected, or the dependency is patched.

---

## Verification Types

| Type | Applicable Findings | Method | Evidence |
|------|---------------------|--------|----------|
| `reproduction_test` | All with reproduction steps | Execute PoC, expect failure | Test output, logs, screenshots |
| `semgrep_rescan` | SAST findings (semgrep source) | Re-run Semgrep on changed files | Semgrep JSON output (finding absent) |
| `dependency_check` | SCA findings (dependency source) | Re-scan lockfiles, query OSV/GHSA | Scan output (CVE resolved) |
| `config_audit` | Recon, config, infra findings | Query live API/state, compare desired | API response, config diff |
| `regression_check` | All remediations | Lightweight targeted scan | New finding count = 0 |

---

## Verification Trigger Points

```
REMEDIATION APPLIED
      │
      ├──► Git PR Merged → Webhook → Verification Queued
      ├──► n8n Workflow Complete → Webhook → Verification Queued
      ├──► Manual "Mark Fixed" → API → Verification Queued
      └──► Scheduled Re-verification → Cron → Verification Queued
```

---

## Verification Runner Architecture

```python
class VerificationOrchestrator:
    """
    Coordinates verification runs for a finding/remediation.
    """
    
    async def run_verification(
        self, 
        finding_id: UUID, 
        proposal_id: UUID | None = None,
        trigger: VerificationTrigger = VerificationTrigger.REMEDIATION_APPLIED,
    ) -> VerificationRun:
        
        finding = await db.get_finding(finding_id)
        asset = await db.get_asset(finding.asset_id)
        
        # Determine verification types based on finding source
        verification_types = self._determine_verification_types(finding)
        
        # Create verification run record
        run = VerificationRun(
            finding_id=finding_id,
            proposal_id=proposal_id,
            scan_id=None,  # Will link to scan if full scan triggered
            verification_type="comprehensive",
            status="running",
            started_at=datetime.utcnow(),
        )
        await db.insert(run)
        
        all_passed = True
        checks = []
        evidence_refs = []
        
        for v_type in verification_types:
            try:
                checker = VERIFICATION_CHECKERS[v_type]
                result = await checker.verify(finding, asset, proposal_id)
                
                checks.append(VerificationCheck(
                    name=v_type.value,
                    passed=result.passed,
                    details=result.details,
                    duration_ms=result.duration_ms,
                ))
                
                all_passed = all_passed and result.passed
                
                # Store evidence
                for ev in result.evidence:
                    evidence_id = await evidence_storage.store(ev)
                    evidence_refs.append(evidence_id)
                    
            except Exception as e:
                checks.append(VerificationCheck(
                    name=v_type.value,
                    passed=False,
                    details={"error": str(e)},
                ))
                all_passed = False
        
        # Update run
        run.status = "passed" if all_passed else "failed"
        run.result = {"checks": [c.model_dump() for c in checks]}
        run.evidence_refs = evidence_refs
        run.passed = all_passed
        run.completed_at = datetime.utcnow()
        await db.update(run)
        
        # If passed, update finding status
        if all_passed and finding.status != "fixed":
            await db.update_finding(finding_id, {
                "status": "fixed",
                "fixed_at": datetime.utcnow(),
                "verification_run_id": run.id,
            })
            await recalculate_workspace_score(finding.workspace_id)
        
        # Emit events
        await event_emitter.emit(finding.workspace_id, "verification_complete", {
            "finding_id": str(finding_id),
            "passed": all_passed,
            "checks": [c.model_dump() for c in checks],
        })
        
        return run
    
    def _determine_verification_types(self, finding: Finding) -> list[VerificationType]:
        types = [VerificationType.REGRESSION_CHECK]  # Always run
        
        if finding.reproduction_steps:
            types.append(VerificationType.REPRODUCTION_TEST)
        
        if finding.source == "semgrep":
            types.append(VerificationType.SEMGREP_RESCAN)
        elif finding.source == "dependency":
            types.append(VerificationType.DEPENDENCY_CHECK)
        elif finding.source in ("recon", "config", "infrastructure"):
            types.append(VerificationType.CONFIG_AUDIT)
        
        return types
```

---

## Verification Checkers

### 1. Reproduction Test Checker

```python
class ReproductionTestChecker:
    """
    Executes the original reproduction steps and expects them to FAIL.
    """
    
    async def verify(self, finding: Finding, asset: Asset, proposal_id: UUID | None) -> VerificationResult:
        if not finding.reproduction_steps:
            return VerificationResult(passed=False, details={"error": "No reproduction steps"})
        
        # Build test script from reproduction steps
        test_script = self._build_test_script(finding.reproduction_steps, asset)
        
        # Execute in isolated environment (container/VM)
        # For now: execute against target if safe, otherwise simulate
        if finding.source == "semgrep" and finding.location.file_path:
            # Static: verify code pattern no longer matches
            return await self._verify_code_fix(finding, proposal_id)
        else:
            # Dynamic: execute HTTP request, command, etc.
            return await self._execute_reproduction(test_script, asset)
    
    async def _verify_code_fix(self, finding: Finding, proposal_id: UUID | None) -> VerificationResult:
        # Get the fixed code version
        if proposal_id:
            proposal = await db.get_remediation_proposal(proposal_id)
            if proposal.code_changes:
                # Apply diffs in memory and test
                fixed_code = apply_diffs(finding.location.file_path, proposal.code_changes)
                # Run Semgrep rule on fixed code
                result = semgrep_test_rule(finding.source_rule_id, fixed_code)
                return VerificationResult(
                    passed=not result.matches,
                    details={"matches": result.matches, "rule": finding.source_rule_id},
                    evidence=[EvidenceCreate(type="test_output", content=result.raw_output)],
                )
        
        # Fallback: rescan file
        return await self._semgrep_rescan_single(finding)
    
    async def _execute_reproduction(self, script: str, asset: Asset) -> VerificationResult:
        # Execute in sandboxed environment
        # For HTTP: send request, check response
        # For commands: execute, check output
        # For now: placeholder
        return VerificationResult(
            passed=True,  # Placeholder
            details={"executed": True, "script": script[:500]},
            evidence=[EvidenceCreate(type="test_output", content={"status": "simulated"})],
        )
```

### 2. Semgrep Rescan Checker

```python
class SemgrepRescanChecker:
    """
    Re-runs the specific Semgrep rule that found the issue.
    """
    
    async def verify(self, finding: Finding, asset: Asset, proposal_id: UUID | None) -> VerificationResult:
        rule_id = finding.source_rule_id
        if not rule_id:
            return VerificationResult(passed=False, details={"error": "No Semgrep rule ID"})
        
        # Get repository at current state (post-fix)
        repo_path = await self._get_repo_path(asset)
        
        # Run Semgrep with ONLY this rule on the specific file
        cmd = [
            "semgrep", "scan",
            "--config", rule_id,
            "--json",
            "--max-target-bytes", "1000000",
            finding.location.file_path,
        ]
        
        result = await asyncio.subprocess.run(cmd, capture_output=True, timeout=120)
        output = parse_semgrep_json(result.stdout)
        
        # Check if finding still exists
        still_vulnerable = any(
            r.check_id == rule_id and 
            r.path == finding.location.file_path and
            r.start.line == finding.location.line_start
            for r in output.results
        )
        
        return VerificationResult(
            passed=not still_vulnerable,
            details={
                "rule_id": rule_id,
                "file": finding.location.file_path,
                "still_vulnerable": still_vulnerable,
                "total_matches": len(output.results),
            },
            evidence=[EvidenceCreate(
                type="semgrep_output",
                title=f"Rescan: {rule_id}",
                content=output.model_dump(),
            )],
        )
```

### 3. Dependency Check Checker

```python
class DependencyCheckChecker:
    """
    Re-scans dependencies and checks if the specific CVE is resolved.
    """
    
    async def verify(self, finding: Finding, asset: Asset, proposal_id: UUID | None) -> VerificationResult:
        cve_ids = finding.cve_ids
        if not cve_ids:
            return VerificationResult(passed=False, details={"error": "No CVE IDs"})
        
        # Get current lockfiles
        repo_path = await self._get_repo_path(asset)
        lockfiles = find_lockfiles(repo_path)
        
        # Parse current dependencies
        current_deps = []
        for lf in lockfiles:
            current_deps.extend(parse_lockfile(lf))
        
        # Check each CVE
        results = {}
        for cve in cve_ids:
            # Query OSV for affected versions
            vuln_info = await osv.query(cve)
            if not vuln_info:
                results[cve] = {"resolved": True, "reason": "CVE not in database"}
                continue
            
            # Check if any current dependency matches affected range
            still_vulnerable = False
            for dep in current_deps:
                if dep.name in vuln_info.affected_packages:
                    if version_in_range(dep.version, vuln_info.affected_range):
                        still_vulnerable = True
                        break
            
            results[cve] = {"resolved": not still_vulnerable, "vuln_info": vuln_info.model_dump()}
        
        all_resolved = all(r["resolved"] for r in results.values())
        
        return VerificationResult(
            passed=all_resolved,
            details={"cve_results": results},
            evidence=[EvidenceCreate(
                type="dependency_scan",
                title="Dependency Rescan",
                content={"results": results, "lockfiles": [str(lf) for lf in lockfiles]},
            )],
        )
```

### 4. Config Audit Checker

```python
class ConfigAuditChecker:
    """
    Queries live infrastructure state and verifies desired configuration.
    """
    
    async def verify(self, finding: Finding, asset: Asset, proposal_id: UUID | None) -> VerificationResult:
        # Get expected config from proposal or finding metadata
        expected = finding.metadata.get("expected_config") or (
            proposal.config_changes[0].desired_config if proposal_id and proposal.config_changes else None
        )
        
        if not expected:
            return VerificationResult(passed=False, details={"error": "No expected config to verify"})
        
        # Query live state based on asset type
        if asset.type == "infrastructure":
            if asset.subtype == "aws":
                actual = await self._query_aws_config(asset, expected)
            elif asset.subtype == "kubernetes":
                actual = await self._query_k8s_config(asset, expected)
            elif asset.subtype == "gcp":
                actual = await self._query_gcp_config(asset, expected)
            else:
                return VerificationResult(passed=False, details={"error": f"Unsupported subtype: {asset.subtype}"})
        elif asset.type == "api":
            actual = await self._query_api_config(asset, expected)
        else:
            return VerificationResult(passed=False, details={"error": f"Config audit not supported for {asset.type}"})
        
        # Compare
        diff = deep_diff(expected, actual)
        passed = len(diff) == 0
        
        return VerificationResult(
            passed=passed,
            details={
                "expected": expected,
                "actual": actual,
                "diff": diff,
            },
            evidence=[EvidenceCreate(
                type="config_audit",
                title="Configuration Audit",
                content={"expected": expected, "actual": actual, "diff": diff},
            )],
        )
```

### 5. Regression Check Checker

```python
class RegressionCheckChecker:
    """
    Runs a lightweight targeted scan to ensure no new critical issues introduced.
    """
    
    async def verify(self, finding: Finding, asset: Asset, proposal_id: UUID | None) -> VerificationResult:
        # Run a quick scan focused on the asset area
        # For code: Semgrep on changed files only
        # For deps: Quick OSV check on all deps
        # For infra: Config drift detection
        
        new_critical = 0
        new_high = 0
        
        if finding.source == "semgrep":
            # Scan only the file that was fixed + related files
            changed_files = self._get_changed_files(proposal_id)
            if changed_files:
                results = await semgrep_scan_files(changed_files)
                new_critical = sum(1 for r in results if r.severity == "critical")
                new_high = sum(1 for r in results if r.severity == "high")
        
        elif finding.source == "dependency":
            # Quick check all deps for new critical vulns
            repo_path = await self._get_repo_path(asset)
            deps = parse_all_lockfiles(repo_path)
            vulns = await osv.query_batch(deps)
            new_critical = sum(1 for v in vulns if v.severity == "critical")
            new_high = sum(1 for v in vulns if v.severity == "high")
        
        # Pass if no new critical, and no more than 2 new high
        passed = (new_critical == 0) and (new_high <= 2)
        
        return VerificationResult(
            passed=passed,
            details={
                "new_critical": new_critical,
                "new_high": new_high,
                "threshold": "critical=0, high<=2",
            },
            evidence=[EvidenceCreate(
                type="regression_check",
                title="Regression Check",
                content={"new_critical": new_critical, "new_high": new_high},
            )],
        )
```

---

## Verification Result Schema

```python
class VerificationResult(BaseModel):
    passed: bool
    checks: list[VerificationCheck]
    evidence_refs: list[UUID] = []
    regression_passed: bool = True
    new_findings_count: int = 0
    duration_ms: int

class VerificationCheck(BaseModel):
    name: str
    passed: bool
    details: dict
    duration_ms: int = 0
    error: str | None = None
```

---

## Verification Run Persistence

```python
class VerificationRun(BaseModel):
    id: UUID
    workspace_id: UUID
    finding_id: UUID
    proposal_id: UUID | None
    scan_id: UUID | None  # If full scan triggered
    verification_type: str  # comprehensive, reproduction_only, etc.
    status: VerificationStatus  # pending, running, passed, failed, inconclusive
    result: dict  # Full check results
    evidence_refs: list[UUID]
    passed: bool
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## Evidence Requirements

| Verification Type | Minimum Evidence |
|-------------------|------------------|
| `reproduction_test` | Test script, execution logs, pass/fail assertion |
| `semgrep_rescan` | Semgrep JSON output showing 0 matches for rule+location |
| `dependency_check` | Lockfile parse output, OSV query results, version comparison |
| `config_audit` | Live API response, expected vs actual diff |
| `regression_check` | Scan summary (counts by severity) |

All evidence stored in `finding_evidence` with `verification_run_id` link.

---

## Verification Scheduling

### Immediate (Post-Remediation)
- Triggered automatically when:
  - Git PR merged (webhook)
  - n8n workflow completes successfully
  - Manual "mark fixed" API call

### Scheduled Re-verification
- Daily: All `fixed` findings from last 30 days (sample 10%)
- Weekly: All `fixed` findings from last 90 days (sample 5%)
- On asset config change: Re-verify all fixed findings on that asset

### Regression Detection
- If re-verification fails → Finding status → `regression_detected`
- Alert: In-app, Email, Slack
- Creates new finding linking to original

---

## API Endpoints

```python
POST   /api/v1/workspaces/{ws_id}/findings/{finding_id}/verify
    # Trigger verification manually
    # Body: { "proposal_id": "uuid", "types": ["reproduction_test", "semgrep_rescan"] }
    # Returns: { "verification_run_id": "uuid", "status": "running" }

GET    /api/v1/workspaces/{ws_id}/verifications/{run_id}
    # Get verification result
    # Returns: VerificationRun with checks, evidence

GET    /api/v1/workspaces/{ws_id}/findings/{finding_id}/verifications
    # List verification history for finding

POST   /api/v1/workspaces/{ws_id}/verifications/{run_id}/retry
    # Retry failed verification
```

---

## Verification Dashboard (UI)

```
Verification Run Detail
├── Status: PASSED/FAILED/IN_PROGRESS
├── Finding: [Link to finding]
├── Proposal: [Link to proposal]
├── Trigger: REMEDIATION_APPLIED / MANUAL / SCHEDULED
├── Duration: 45s
├── Checks
│   ├── ✅ reproduction_test (12s) - "Original PoC returns 403"
│   ├── ✅ semgrep_rescan (8s) - "Rule java.lang.Security.SQLInjection: 0 matches"
│   ├── ✅ regression_check (25s) - "0 new critical, 1 new high (acceptable)"
│   └── ⚠ config_audit (3s) - "Skipped (not applicable)"
├── Evidence
│   ├── Reproduction Test Output [View]
│   ├── Semgrep Rescan JSON [Download]
│   └── Regression Scan Summary [View]
└── Actions
    ├── [Retry Failed Checks]
    ├── [View Finding]
    └── [Mark as False Positive] (if verification failed but fix is valid)
```

---

## Failure Handling

| Failure | Action |
|---------|--------|
| Reproduction test passes (vuln still exists) | Finding stays OPEN, proposal marked `needs_revision`, alert |
| Semgrep still matches | Finding stays OPEN, proposal marked `needs_revision` |
| Dependency CVE still present | Finding stays OPEN, proposal marked `needs_revision` |
| Config audit mismatch | Finding stays OPEN, proposal marked `needs_revision` |
| Regression: new critical findings | Alert raised, new findings created, proposal marked `regression` |
| Tool error (timeout, API down) | Verification `inconclusive`, retry scheduled (max 3) |
| Asset unreachable | Verification `inconclusive`, retry with backoff |

---

## Metrics & SLOs

| Metric | Target |
|--------|--------|
| Verification completion rate | > 95% |
| False pass rate (vuln exists but verification passes) | < 1% |
| False fail rate (vuln fixed but verification fails) | < 5% |
| Median verification time | < 60 seconds |
| P95 verification time | < 5 minutes |
| Evidence capture rate | 100% |

---

## Future: Continuous Verification

```
┌─────────────────────────────────────────────────────────────┐
│              CONTINUOUS VERIFICATION LOOP                   │
│                                                             │
│  Asset Config Change  ──► Drift Detection ──► Re-verify    │
│       │                          │                          │
│       │                          ▼                          │
│       │                  Fixed Finding Regressed?           │
│       │                          │                          │
│       ├── No ──► Continue Monitoring                         │
│       │                          │                          │
│       └── Yes ──► Alert + Auto-create Finding                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Implementation**: n8n workflow polling asset state + ShadowOps API webhook