# PROJECT SOURCE OF TRUTH

## Source Documents Inspected

| Document | Status | Location | Notes |
|----------|--------|----------|-------|
| PRD | NOT FOUND | - | No Product Requirements Document exists |
| SRS | NOT FOUND | - | No Software Requirements Specification exists |
| Architecture Documents | NOT FOUND | - | No existing architecture documentation |
| UI Designs | NOT FOUND | - | No Figma, Sketch, or design system files |
| Project Specifications | NOT FOUND | - | No formal specifications |
| Security Architecture | NOT FOUND | - | No existing security architecture docs |
| Existing Source Code | NOT FOUND | - | Empty repository |
| Assets/Logos | NOT FOUND | - | No branding assets found |
| Documentation | NOT FOUND | - | No README, CONTRIBUTING, or wiki |
| Previous Implementation Notes | NOT FOUND | - | No prior work documented |
| Project Screenshots | NOT FOUND | - | No visual references |
| Configuration Files | NOT FOUND | - | No package.json, pyproject.toml, docker-compose, etc. |

## Source of Truth Hierarchy

Since no existing project artifacts exist, the **Stage 0 task specification itself** serves as the single source of truth for all product definition, architecture, and implementation planning.

### Hierarchy (Highest to Lowest Authority)

1. **Stage 0 Task Specification** (this prompt) — Canonical product definition, architecture constraints, tech stack, security principles, and deliverable requirements
2. **Derived Architecture Documents** (created in Stage 0) — Authoritative once created, must not conflict with #1
3. **Future Implementation Decisions** — Must trace back to #1 and #2

## Conflicts Identified

**None** — No existing documents to conflict with.

## Notes

- This is a greenfield project with zero prior artifacts
- All architecture and design decisions in Stage 0 derive exclusively from the task specification
- Any future implementation must reference these Stage 0 documents as the source of truth