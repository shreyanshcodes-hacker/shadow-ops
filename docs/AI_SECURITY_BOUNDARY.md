# AI Security Boundary

## Principle

**AI output is informational only. It never directly triggers actions, modifies state, or controls system behavior.**

## Boundary Enforcement

### What AI Output CAN Do
- Be displayed to human reviewers in the UI
- Be stored in `finding_ai_analysis` table for audit trail
- Inform human triage decisions (status changes, remediation)
- Be referenced in reports

### What AI Output CANNOT Do

| Action | Prevention Mechanism |
|--------|---------------------|
| Execute shell commands | No command execution interface; AI only returns JSON |
| Modify database records | AI writes to `finding_ai_analysis` only via validated service layer |
| Trigger scans | No API endpoint accepts AI output as scan trigger |
| Deploy code | No deployment pipeline integration |
| Change finding status | Status changes require explicit human API call (`PATCH /findings`) |
| Modify assets | Asset modification requires admin API calls |
| Change permissions | AuthZ changes require explicit admin action |
| Make network requests | AI provider calls are backend-only, outbound only to provider APIs |
| Access filesystem | File access only via scanner (Semgrep), not AI |

## Data Flow Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                     HUMAN REVIEWER                          │
│  (Makes all decisions: triage, remediate, deploy, close)   │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ Reads AI analysis
                            │
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                         │
│  - Validates AI output against SecurityAnalysis schema      │
│  - Verifies evidence references exist                       │
│  - Stores in finding_ai_analysis (append-only)              │
│  - Creates audit log entries                                │
│  - NO automatic actions based on AI content                 │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ Structured JSON only
                            │
┌─────────────────────────────────────────────────────────────┐
│                      AI PROVIDER                             │
│  - Receives sanitized prompt with evidence                  │
│  - Returns SecurityAnalysis JSON                            │
│  - No tool use, no function calling                         │
│  - No persistent memory between requests                    │
└─────────────────────────────────────────────────────────────┘
```

## Explicit Prohibitions (Code-Level)

### 1. No Auto-Triage
```python
# FORBIDDEN - Never implemented
async def auto_triage_finding(finding_id, ai_analysis):
    if ai_analysis.confidence > 0.9:
        await finding_repo.update(finding_id, {"status": "triaged"})
```

### 2. No Auto-Remediation
```python
# FORBIDDEN - Stage 6+ territory
async def generate_and_apply_patch(finding_id, ai_analysis):
    patch = ai_analysis.recommended_next_steps[0]
    await git.apply(patch)
```

### 3. No Scan Triggering
```python
# FORBIDDEN
async def trigger_rescan_if_critical(ai_analysis):
    if ai_analysis.severity_assessment == "critical":
        await scan_service.create_scan(...)
```

### 4. No Status Changes
```python
# FORBIDDEN
async def close_finding_if_false_positive(ai_analysis):
    if "false positive" in ai_analysis.reasoning.lower():
        await finding_repo.update(finding_id, {"status": "false_positive"})
```

## Enforcement Checklist

- [x] AI provider only returns structured JSON (no tool use)
- [x] All AI output validated against `SecurityAnalysis` schema
- [x] Evidence references verified against actual evidence IDs
- [x] AI analysis stored in separate table (`finding_ai_analysis`)
- [x] No database triggers on `finding_ai_analysis` inserts
- [x] No webhooks/callbacks from AI analysis creation
- [x] Frontend displays "Advisory Only" badge on all AI content
- [x] Scanner facts (file, line, rule) stored separately in `findings` table
- [x] Finding status changes only via explicit `PATCH /findings/{id}`

## Audit Trail

Every AI analysis creates immutable audit records:
- `ai.analysis.requested` - User initiated
- `ai.analysis.started` - Provider call began
- `ai.analysis.completed` - Success with metadata
- `ai.analysis.failed` - Failure with error classification

These logs are **append-only** and cannot be modified by AI output.

## Future Stages

When Stage 6+ introduces remediation capabilities:
- Remediation proposals will be **separate entities** (`remediation_proposals` table)
- Proposals require **explicit human approval** (`PATCH /remediations/{id}/approve`)
- AI analysis may **inform** proposals but never **create** them autonomously
- All actions remain **human-authorized** with audit trail