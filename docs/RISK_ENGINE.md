# Risk Engine Documentation

## Overview

The Risk Engine is a deterministic scoring system that calculates a 0-100 risk score for attack paths based on explicit, auditable factors. It is designed to be:

- **Deterministic**: Same inputs always produce the same score
- **Explainable**: Every factor contribution is visible
- **Versioned**: Model version stored with every calculation
- **AI-free**: No LLM involvement in final numerical score

## Risk Model v1 (risk-v1)

### Formula

```
Risk Score = Σ (factor_weight × factor_value × 100)
```

Where each factor_value is normalized to 0.0-1.0.

### Weights (sum = 1.0)

| Factor | Weight | Description |
|--------|--------|-------------|
| SEVERITY | 30% | Maximum finding severity in path |
| EXPLOITABILITY | 20% | Likelihood of successful exploitation |
| IMPACT | 20% | Potential damage if exploited |
| CONFIDENCE | 15% | Certainty of the analysis |
| EXPOSURE | 10% | External accessibility |
| PATH_COMPLEXITY | 5% | Attack path length/complexity |

### Factor Calculations

#### SEVERITY (30%)
- Maps finding severity to 0.0-1.0:
  - CRITICAL → 1.0
  - HIGH → 0.8
  - MEDIUM → 0.6
  - LOW → 0.4
  - INFO → 0.2
- Takes maximum across all findings in path
- Contribution: `max_severity × 0.30 × 100` (max 30 points)

#### EXPLOITABILITY (20%)
- Uses edge confidences (relationship confidence) as proxy
- Average of all edge confidences in path
- Falls back to 0.5 (neutral) if no edges
- Contribution: `avg_edge_confidence × 0.20 × 100` (max 20 points)

#### IMPACT (20%)
- Checks for IMPACT node type (0.8)
- Checks for BOUNDARY node type (0.7) - indicates privilege escalation
- Falls back to 0.5
- Takes maximum
- Contribution: `max_impact × 0.20 × 100` (max 20 points)

#### CONFIDENCE (15%)
- Averages attack_path.confidence + edge confidences
- Falls back to 0.5
- Contribution: `avg_confidence × 0.15 × 100` (max 15 points)

#### EXPOSURE (10%)
- Entry point node present → 0.9 (externally accessible)
- Falls back to 0.5
- Contribution: `exposure × 0.10 × 100` (max 10 points)

#### PATH_COMPLEXITY (5%)
- Inverse relationship with length:
  - ≤2 nodes: 0.6
  - 3-4 nodes: 0.5
  - 5-6 nodes: 0.4
  - ≥7 nodes: 0.3
- Rationale: Longer paths = more steps to exploit = slightly lower risk
- Contribution: `complexity × 0.05 × 100` (max 5 points)

### Risk Bands

| Score Range | Band | Label |
|-------------|------|-------|
| 0-19 | INFORMATIONAL | Informational |
| 20-39 | LOW | Low |
| 40-59 | MEDIUM | Medium |
| 60-79 | HIGH | High |
| 80-100 | CRITICAL | Critical |

### Example Calculation

**Path**: 3 findings (CRITICAL, HIGH, MEDIUM), 2 edges (conf 0.8, 0.7), has entry point, 3 nodes

| Factor | Value | Weight | Contribution |
|--------|-------|--------|--------------|
| Severity | 1.0 (CRITICAL) | 30% | 30.0 |
| Exploitability | 0.75 (avg edge) | 20% | 15.0 |
| Impact | 0.8 (has impact node) | 20% | 16.0 |
| Confidence | 0.75 (path + edges) | 15% | 11.25 |
| Exposure | 0.9 (entry point) | 10% | 9.0 |
| Complexity | 0.5 (3 nodes) | 5% | 2.5 |
| **Total** | | | **83.75** → **84** |

**Risk Band**: CRITICAL (80-100)

### Persistence

Every calculation creates a `RiskSnapshot`:
```json
{
  "score": 84,
  "risk_band": "critical",
  "model_version": "risk-v1",
  "factors": [
    {"name": "severity", "weight": 0.30, "value": 1.0, "contribution": 30.0, "description": "..."},
    ...
  ],
  "explanation": "Risk Score: 84 / 100 (CRITICAL)\nModel: risk-v1\n\nContributing Factors:\n  severity              30.0  Maximum finding severity in path: CRITICAL\n  exploitability        15.0  Exploitability from relationship confidences: 0.75\n  ..."
}
```

### Versioning

- Model version stored in `AttackPath.risk_model_version` and `RiskSnapshot.model_version`
- Changing weights/formula requires new version (e.g., "risk-v2")
- Historical snapshots retain their version for trend analysis
- API returns `model_version` with every calculation

### API Usage

**Recalculate Risk**:
```
POST /attack-paths/{id}/recalculate-risk
→ RiskCalculationResult { score, risk_band, model_version, factors[], explanation }
```

**Get History**:
```
GET /attack-paths/{id}/risk-history
→ RiskSnapshot[] (chronological)
```

### Testing

Boundary value tests (score → band):
- 0 → INFORMATIONAL
- 19 → INFORMATIONAL
- 20 → LOW
- 39 → LOW
- 40 → MEDIUM
- 59 → MEDIUM
- 60 → HIGH
- 79 → HIGH
- 80 → CRITICAL
- 100 → CRITICAL

Determinism test: Same attack path → same score every time.

### Security

- Risk calculation runs server-side only
- No client-supplied factors accepted
- AI outputs are inputs (evidence) but never directly determine score
- All factors derived from stored data (findings, relationships, path structure)