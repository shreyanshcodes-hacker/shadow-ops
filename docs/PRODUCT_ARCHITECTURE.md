# PRODUCT ARCHITECTURE

## Product Definition

**ShadowOps** is an AI-native cybersecurity SaaS platform that functions as an "AI Security Team" for startups and engineering organizations.

### Core Promise

ShadowOps continuously helps authorized teams:
- **Discover** vulnerabilities across authorized applications, repositories, APIs, and infrastructure
- **Analyze** findings with AI-powered security expertise
- **Correlate** findings into attack paths
- **Prioritize** risk based on deterministic, explainable models
- **Explain** results through contextual AI chat
- **Remediate** with AI-generated, human-approved fixes
- **Verify** that fixes actually work
- **Report** security posture to stakeholders

### Tagline

> "Your AI Security Team. Always Watching."

### Security Boundary (Non-Negotiable)

> **NO AUTHORIZATION → NO SCAN**

This rule is enforced at the **backend layer only**. The frontend is never a security boundary.

---

## Target Users & Needs

| User Persona | Primary Needs | ShadowOps Value |
|-------------|--------------|-----------------|
| **Startup Founders** | Security visibility without hiring security team; investor-ready reports | Executive dashboards, automated compliance reporting, continuous monitoring |
| **CTOs** | Strategic risk view; resource allocation for security; board communication | Risk scoring, attack path visualization, prioritization, executive reports |
| **Engineering Teams** | Actionable findings in workflow; minimal false positives; fast remediation | IDE-friendly findings, AI remediation proposals, PR integration, verification |
| **Security Engineers** | Deep technical analysis; custom rules; hunt capabilities | Semgrep rule authoring, attack path exploration, evidence chains, audit logs |
| **Developers** | Understand vulnerabilities in their code; guided fixes | Contextual AI explanations, code-level evidence, remediation snippets |
| **DevOps Teams** | Pipeline integration; infrastructure scanning; deployment gates | CI/CD integration, infrastructure-as-code analysis, automated verification |
| **Security Consultants** | Multi-client management; professional reporting; evidence provenance | Workspace isolation, client-scoped assets, professional report templates, audit trails |

---

## Core Product Loop (21 Steps)

```
1.  USER AUTHENTICATES
    ↓
2.  USER ENTERS/CREATES WORKSPACE
    ↓
3.  USER ADDS AN ASSET
    ↓
4.  USER PROVIDES/RECORDS AUTHORIZATION
    ↓
5.  SHADOWOPS VALIDATES AUTHORIZATION (BACKEND)
    ↓
6.  SCAN BEGINS
    ↓
7.  RECON / SECURITY ANALYSIS OCCURS
    ↓
8.  CODE / DEPENDENCY ANALYSIS (WHERE APPLICABLE)
    ↓
9.  AI SECURITY MANAGER COORDINATES AGENTS
    ↓
10. FINDINGS ARE GENERATED
    ↓
11. EVIDENCE IS COLLECTED & STORED
    ↓
12. FINDINGS ARE CORRELATED
    ↓
13. RISK IS CALCULATED (DETERMINISTIC)
    ↓
14. ATTACK PATHS ARE CONSTRUCTED
    ↓
15. AI GENERATES REMEDIATION PROPOSALS
    ↓
16. HUMAN APPROVES REMEDIATION
    ↓
17. FIX APPLIED VIA AUTHORIZED WORKFLOW ONLY
    ↓
18. VERIFICATION RUNS
    ↓
19. SECURITY SCORE RECALCULATED
    ↓
20. REPORTS ARE GENERATED
    ↓
21. AI SECURITY CHAT EXPLAINS RESULTS
```

---

## Product Principles

1. **Authorization-First** — No scan without verified authorization
2. **Evidence-Based** — Every finding has provenance and evidence
3. **Human-in-the-Loop** — AI proposes, humans approve, system executes
4. **Explainable Risk** — Scores are deterministic and auditable
5. **Workspace Isolation** — Zero data leakage between workspaces
6. **Audit Everything** — Security actions are logged immutably
7. **AI as Analyst, Not Actor** — AI analyzes and proposes; never executes destructively
8. **Continuous, Not Point-in-Time** — Ongoing monitoring, not one-off scans