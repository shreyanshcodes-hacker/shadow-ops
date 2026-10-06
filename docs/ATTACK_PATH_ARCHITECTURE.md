# Attack Path Architecture

## Overview

The Attack Path Intelligence system transforms isolated security findings into contextual security relationships, enabling risk-based prioritization through deterministic attack path generation and scoring.

## Core Components

### 1. Finding Relationships

**Model**: `FindingRelationship` (`models/__init__.py`)

Normalized relationships between two findings:
- `source_finding_id` → `target_finding_id`
- `relationship_type`: Controlled vocabulary (DEPENDS_ON, ENABLES, EXPOSES, LEADS_TO, SHARES_COMPONENT, SHARES_ENTRY_POINT, SHARES_DATA_FLOW, AMPLIFIES)
- `confidence`: 0.0-1.0
- `source`: DETERMINISTIC | AI_SUGGESTED | HUMAN_CONFIRMED
- `rationale`: Human-readable explanation
- `evidence_reference`: Optional JSON reference to supporting evidence

**Key Design Decisions**:
- AI suggestions are explicitly marked as `AI_SUGGESTED` - never authoritative
- Human confirmation upgrades to `HUMAN_CONFIRMED`
- Deterministic relationships are `DETERMINISTIC` (from code analysis)
- Unique constraint prevents duplicate relationships

### 2. Attack Paths

**Models**: `AttackPath`, `AttackPathNode`, `AttackPathEdge` (`models/__init__.py`)

**AttackPath**:
- Container for a correlated sequence of findings
- Linked to `asset_id` and `workspace_id`
- Status: DRAFT | ACTIVE | DISMISSED | RESOLVED
- `risk_score`: 0-100 (deterministic)
- `risk_model_version`: Versioned risk formula

**AttackPathNode**:
- Ordered nodes in the path (sequence)
- Types: ENTRY | FINDING | BOUNDARY | IMPACT
- Optional link to `Finding`
- Rationale for node inclusion

**AttackPathEdge**:
- Relationships between nodes
- Carries `relationship_type`, `confidence`, `source`, `rationale`
- Validates source/target belong to same attack path

### 3. Risk Snapshots

**Model**: `RiskSnapshot` (`models/__init__.py`)

Immutable historical record of risk calculations:
- `score`: 0-100
- `risk_band`: INFORMATIONAL | LOW | MEDIUM | HIGH | CRITICAL
- `model_version`: e.g., "risk-v1"
- `factors`: Full factor breakdown (JSONB)
- `calculated_at`: Timestamp

Never overwrites previous snapshots - enables trend analysis.

## Deterministic Correlation Engine

**Service**: `CorrelationEngine` (`services/correlation.py`)

Detects relationships without AI:
1. **Same file**: `SHARES_COMPONENT` (confidence 0.9)
2. **Nearby lines** (≤20): `DEPENDS_ON` (confidence 0.7-distance*0.02)
3. **Same component** (parent dir): `SHARES_COMPONENT` (0.8)
4. **Shared CWE**: `SHARES_DATA_FLOW` (0.6)
5. **Shared OWASP**: `SHARES_COMPONENT` (0.5)
6. **Injection → Auth**: `ENABLES` (0.6)
7. **Auth → Data Exposure**: `LEADS_TO` (0.5)
8. **Misconfig → Injection**: `ENABLES` (0.5)

All rationales are explicit and auditable.

## AI Relationship Analysis

**Service**: `AIRelationshipAnalyzer` (`services/correlation.py`)

Uses existing Stage 5 AI provider abstraction:
- Input: Two findings + evidence + AI analyses
- Output: Structured `RelationshipAnalysis` (type, confidence, rationale, required_evidence)
- Creates `AI_SUGGESTED` relationships
- Confidence threshold: ≥0.5
- Prompt injection defenses from Stage 5 reused

## Attack Path Builder

**Service**: `AttackPathBuilder` (`services/attack_path.py`)

Graph construction from validated relationships:
1. Build adjacency graph from relationships
2. Find entry points (no incoming edges)
3. DFS with cycle detection (max depth: 8 nodes)
4. Deduplicate paths by finding sequence
5. Create nodes with types (ENTRY/FINDING/BOUNDARY/IMPACT)
6. Create edges from relationships

**Safety Constraints**:
- Maximum 8 nodes per path (`MAX_PATH_NODES`)
- Maximum 20 edges per path (`MAX_PATH_EDGES`)
- Cycle detection prevents infinite recursion
- Workspace isolation enforced
- Asset isolation (paths within single asset by default)

## Deterministic Risk Engine

**Service**: `RiskEngine` (`services/risk.py`)

**Formula** (risk-v1):
```
Severity           30%  (max finding severity in path)
Exploitability     20%  (edge confidences + AI exploitability)
Impact             20%  (impact nodes + boundary nodes)
Confidence         15%  (path confidence + edge confidences)
Exposure           10%  (entry point presence)
Path Complexity     5%  (inverse of length)
```

**Risk Bands**:
- 0-19:   INFORMATIONAL
- 20-39:  LOW
- 40-59:  MEDIUM
- 60-79:  HIGH
- 80-100: CRITICAL

**Guarantees**:
- Deterministic: Same inputs → same score
- Explainable: Full factor breakdown with contributions
- Versioned: `risk_model_version` stored with every snapshot
- No AI in final score calculation

## API Endpoints

### Finding Relationships
- `GET /attack-paths/findings/{finding_id}/relationships` - List relationships
- `POST /attack-paths/relationships/{id}/confirm` - Human confirm AI suggestion
- `POST /attack-paths/relationships/{id}/dismiss` - Dismiss AI suggestion

### Attack Paths
- `GET /attack-paths` - List with filters (workspace, asset, status)
- `POST /attack-paths` - Create manual attack path
- `GET /attack-paths/{id}` - Full detail with nodes/edges
- `PATCH /attack-paths/{id}` - Update metadata
- `GET /attack-paths/{id}/nodes` - Path nodes
- `GET /attack-paths/{id}/edges` - Path edges
- `POST /attack-paths/{id}/recalculate-risk` - Recalculate risk
- `GET /attack-paths/{id}/risk-history` - Historical snapshots

### Correlation
- `POST /attack-paths/correlate/{finding_id}` - Deterministic correlation for finding
- `POST /attack-paths/correlate/workspace/{workspace_id}` - Full workspace correlation
- `POST /attack-paths/correlate/ai/{finding_a_id}/{finding_b_id}` - AI correlation

### Attack Path Generation
- `POST /attack-paths/generate/{asset_id}` - Build paths from relationships

### Finding → Attack Paths
- `GET /attack-paths/findings/{finding_id}/attack-paths` - Paths containing finding

## Frontend Pages

### `/attack-paths` - List Page
- Stats cards (total, critical, high, avg score)
- Asset filter dropdown
- Status tabs (all/active/draft/dismissed)
- Generate attack paths from assets
- Risk score display with band badge

### `/attack-paths/[id]` - Detail Page
- Risk score display with recalculate button
- Graph visualization (visual + textual for accessibility)
- Node detail list with finding links
- Risk factor breakdown
- Risk history timeline
- Related findings sidebar

### Finding Detail Integration (`/findings/[id]`)
- Security Relationships section
- Lists deterministic + AI-suggested relationships
- Links to related findings
- Attack paths containing this finding
- "Run Correlation" action in sidebar

## Security Controls

1. **Workspace Isolation**: All models have `workspace_id` FK, all queries filtered
2. **Authorization**: `require_workspace_member` on all endpoints
3. **AI Boundary**: AI only suggests relationships; deterministic engine builds paths; deterministic engine calculates risk
4. **Human-in-the-loop**: AI suggestions require explicit confirmation
5. **Audit Logging**: All mutations logged (relationship.confirmed, attack_path.created, risk.calculated)
5. **Graph Safety**: Cycle detection, max depth, deduplication
6. **No Exploitation**: Purely analytical - no payload execution, no external scanning

## Data Flow

```
Findings + Evidence
       ↓
Deterministic Correlation Engine
       ↓
FindingRelationships (DETERMINISTIC)
       ↓
AI Relationship Analyzer (optional)
       ↓
FindingRelationships (AI_SUGGESTED → HUMAN_CONFIRMED)
       ↓
AttackPathBuilder (graph construction)
       ↓
AttackPath + Nodes + Edges
       ↓
RiskEngine (deterministic scoring)
       ↓
RiskSnapshot (persisted)
       ↓
Frontend Visualization
```

## Configuration

Environment variables:
- `MAX_ATTACK_PATH_NODES` (default: 8)
- `MAX_ATTACK_PATH_EDGES` (default: 20)
- Risk model weights in `RiskEngine.WEIGHTS` (code, not env)

## Testing

Unit tests cover:
- Correlation: same workspace, cross-workspace rejection, duplicate handling
- Graph: simple path, multi-node, cycle, max depth, empty graph
- Risk Engine: deterministic scores, boundary values (0,19,20,39,40,59,60,79,80,100), correct bands
- AI Correlation: valid suggestion, malformed JSON, invalid type, confidence bounds, prompt injection

## Future Extensibility (Stage 7+)

- Multi-asset attack paths
- Custom relationship types
- Risk model versioning with migration
- Attack path comparison/diff
- Integration with remediation tracking
- Compliance reporting (OWASP, NIST)