# Risk Model v1 Specification

## Version
`risk-v1`

## Release Date
2025 (Stage 6)

## Formula

```
Score = Σ (weight_i × value_i × 100)
Score ∈ [0, 100]
```

### Weights

| Factor | Weight | Rationale |
|--------|--------|-----------|
| Severity | 0.30 | Direct measure of vulnerability criticality; highest weight |
| Exploitability | 0.20 | Likelihood of successful attack; derived from relationship evidence |
| Impact | 0.20 | Potential damage; indicated by path structure |
| Confidence | 0.15 | Certainty of analysis; reduces score when uncertain |
| Exposure | 0.10 | External accessibility; entry points increase risk |
| Path Complexity | 0.05 | Minor factor; longer paths slightly harder to exploit |

**Sum = 1.00**

### Factor Value Ranges
All factor values normalized to [0.0, 1.0]

### Maximum Contributions
| Factor | Max Contribution |
|--------|------------------|
| Severity | 30.0 |
| Exploitability | 20.0 |
| Impact | 20.0 |
| Confidence | 15.0 |
| Exposure | 10.0 |
| Path Complexity | 5.0 |
| **Total** | **100.0** |

## Factor Definitions

### Severity (weight: 0.30)
```
value = max(severity_to_value(f.severity) for f in path_findings)

severity_to_value:
  CRITICAL → 1.0
  HIGH     → 0.8
  MEDIUM   → 0.6
  LOW      → 0.4
  INFO     → 0.2
  default  → 0.0
```

### Exploitability (weight: 0.20)
```
value = mean(edge.confidence for edge in path_edges)
default = 0.5
```

### Impact (weight: 0.20)
```
values = []
if any(n.node_type == IMPACT): values.append(0.8)
if any(n.node_type == BOUNDARY): values.append(0.7)
value = max(values) if values else 0.5
```

### Confidence (weight: 0.15)
```
values = [path.confidence] + [edge.confidence for edge in path_edges]
value = mean(values)
default = 0.5
```

### Exposure (weight: 0.10)
```
value = 0.9 if any(n.node_type == ENTRY) else 0.5
```

### Path Complexity (weight: 0.05)
```
length = count(path_nodes)
if length <= 2:     value = 0.6
elif length <= 4:   value = 0.5
elif length <= 6:   value = 0.4
else:               value = 0.3
```

## Risk Bands

| Score Range | Band | Description |
|-------------|------|-------------|
| 0-19 | INFORMATIONAL | No significant risk identified |
| 20-39 | LOW | Minor risk, monitoring recommended |
| 40-59 | MEDIUM | Moderate risk, should be addressed |
| 60-79 | HIGH | Significant risk, prioritize remediation |
| 80-100 | CRITICAL | Critical risk, immediate action required |

## Determinism Guarantee

For identical attack path structure and finding data:
- Same factor values calculated
- Same weights applied
- Same score produced
- No randomness, no AI, no external state

## Persistence

Every calculation creates `RiskSnapshot` with:
- `score`: Integer 0-100
- `risk_band`: Enum value
- `model_version`: "risk-v1"
- `factors`: Full breakdown JSON
- `calculated_at`: Timestamp

## Migration Path

To update model (e.g., risk-v2):
1. Create new `RiskEngine` class with updated weights/formula
2. Increment `RISK_MODEL_VERSION` constant
3. Deploy - new calculations use v2
4. Historical snapshots retain v1 for comparison
5. AttackPath.risk_model_version updated on recalculation

## Testing Requirements

### Determinism
- Same AttackPath object → same score (1000 iterations)

### Boundary Values
| Score | Expected Band |
|-------|---------------|
| 0 | INFORMATIONAL |
| 19 | INFORMATIONAL |
| 20 | LOW |
| 39 | LOW |
| 40 | MEDIUM |
| 59 | MEDIUM |
| 60 | HIGH |
| 79 | HIGH |
| 80 | CRITICAL |
| 100 | CRITICAL |

### Factor Isolation
- Only severity varies → score changes predictably
- Only exploitability varies → score changes predictably
- etc.

### Edge Cases
- Empty path (no findings) → handled gracefully
- No edges → uses defaults
- Missing AI analyses → uses defaults
- All findings INFO → low severity score