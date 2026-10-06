# REMEDIATION ARCHITECTURE

## Core Principle

**AI proposes → Human approves → Authorized workflow executes → Verification confirms**

AI never directly modifies production systems. Every remediation action requires explicit human approval and runs through an authorized, auditable execution path.

---

## Remediation Workflow

```
FINDING (Open, Triaged)
      │
      ▼
AI REMEDIATION AGENT
      │
      ├─► Generates RemediationProposal
      │     • Code diff / Config patch / Commands
      │     • Test plan
      │     • Risk assessment of fix
      │     • Confidence score
      │
      ▼
HUMAN REVIEW (Dashboard)
      │
      ├─► APPROVE → RemediationApproval record
      │     • Approver, timestamp, justification
      │     • Conditions (e.g., "test in staging first")
      │
      ├─► REJECT → RemediationApproval record (rejected)
      │     • Required justification
      │
      └─► REQUEST CHANGES → Back to AI Agent
      
APPROVED PROPOSAL
      │
      ▼
AUTHORIZED EXECUTION WORKFLOW
      │
      ├─► Code Change → Git PR (GitHub/GitLab/Bitbucket)
      │     • PR created by ShadowOps bot
      │     • Requires standard code review + merge
      │     • ShadowOps tracks PR status
      │
      ├─► Config Change → Infrastructure API (Terraform, K8s, Cloud APIs)
      │     • Executed via n8n workflow with credentials
      │     • Requires workspace admin approval in n8n
      │     • Dry-run → Apply → Verify
      │
      ├─► Dependency Update → Dependabot-style PR
      │     • Automated PR with changelog
      │     • CI runs tests
      │
      └─► Infrastructure Change → n8n + Cloud CLI
            • Plan → Approve → Apply
            • State stored, rollback possible
      
      ▼
VERIFICATION PHASE
      │
      ├─► Triggered automatically on merge/apply
      ├─► Runs targeted scan / reproduction test
      ├─► VerificationRun record created
      │
      ▼
VERIFICATION RESULT
      │
      ├─► PASSED → Finding status = FIXED, security score recalculated
      │
      └─► FAILED → Finding stays OPEN, alert raised, proposal marked needs_revision
```

---

## Remediation Proposal Types

| Fix Type | Execution Method | Approval Required | Verification |
|----------|------------------|-------------------|--------------|
| `code_change` | Git PR | Code review + merge | Semgrep rescan + tests |
| `config_change` | n8n workflow (Terraform/K8s/Cloud CLI) | Workspace admin in n8n | Config audit + scan |
| `dependency_update` | Git PR (Dependabot-style) | Code review + merge | Dependency rescan + tests |
| `infrastructure_change` | n8n workflow (Terraform/Pulumi) | Workspace admin in n8n | Infra scan + drift detection |
| `waf_rule` | n8n → WAF API (Cloudflare, AWS WAF) | Security admin | Rule test + traffic test |
| `network_policy` | n8n → K8s/Cloud Network API | Platform admin | Connectivity test |
| `secret_rotation` | n8n → Vault/Secrets Manager | Security admin | Secret validation + app health |

---

## Remediation Proposal Schema

```python
class RemediationProposal(BaseModel):
    id: UUID
    workspace_id: UUID
    finding_id: UUID
    proposed_by: str  # "ai_manager", "remediation_agent"
    model_used: str  # "gemini-1.5-pro", "grok"
    
    title: str
    description: str
    
    fix_type: FixType  # code_change, config_change, dependency_update, etc.
    
    # For code changes
    code_changes: list[CodeChange] | None = None
    
    # For config changes
    config_changes: list[ConfigChange] | None = None
    
    # For dependency updates
    dependency_updates: list[DependencyUpdate] | None = None
    
    # For infrastructure
    infra_changes: list[InfraChange] | None = None
    
    # Generic commands (for manual/CLI execution)
    commands: list[str] = []
    
    # Prerequisites
    prerequisites: list[str] = []  # "Run tests in staging", "Backup database"
    
    # Risk of applying this fix
    risk_level: RiskLevel  # low, medium, high
    
    # AI confidence in this fix
    confidence: ConfidenceLevel  # low, medium, high
    
    # Estimated effort
    estimated_effort_hours: float
    
    # Test plan for verification
    test_plan: list[TestStep] = []
    
    # Status
    status: ProposalStatus  # proposed, approved, rejected, applied, superseded
    
    created_at: datetime
    updated_at: datetime
```

### CodeChange Schema

```python
class CodeChange(BaseModel):
    file_path: str
    unified_diff: str  # Standard unified diff format
    language: str
    description: str  # What this change does
    related_findings: list[UUID] = []  # Which findings this addresses
```

### ConfigChange Schema

```python
class ConfigChange(BaseModel):
    target: ConfigTarget  # terraform, kubernetes, aws, gcp, azure, docker, nginx, etc.
    resource_id: str  # e.g., "aws_security_group.sg-123", "k8s/deployment/myapp"
    current_config: dict  # Current state (for diff)
    desired_config: dict  # Desired state
    change_type: ConfigChangeType  # create, update, delete
    rollback_config: dict | None = None  # For manual rollback
    dry_run_output: str | None = None  # From n8n dry-run
```

### DependencyUpdate Schema

```python
class DependencyUpdate(BaseModel):
    package_manager: str  # npm, pip, maven, gradle, cargo, go
    package_name: str
    current_version: str
    target_version: str
    update_type: UpdateType  # patch, minor, major
    breaking_changes: list[str] = []
    changelog_url: str | None = None
    lockfile_paths: list[str] = []
```

### InfraChange Schema

```python
class InfraChange(BaseModel):
    tool: InfraTool  # terraform, pulumi, crossplane, helm, kubectl
    workspace: str  # Terraform workspace, K8s namespace, etc.
    plan_file: str | None = None  # Path to plan artifact
    apply_command: str  # Exact command to run
    rollback_command: str | None = None
    requires_approval: bool = True
```

---

## Human Approval Process

### Approval Requirements by Fix Type

| Fix Type | Minimum Approver Role | Additional Requirements |
|----------|----------------------|------------------------|
| `code_change` | Member | Standard PR review (2 approvals if branch protection) |
| `config_change` | Admin | n8n workflow approval + dry-run review |
| `dependency_update` | Member | CI passes + PR review |
| `infrastructure_change` | Admin | Terraform plan review + n8n approval |
| `waf_rule` | Admin | Security team review + staging test |
| `network_policy` | Admin | Platform team review + connectivity test |
| `secret_rotation` | Admin | Security team + on-call coordination |

### Approval Record

```python
class RemediationApproval(BaseModel):
    id: UUID
    proposal_id: UUID
    workspace_id: UUID
    approved_by: UUID  # User ID
    decision: Decision  # approved, rejected
    justification: str  # Required for rejection
    conditions: list[str] = []  # "Test in staging", "Deploy during maintenance window"
    approved_at: datetime
    expires_at: datetime | None = None  # Approval expires if not applied
```

### Approval UI Flow

```
Dashboard → Remediation Tab → Proposal Card
    │
    ├─► View: Diff, Test Plan, Risk Assessment, AI Reasoning
    │
    ├─► [Approve] → Modal: Conditions (optional) → Confirm
    │
    ├─► [Reject] → Modal: Justification (required) → Confirm
    │
    └─► [Request Changes] → Modal: Feedback → AI Agent regenerates
```

---

## Authorized Execution Workflows

### 1. Code Changes (Git PR)

```python
class GitPRExecutor:
    async def execute(self, proposal: RemediationProposal, approval: RemediationApproval) -> ExecutionResult:
        # 1. Clone repo (using asset credentials)
        repo = await self.clone_repo(proposal.asset)
        
        # 2. Create branch
        branch = f"shadowops/fix-{proposal.id}-{short_uuid()}"
        await repo.create_branch(branch)
        
        # 3. Apply each code change
        for change in proposal.code_changes:
            await repo.apply_diff(change.file_path, change.unified_diff)
        
        # 4. Commit
        commit_msg = f"fix(security): {proposal.title}\n\nShadowOps Proposal: {proposal.id}\nFinding: {proposal.finding_id}"
        await repo.commit(commit_msg)
        
        # 5. Push
        await repo.push(branch)
        
        # 6. Create PR
        pr = await self.create_pr(
            repo=proposal.asset,
            title=f"[Security] {proposal.title}",
            body=self.generate_pr_body(proposal, approval),
            head=branch,
            base=proposal.asset.default_branch,
        )
        
        # 7. Track PR
        await db.create_remediation_tracking(proposal.id, pr.url, pr.number)
        
        return ExecutionResult(
            success=True,
            execution_type="git_pr",
            reference=pr.url,
            metadata={"pr_number": pr.number, "branch": branch},
        )
```

**PR Body Template**:
```markdown
## Security Fix: {proposal.title}

**Finding**: {finding.title} ({finding.severity})
**Risk Score**: {finding.risk_score}/100
**Proposal**: {proposal.id}
**Approved by**: {approver.name} at {approval.approved_at}

### Changes
{for each code_change: show file + diff summary}

### Test Plan
{proposal.test_plan}

### Verification
This PR will be verified by ShadowOps after merge. A targeted scan will run to confirm the fix.

### Rollback
Revert this PR if issues arise.
```

---

### 2. Config/Infrastructure Changes (n8n)

```python
class N8nWorkflowExecutor:
    async def execute(self, proposal: RemediationProposal, approval: RemediationApproval) -> ExecutionResult:
        # 1. Prepare workflow input
        workflow_input = {
            "proposal_id": str(proposal.id),
            "approval_id": str(approval.id),
            "config_changes": [c.model_dump() for c in proposal.config_changes],
            "infra_changes": [i.model_dump() for i in proposal.infra_changes],
            "dry_run": False,
            "approved_by": str(approval.approved_by),
            "approved_at": approval.approved_at.isoformat(),
        }
        
        # 2. Trigger n8n workflow (webhook)
        execution = await self.n8n.trigger_workflow(
            workflow_id="shadowops-remediation-apply",
            data=workflow_input,
        )
        
        # 3. Wait for completion (poll/webhook)
        result = await self.n8n.wait_for_execution(execution.id, timeout=1800)
        
        if result.status == "success":
            return ExecutionResult(
                success=True,
                execution_type="n8n_workflow",
                reference=result.execution_url,
                metadata=result.output,
            )
        else:
            # Attempt rollback if configured
            if proposal.rollback_commands:
                await self.execute_rollback(proposal.rollback_commands)
            raise ExecutionError(f"n8n workflow failed: {result.error}")
```

### n8n Workflow: `shadowops-remediation-apply`

```
Webhook Trigger
    │
    ▼
Validate Approval (check approval record exists, not expired)
    │
    ▼
DRY RUN (if config_change/infra_change)
    │  ├─► Terraform Plan / K8s Dry-run / Cloud API Preview
    │  └─► Store output for review
    │
    ▼
HUMAN APPROVAL NODE (n8n "Wait for Webhook" or "Approval" node)
    │  ├─► Workspace Admin reviews dry-run output in n8n UI
    │  └─► Approve → Continue | Reject → Stop & Notify
    │
    ▼
APPLY
    │  ├─► Terraform Apply / K8s Apply / Cloud API Call
    │  └─► Capture output, state
    │
    ▼
VERIFY
    │  ├─► Run verification checks (config audit, connectivity)
    │  └─► Store results
    │
    ▼
COMPLETE → Webhook back to ShadowOps backend
```

---

### 3. Dependency Updates

```python
class DependencyUpdater:
    async def execute(self, proposal: RemediationProposal) -> ExecutionResult:
        # Similar to GitPRExecutor but specialized for dependency files
        # 1. Update lockfiles (package-lock.json, Cargo.lock, etc.)
        # 2. Run package manager install to verify resolution
        # 3. Run project tests (if test command known)
        # 4. Create PR with changes
        pass
```

---

## Verification Architecture

### Verification Types

| Type | Description | When Used |
|------|-------------|-----------|
| `reproduction_test` | Re-run original exploit/PoC, expect failure | All findings with known reproduction |
| `semgrep_rescan` | Run Semgrep on changed files, finding should disappear | Code findings |
| `dependency_check` | Re-scan dependencies, CVE should be resolved | Dependency findings |
| `config_audit` | Query live config, verify desired state | Config/infra changes |
| `regression_check` | Full scan, ensure no new critical findings | All remediations |

### Verification Runner

```python
class VerificationRunner:
    async def verify(self, proposal: RemediationProposal, finding: Finding) -> VerificationResult:
        checks = []
        all_passed = True
        
        # 1. Reproduction test (if available)
        if finding.reproduction_steps:
            result = await self.run_reproduction_test(finding)
            checks.append(VerificationCheck(name="reproduction_test", passed=result.passed, details=result.details))
            all_passed = all_passed and result.passed
        
        # 2. Source-specific verification
        if finding.source == "semgrep":
            result = await self.run_semgrep_rescan(finding, proposal)
            checks.append(VerificationCheck(name="semgrep_rescan", passed=result.passed, details=result.details))
            all_passed = all_passed and result.passed
        
        elif finding.source == "dependency":
            result = await self.run_dependency_rescan(finding)
            checks.append(VerificationCheck(name="dependency_check", passed=result.passed, details=result.details))
            all_passed = all_passed and result.passed
        
        elif finding.source in ("recon", "config"):
            result = await self.run_config_audit(finding, proposal)
            checks.append(VerificationCheck(name="config_audit", passed=result.passed, details=result.details))
            all_passed = all_passed and result.passed
        
        # 3. Regression check (lightweight)
        result = await self.run_regression_check(finding.asset_id)
        checks.append(VerificationCheck(name="regression_check", passed=result.passed, details=result.details))
        all_passed = all_passed and result.passed
        
        # 4. Persist verification run
        verification = VerificationRun(
            finding_id=finding.id,
            proposal_id=proposal.id,
            verification_type="comprehensive",
            status="passed" if all_passed else "failed",
            result={"checks": [c.model_dump() for c in checks]},
            passed=all_passed,
        )
        await db.insert(verification)
        
        # 5. Update finding status
        if all_passed:
            await db.update_finding(finding.id, {"status": "fixed", "fixed_at": datetime.utcnow()})
            await recalculate_workspace_score(finding.workspace_id)
        
        return VerificationResult(passed=all_passed, checks=checks)
```

---

## Remediation Tracking & Status

### Proposal Lifecycle

```
PROPOSED
    │
    ├─► APPROVED → APPLIED → VERIFIED → FIXED (Finding)
    │                │
    │                └─► VERIFICATION FAILED → NEEDS_REVISION
    │
    ├─► REJECTED → (Closed)
    │
    ├─► SUPERSEDED (New proposal for same finding)
    │
    └─► EXPIRED (Approval expired, not applied)
```

### Tracking Table

```python
class RemediationTracking(BaseModel):
    proposal_id: UUID
    execution_type: ExecutionType  # git_pr, n8n_workflow, manual
    reference: str  # PR URL, n8n execution URL, ticket ID
    external_id: str | None = None  # PR number, n8n execution ID
    status: TrackingStatus  # pending, in_progress, completed, failed
    applied_at: datetime | None = None
    verified_at: datetime | None = None
    verification_run_id: UUID | None = None
    error: str | None = None
```

---

## Audit Trail

Every remediation action creates audit log entries:

| Action | Audit Log |
|--------|-----------|
| Proposal generated | `remediation.proposal.created` |
| Proposal viewed | `remediation.proposal.viewed` |
| Approval granted | `remediation.approval.granted` (with conditions) |
| Approval rejected | `remediation.approval.rejected` (with justification) |
| Execution started | `remediation.execution.started` |
| Execution completed | `remediation.execution.completed` (with output ref) |
| Execution failed | `remediation.execution.failed` (with error) |
| Verification run | `remediation.verification.run` |
| Verification passed | `remediation.verification.passed` |
| Verification failed | `remediation.verification.failed` |
| Finding fixed | `finding.status.changed` (to fixed) |

---

## Rollback Strategy

### Automatic Rollback Triggers
- Verification fails after apply
- Health checks fail post-deploy
- Alert firing on affected service

### Rollback Methods by Type

| Fix Type | Rollback Method |
|----------|-----------------|
| Git PR | Revert PR (creates new PR) |
| Terraform | `terraform apply -refresh-only` with previous state |
| K8s | `kubectl rollout undo` |
| Cloud API | Apply previous config (stored in rollback_config) |
| WAF Rule | Disable/delete rule |
| Network Policy | Revert to previous policy |
| Secret Rotation | Restore previous version from Vault |

### Rollback Record

```python
class RemediationRollback(BaseModel):
    proposal_id: UUID
    tracking_id: UUID
    triggered_by: UUID  # User or "auto_verification_failed"
    reason: str
    method: str  # revert_pr, terraform_rollback, k8s_rollback, etc.
    status: RollbackStatus  # initiated, completed, failed
    executed_at: datetime
    completed_at: datetime | None = None
```

---

## Notifications

| Event | Channels | Recipients |
|-------|----------|------------|
| Proposal generated | In-app, Email | Finding assignee, workspace admins |
| Approval needed | In-app, Slack | Workspace admins, security team |
| Approval granted | In-app | Proposer, finding assignee |
| Approval rejected | In-app, Email | Proposer, finding assignee |
| Execution started | In-app | Approver, finding assignee |
| Execution completed | In-app, Slack | Workspace members |
| Execution failed | In-app, Slack, PagerDuty | Workspace admins, on-call |
| Verification passed | In-app, Email | All stakeholders |
| Verification failed | In-app, Slack, PagerDuty | Workspace admins, on-call |

---

## Cost & Time Estimates

| Fix Type | Avg AI Cost | Avg Human Review Time | Avg Execution Time | Verification Time |
|----------|-------------|----------------------|-------------------|-------------------|
| Code change (simple) | $0.10 | 10 min | 5 min (PR) | 3 min |
| Code change (complex) | $0.30 | 30 min | 10 min (PR) | 5 min |
| Config change | $0.05 | 15 min | 10 min (n8n) | 5 min |
| Dependency update | $0.02 | 5 min | 5 min (PR) | 3 min |
| Infrastructure change | $0.10 | 30 min | 20 min (n8n) | 10 min |
| WAF rule | $0.05 | 10 min | 5 min (n8n) | 3 min |

**Total AI Cost per Scan**: Typically $2-5 for all remediation proposals