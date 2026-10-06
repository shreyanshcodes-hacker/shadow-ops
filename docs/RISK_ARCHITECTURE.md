# RISK ARCHITECTURE

## Design Principles

1. **Deterministic** — Same inputs always produce same score (no AI randomness in final score)
2. **Explainable** — Every point traceable to factors with weights
3. **Configurable** — Weights adjustable per workspace (Enterprise)
4. **Auditable** — Full calculation trace stored in `risk_assessments.factors`
5. **AI-Augmented** — AI provides analysis inputs; engine computes final score
6. **Bounded** — 0-100 scale, no arbitrary inflation

---

## Risk Factors

| Factor | Source | Range | Weight | Description |
|--------|--------|-------|--------|-------------|
| **Base Severity** | Finding.severity | 0-100 | 30% | CVSS-like base from tool/AI |
| **Exploitability** | AI/Tool analysis | 0-100 | 20% | How easily can this be exploited |
| **Exposure** | Recon + Asset config | 0-100 | 15% | Network accessibility (internet-facing = higher) |
| **Asset Criticality** | Asset.criticality | 0-100 | 15% | Business impact of asset compromise |
| **Confidence** | Finding.confidence | 0-100 | 10% | Certainty the finding is real |
| **Attack Path Impact** | Attack path engine | 0-100 | 10% | Additional risk from chained paths |

---

## Severity → Base Score Mapping

```python
SEVERITY_BASE_SCORES = {
    "critical": 95,
    "high": 75,
    "medium": 50,
    "low": 25,
    "info": 10,
}

# AI/Tool can override with specific CVSS
def calculate_base_score(finding: Finding) -> float:
    if finding.cvss_score:
        return finding.cvss_score  # 0-100 scale
    return SEVERITY_BASE_SCORES.get(finding.severity, 50)
```

---

## Exploitability Scoring

```python
def calculate_exploitability(finding: Finding, ai_analysis: ThreatAnalysis | None) -> float:
    """
    Factors:
    - Public exploit available (CVE with exploit-db/Metasploit)
    - Authentication required (none = higher)
    - Complexity (low = higher)
    - User interaction required (none = higher)
    - AI threat analyst scenario likelihood
    """
    score = 50  # Baseline
    
    # Public exploit
    if finding.cve_ids:
        for cve in finding.cve_ids:
            if exploit_db.has_exploit(cve):
                score += 30
                break
    
    # Authentication
    auth_required = finding.location.metadata.get("auth_required", True)
    if not auth_required:
        score += 20
    
    # Complexity (from AI or CVSS)
    complexity = finding.metadata.get("attack_complexity", "medium")
    if complexity == "low":
        score += 15
    elif complexity == "high":
        score -= 15
    
    # User interaction
    if not finding.metadata.get("user_interaction", False):
        score += 10
    
    # AI threat scenario likelihood
    if ai_analysis:
        max_likelihood = max((s.likelihood for s in ai_analysis.scenarios), default=0)
        score += max_likelihood * 20
    
    return clamp(score, 0, 100)
```

---

## Exposure Scoring

```python
def calculate_exposure(finding: Finding, asset: Asset, recon: ReconResult | None) -> float:
    """
    Network exposure of the vulnerable component
    """
    score = 20  # Baseline (internal)
    
    # Asset type baseline
    type_exposure = {
        "api": 70,           # Public API
        "application": 60,   # Web app
        "repository": 30,    # Code (supply chain)
        "infrastructure": 50, # Cloud infra
        "container": 40,     # Container registry
    }
    score = type_exposure.get(asset.type, 30)
    
    # Recon data refinement
    if recon:
        # Internet-facing endpoint?
        for ep in recon.endpoints:
            if ep.url in finding.affected_endpoints:
                if ep.source == "public":
                    score = max(score, 90)
                elif ep.source == "internal":
                    score = min(score, 40)
                break
        
        # Exposed service on same host?
        for svc in recon.exposed_services:
            if svc.port == finding.location.port:
                if "public" in svc.tags:
                    score = max(score, 85)
    
    # Network zone from asset config
    zone = asset.connection_config.get("network_zone", "private")
    zone_modifier = {"public": 20, "dmz": 10, "private": 0, "isolated": -20}
    score += zone_modifier.get(zone, 0)
    
    return clamp(score, 0, 100)
```

---

## Asset Criticality

```python
ASSET_CRITICALITY_SCORES = {
    "low": 20,
    "medium": 50,
    "high": 80,
    "critical": 95,
}

def calculate_asset_criticality(asset: Asset) -> float:
    base = ASSET_CRITICALITY_SCORES.get(asset.criticality, 50)
    
    # Adjust for data sensitivity tags
    tags = asset.tags or []
    if "pii" in tags:
        base += 10
    if "financial" in tags:
        base += 10
    if "hipaa" in tags:
        base += 15
    if "pci" in tags:
        base += 15
    if "production" in tags:
        base += 10
    
    return clamp(base, 0, 100)
```

---

## Confidence Scoring

```python
CONFIDENCE_SCORES = {
    "low": 30,
    "medium": 60,
    "high": 90,
}

def calculate_confidence(finding: Finding) -> float:
    base = CONFIDENCE_SCORES.get(finding.confidence, 60)
    
    # Tool findings have higher confidence
    if finding.source in ("semgrep", "dependency"):
        base = max(base, 70)
    
    # Multiple sources confirming
    if finding.deduplicated_from:
        base += min(len(finding.deduplicated_from) * 5, 20)
    
    # AI analysis confirmed
    if finding.ai_confirmed:
        base += 10
    
    return clamp(base, 0, 100)
```

---

## Attack Path Impact

```python
def calculate_attack_path_impact(finding: Finding, attack_paths: list[AttackPath]) -> float:
    """
    Additional risk from being part of attack chains
    """
    if not attack_paths:
        return 0
    
    max_boost = 0
    for path in attack_paths:
        # Check if finding is in this path
        finding_in_path = any(
            node.finding_id == finding.id 
            for node in path.nodes
        )
        if finding_in_path:
            # Boost based on path risk and position
            path_risk = path.risk_score  # 0-100
            position_factor = 1.0  # Entry point = 1.0, deeper = 0.7
            boost = path_risk * position_factor * 0.2  # Max 20 points per path
            max_boost = max(max_boost, boost)
    
    return clamp(max_boost, 0, 30)  # Cap at 30 points boost
```

---

## Final Risk Score Formula

```python
# Default weights (configurable per workspace)
DEFAULT_WEIGHTS = {
    "base_severity": 0.30,
    "exploitability": 0.20,
    "exposure": 0.15,
    "asset_criticality": 0.15,
    "confidence": 0.10,
    "attack_path_impact": 0.10,
}

def calculate_risk_score(
    finding: Finding,
    asset: Asset,
    recon: ReconResult | None,
    ai_threat: ThreatAnalysis | None,
    attack_paths: list[AttackPath],
    weights: dict[str, float] = DEFAULT_WEIGHTS,
) -> RiskAssessment:
    # Calculate each factor
    base_severity = calculate_base_score(finding)
    exploitability = calculate_exploitability(finding, ai_threat)
    exposure = calculate_exposure(finding, asset, recon)
    asset_criticality = calculate_asset_criticality(asset)
    confidence = calculate_confidence(finding)
    attack_path_impact = calculate_attack_path_impact(finding, attack_paths)
    
    # Weighted sum
    factors = {
        "base_severity": base_severity,
        "exploitability": exploitability,
        "exposure": exposure,
        "asset_criticality": asset_criticality,
        "confidence": confidence,
        "attack_path_impact": attack_path_impact,
    }
    
    final_score = sum(factors[k] * weights[k] for k in weights)
    final_score = clamp(final_score, 0, 100)
    
    # Build explanation
    explanation = build_explanation(factors, weights, final_score)
    
    return RiskAssessment(
        finding_id=finding.id,
        base_score=base_severity,
        exploitability=exploitability,
        exposure=exposure,
        asset_criticality=asset_criticality,
        confidence=confidence,
        attack_path_impact=attack_path_impact,
        final_score=final_score,
        factors=factors,
        formula_version="1.0",
        explanation=explanation,
    )
```

---

## Explanation Generation

```python
def build_explanation(factors: dict, weights: dict, final_score: float) -> str:
    lines = [f"Final Risk Score: {final_score:.1f}/100"]
    lines.append("")
    lines.append("Factor Breakdown:")
    
    # Sort by contribution
    contributions = {
        k: factors[k] * weights[k] 
        for k in factors
    }
    for factor, contrib in sorted(contributions.items(), key=lambda x: -x[1]):
        pct = (contrib / final_score * 100) if final_score > 0 else 0
        lines.append(f"  • {factor.replace('_', ' ').title()}: {factors[factor]:.1f} × {weights[factor]:.0%} = {contrib:.1f} ({pct:.0f}%)")
    
    lines.append("")
    lines.append("Key Drivers:")
    if factors["exposure"] > 80:
        lines.append("  • Highly exposed (internet-facing or DMZ)")
    if factors["exploitability"] > 80:
        lines.append("  • Trivially exploitable (public exploit, no auth)")
    if factors["asset_criticality"] > 80:
        lines.append("  • Critical business asset")
    if factors["attack_path_impact"] > 15:
        lines.append("  • Part of critical attack path")
    if factors["confidence"] < 50:
        lines.append("  ⚠ Low confidence — verify before prioritizing")
    
    return "\n".join(lines)
```

---

## Risk Levels (UI Display)

| Score Range | Label | Color | Action |
|-------------|-------|-------|--------|
| 90-100 | **Critical** | 🔴 Crimson | Immediate action, block deploy |
| 70-89 | **High** | 🟠 Orange | Fix within 7 days |
| 40-69 | **Medium** | 🟡 Amber | Fix within 30 days |
| 15-39 | **Low** | 🔵 Blue | Fix in next sprint |
| 0-14 | **Informational** | ⚪ Gray | Track, no immediate action |

---

## Attack Path Risk Scoring

```python
def calculate_attack_path_risk(path: AttackPath) -> float:
    """
    Aggregate risk of an attack path
    """
    if not path.nodes:
        return 0
    
    # Node risk contributions
    node_risks = [n.risk_contribution for n in path.nodes if n.risk_contribution > 0]
    if not node_risks:
        return 0
    
    # Path risk = max node risk + edge likelihood propagation
    max_node_risk = max(node_risks)
    
    # Edge propagation: multiply likelihoods along path
    edge_likelihood = 1.0
    for edge in path.edges:
        edge_likelihood *= (edge.likelihood / 100)
    
    # Combine: high node risk + viable path = higher score
    path_risk = max_node_risk * (0.5 + 0.5 * edge_likelihood)
    
    return clamp(path_risk, 0, 100)
```

---

## Workspace Risk Aggregation

```python
def calculate_workspace_risk_score(workspace_id: UUID) -> WorkspaceRiskScore:
    # Get all open findings in workspace
    findings = db.get_open_findings(workspace_id)
    attack_paths = db.get_active_attack_paths(workspace_id)
    
    if not findings:
        return WorkspaceRiskScore(score=100, grade="A", factors={})
    
    # Asset-level scores
    asset_scores = {}
    for finding in findings:
        asset_id = finding.asset_id
        if asset_id not in asset_scores:
            asset_scores[asset_id] = []
        asset_scores[asset_id].append(finding.risk_score)
    
    # Average per asset, then average across assets
    asset_averages = [sum(scores)/len(scores) for scores in asset_scores.values()]
    raw_score = 100 - (sum(asset_averages) / len(asset_averages))
    
    # Attack path penalty
    path_penalty = sum(
        15 if p.risk_score > 80 else 8 if p.risk_score > 50 else 0
        for p in attack_paths
    )
    
    # Verified fix bonus
    recent_fixes = db.get_verified_fixes(workspace_id, days=30)
    fix_bonus = min(len(recent_fixes) * 2, 20)
    
    # Scan recency decay
    last_scan = db.get_last_full_scan(workspace_id)
    decay = 0
    if last_scan:
        days = (datetime.utcnow() - last_scan.completed_at).days
        decay = min(days, 30)
    
    final = clamp(raw_score - path_penalty + fix_bonus - decay, 0, 100)
    
    grade = score_to_grade(final)
    
    return WorkspaceRiskScore(
        score=final,
        grade=grade,
        factors={
            "finding_risk": 100 - raw_score,
            "attack_path_penalty": path_penalty,
            "fix_bonus": fix_bonus,
            "recency_decay": decay,
        },
        open_critical=sum(1 for f in findings if f.severity == "critical"),
        open_high=sum(1 for f in findings if f.severity == "high"),
        active_attack_paths=len(attack_paths),
    )
```

---

## Configuration (Enterprise)

```python
class RiskModelConfig(BaseModel):
    version: str = "1.0"
    weights: dict[str, float] = DEFAULT_WEIGHTS
    severity_base: dict[str, float] = SEVERITY_BASE_SCORES
    criticality_base: dict[str, float] = ASSET_CRITICALITY_SCORES
    confidence_base: dict[str, float] = CONFIDENCE_SCORES
    attack_path_boost_cap: float = 30.0
    workspace_decay_per_day: float = 1.0
    max_fix_bonus: float = 20.0
    
    # Custom factor functions (Python paths for Enterprise)
    custom_factors: list[str] = []
```

**Validation**: Weights must sum to 1.0. All scores clamped 0-100.

---

## Testing & Validation

### Unit Tests
- Each factor function tested in isolation
- Edge cases: missing data, extreme values, clamp boundaries
- Weight changes produce expected score shifts

### Golden Cases
| Scenario | Expected Score Range |
|----------|---------------------|
| Critical RCE, internet-facing, production DB, public exploit | 90-100 |
| High SQLi, internal API, no exploit, medium confidence | 60-75 |
| Medium XSS, public web app, user interaction required | 40-55 |
| Low info leak, internal tool, no exploit | 15-25 |
| False positive (confidence low) | 0-15 |

### Regression Tests
- Run on every risk model version change
- Compare scores for 1000+ historical findings
- Flag findings with >10 point shifts for review

---

## API: Risk Assessment Retrieval

```python
GET /api/v1/workspaces/{ws_id}/findings/{finding_id}/risk

Response:
{
  "finding_id": "uuid",
  "base_score": 95.0,
  "exploitability": 90.0,
  "exposure": 85.0,
  "asset_criticality": 80.0,
  "confidence": 85.0,
  "attack_path_impact": 18.0,
  "final_score": 87.3,
  "factors": {
    "base_severity": {"value": 95.0, "weight": 0.30, "contribution": 28.5},
    "exploitability": {"value": 90.0, "weight": 0.20, "contribution": 18.0},
    ...
  },
  "explanation": "Final Risk Score: 87.3/100\n\nFactor Breakdown:\n  • Base Severity: 95.0 × 30% = 28.5 (33%)\n  ...",
  "risk_level": "critical",
  "calculated_at": "2024-01-15T10:30:00Z",
  "formula_version": "1.0"
}
```