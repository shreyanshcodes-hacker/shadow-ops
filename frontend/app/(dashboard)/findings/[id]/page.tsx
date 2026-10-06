'use client';

import { useState } from 'react';
import {
  Zap, Clock, AlertTriangle, CheckCircle, XCircle, Loader2,
  ChevronRight, ChevronDown, FileText, Code, AlertCircle,
  BarChart2, Download, RefreshCw, X, Brain, Bot, Shield, Sparkles,
  Info, AlertCircle as AlertCircleIcon, Flag, Target, Search,
  MessageSquare, GitBranch, Copy, ExternalLink, Eye, EyeOff
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Dropdown, DropdownItem, DropdownTrigger, DropdownContent, DropdownSeparator } from '@/components/ui/Dropdown';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs';
import { Progress } from '@/components/ui/Progress';
import { useWorkspace } from '@/hooks/useWorkspace';
import { useParams, useRouter } from 'next/navigation';
import { api, type Scan, type ScanEvent, type ScanSummary, type Finding, type FindingAiAnalysis, type AiRun, type AiAnalysisStatus, type SupportingEvidenceRef, type FindingRelationship, type AttackPath } from '@/lib/api';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { clsx } from 'clsx';
import Link from 'next/link';

const SEVERITY_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.ComponentType<{ className?: string }> }> = {
  critical: { label: 'Critical', color: 'text-status-error', bg: 'bg-status-error/10', icon: AlertTriangle },
  high: { label: 'High', color: 'text-status-error', bg: 'bg-status-error/10', icon: AlertTriangle },
  medium: { label: 'Medium', color: 'text-status-warning', bg: 'bg-status-warning/10', icon: AlertCircle },
  low: { label: 'Low', color: 'text-status-info', bg: 'bg-status-info/10', icon: Info },
  info: { label: 'Info', color: 'text-foreground-muted', bg: 'bg-background-tertiary', icon: Info },
};

const VULNERABILITY_TYPE_LABELS: Record<string, string> = {
  injection: 'Injection',
  authentication: 'Authentication',
  authorization: 'Authorization',
  cryptography: 'Cryptography',
  data_exposure: 'Data Exposure',
  configuration: 'Configuration',
  dependency: 'Dependency',
  denial_of_service: 'DoS',
  business_logic: 'Business Logic',
  unknown: 'Unknown',
};

const EXPLOITABILITY_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  high: { label: 'High', color: 'text-status-error', bg: 'bg-status-error/10' },
  medium: { label: 'Medium', color: 'text-status-warning', bg: 'bg-status-warning/10' },
  low: { label: 'Low', color: 'text-status-success', bg: 'bg-status-success/10' },
  unknown: { label: 'Unknown', color: 'text-foreground-muted', bg: 'bg-background-tertiary' },
};

const CERTAINTY_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.ComponentType<{ className?: string }> }> = {
  observed: { label: 'Observed', color: 'text-status-success', bg: 'bg-status-success/10', icon: CheckCircle },
  inferred: { label: 'Inferred', color: 'text-status-warning', bg: 'bg-status-warning/10', icon: AlertTriangle },
  uncertain: { label: 'Uncertain', color: 'text-foreground-muted', bg: 'bg-background-tertiary', icon: AlertCircleIcon },
};

const RELATIONSHIP_TYPE_LABELS: Record<string, string> = {
  depends_on: 'Depends On',
  enables: 'Enables',
  exposes: 'Exposes',
  leads_to: 'Leads To',
  shares_component: 'Shares Component',
  shares_entry_point: 'Shares Entry Point',
  shares_data_flow: 'Shares Data Flow',
  amplifies: 'Amplifies',
};

const SOURCE_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  deterministic: { label: 'Deterministic', color: 'text-status-success', bg: 'bg-status-success/10' },
  ai_suggested: { label: 'AI Suggested', color: 'text-accent-DEFAULT', bg: 'bg-accent-DEFAULT/10' },
  human_confirmed: { label: 'Human Confirmed', color: 'text-status-info', bg: 'bg-status-info/10' },
};

const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low', 'info'];

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString();
}

function ConfidenceBar({ confidence }: { confidence: number }) {
  const percentage = Math.round(confidence * 100);
  let color = 'bg-status-error';
  if (percentage >= 80) color = 'bg-status-success';
  else if (percentage >= 60) color = 'bg-status-warning';
  else if (percentage >= 40) color = 'bg-status-info';

  return (
    <div className="w-full max-w-xs">
      <div className="flex justify-between text-xs mb-1">
        <span className="text-foreground-muted">Confidence</span>
        <span className="font-mono font-medium">{percentage}%</span>
      </div>
      <div className="h-2 bg-background-tertiary rounded-full overflow-hidden">
        <div className={`${color} h-full rounded-full transition-all`} style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}

function CertaintyBadge({ certainty }: { certainty: string }) {
  const config = CERTAINTY_CONFIG[certainty] || CERTAINTY_CONFIG.uncertain;
  const Icon = config.icon;
  return (
    <Badge variant="outline" className={clsx('gap-1', config.color)}>
      <Icon className="h-2.5 w-2.5" />
      {config.label}
    </Badge>
  );
}

function VulnerabilityTypeBadge({ type }: { type: string }) {
  return (
    <Badge variant="outline" className="text-accent-DEFAULT border-accent-DEFAULT/30">
      <Target className="h-3 w-3 mr-1" />
      {VULNERABILITY_TYPE_LABELS[type] || type}
    </Badge>
  );
}

function EvidenceReferences({ references, evidenceMap }: { references: SupportingEvidenceRef[]; evidenceMap: Map<string, any> }) {
  if (!references || references.length === 0) {
    return <p className="text-sm text-foreground-muted">No evidence references</p>;
  }

  return (
    <div className="space-y-2">
      {references.map((ref, idx) => {
        const evidence = evidenceMap.get(ref.evidence_id);
        return (
          <div key={idx} className="p-3 rounded-lg border border-border-DEFAULT bg-background-tertiary/30">
            <div className="flex items-start gap-3">
              <CertaintyBadge certainty={ref.certainty} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground-DEFAULT">{ref.reason}</p>
                {evidence && (
                  <div className="mt-1 flex items-center gap-2 text-xs text-foreground-muted">
                    <span className="font-mono">{evidence.evidence_type}</span>
                    {evidence.file_path && (
                      <>
                        <span>•</span>
                        <span className="font-mono truncate max-w-xs">{evidence.file_path}</span>
                        {evidence.line_start && (
                          <>
                            <span>:</span>
                            <span className="font-mono">{evidence.line_start}</span>
                            {evidence.line_end && evidence.line_end !== evidence.line_start && (
                              <>
                                <span>–</span>
                                <span className="font-mono">{evidence.line_end}</span>
                              </>
                            )}
                          </>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AiAnalysisPanel({ analysis, evidenceList }: { analysis: FindingAiAnalysis; evidenceList: any[] }) {
  const evidenceMap = new Map(evidenceList.map(e => [e.id, e]));

  return (
    <Card className="border-accent-DEFAULT/30 bg-accent-DEFAULT/5">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-accent-DEFAULT" />
            AI Security Analysis
          </CardTitle>
          <Badge variant="outline" className="text-accent-DEFAULT border-accent-DEFAULT/30">
            <Bot className="h-3 w-3 mr-1" />
            Advisory Only
          </Badge>
        </div>
        <CardDescription>
          This analysis is AI-generated and should be reviewed by a human security professional.
          Scanner facts (file, line, rule) are authoritative and not modified by AI.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Summary & Meta */}
        <div className="grid gap-4 md:grid-cols-3">
          <div className="p-4 rounded-lg border border-border-DEFAULT bg-background-secondary/50">
            <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide mb-1">Summary</p>
            <p className="text-foreground-DEFAULT">{analysis.summary}</p>
          </div>
          <div className="p-4 rounded-lg border border-border-DEFAULT bg-background-secondary/50">
            <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide mb-1">Vulnerability Type</p>
            <VulnerabilityTypeBadge type={analysis.vulnerability_type} />
          </div>
          <div className="p-4 rounded-lg border border-border-DEFAULT bg-background-secondary/50">
            <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide mb-1">AI Severity Assessment</p>
            <Badge variant="outline" className={clsx(EXPLOITABILITY_CONFIG[analysis.severity_assessment]?.color || 'text-foreground-muted')}>
              {analysis.severity_assessment.toUpperCase()}
            </Badge>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <ConfidenceBar confidence={analysis.confidence} />
          <div className="p-4 rounded-lg border border-border-DEFAULT bg-background-secondary/50">
            <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide mb-1">Exploitability</p>
            <Badge variant="outline" className={clsx(EXPLOITABILITY_CONFIG[analysis.exploitability_assessment]?.color || 'text-foreground-muted', EXPLOITABILITY_CONFIG[analysis.exploitability_assessment]?.bg || 'bg-background-tertiary')}>
              {EXPLOITABILITY_CONFIG[analysis.exploitability_assessment]?.label || analysis.exploitability_assessment}
            </Badge>
          </div>
          <div className="p-4 rounded-lg border border-border-DEFAULT bg-background-secondary/50">
            <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide mb-1">Affected Component</p>
            <p className="font-mono text-sm text-foreground-DEFAULT truncate">{analysis.affected_component}</p>
          </div>
        </div>

        {/* Evidence Interpretation */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-foreground-DEFAULT flex items-center gap-2">
            <Search className="h-4 w-4" />
            Evidence Interpretation
          </h4>
          <div className="p-4 rounded-lg border border-border-DEFAULT bg-background-secondary/30">
            <p className="text-sm text-foreground-muted whitespace-pre-wrap">{analysis.evidence_interpretation}</p>
          </div>
        </div>

        {/* Reasoning */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-foreground-DEFAULT flex items-center gap-2">
            <MessageSquare className="h-4 w-4" />
            Reasoning
          </h4>
          <div className="p-4 rounded-lg border border-border-DEFAULT bg-background-secondary/30">
            <p className="text-sm text-foreground-muted whitespace-pre-wrap">{analysis.reasoning}</p>
          </div>
        </div>

        {/* Impact Assessment */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-foreground-DEFAULT flex items-center gap-2">
            <Flag className="h-4 w-4" />
            Impact Assessment
          </h4>
          <div className="p-4 rounded-lg border border-border-DEFAULT bg-background-secondary/30">
            <p className="text-sm text-foreground-muted whitespace-pre-wrap">{analysis.impact_assessment}</p>
          </div>
        </div>

        {/* Attack Preconditions */}
        {analysis.attack_preconditions && (
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-foreground-DEFAULT flex items-center gap-2">
              <GitBranch className="h-4 w-4" />
              Attack Preconditions
            </h4>
            <div className="p-4 rounded-lg border border-border-DEFAULT bg-background-secondary/30">
              <p className="text-sm text-foreground-muted whitespace-pre-wrap">{analysis.attack_preconditions}</p>
            </div>
          </div>
        )}

        {/* Recommended Next Steps */}
        {analysis.recommended_next_steps && analysis.recommended_next_steps.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-foreground-DEFAULT flex items-center gap-2">
              <Target className="h-4 w-4" />
              Recommended Next Steps
            </h4>
            <div className="space-y-2">
              {analysis.recommended_next_steps.map((step, idx) => (
                <div key={idx} className="flex items-start gap-3 p-3 rounded-lg border border-border-DEFAULT bg-background-secondary/30">
                  <span className="flex-shrink-0 w-6 h-6 rounded-full border border-border-DEFAULT flex items-center justify-center text-xs font-mono text-foreground-muted">
                    {idx + 1}
                  </span>
                  <p className="text-sm text-foreground-DEFAULT">{step}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Uncertainty */}
        {analysis.uncertainty && (
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-foreground-DEFAULT flex items-center gap-2">
              <AlertCircleIcon className="h-4 w-4 text-status-warning" />
              Uncertainty & Gaps
            </h4>
            <div className="p-4 rounded-lg border border-status-warning/30 bg-status-warning/5">
              <p className="text-sm text-foreground-muted whitespace-pre-wrap">{analysis.uncertainty}</p>
            </div>
          </div>
        )}

        {/* Supporting Evidence */}
        {analysis.supporting_evidence && analysis.supporting_evidence.length > 0 && (
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-foreground-DEFAULT flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Supporting Evidence References
            </h4>
            <EvidenceReferences references={analysis.supporting_evidence} evidenceMap={evidenceMap} />
          </div>
        )}

        {/* Provider Metadata */}
        <div className="pt-4 border-t border-border-DEFAULT">
          <div className="flex flex-wrap gap-4 text-xs text-foreground-muted">
            <span className="flex items-center gap-1">
              <Bot className="h-3 w-3" />
              Provider: <span className="font-mono capitalize">{analysis.provider}</span>
            </span>
            <span className="flex items-center gap-1">
              <Code className="h-3 w-3" />
              Model: <span className="font-mono">{analysis.model}</span>
            </span>
            <span className="flex items-center gap-1">
              <GitBranch className="h-3 w-3" />
              Prompt: <span className="font-mono">{analysis.prompt_version}</span>
            </span>
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Generated: <span className="font-mono">{formatDate(analysis.created_at)}</span>
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function FindingDetailHeader({ finding }: { finding: Finding }) {
  const config = SEVERITY_CONFIG[finding.severity] || SEVERITY_CONFIG.info;
  const SeverityIcon = config.icon;

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link href="/scans" className="p-2 rounded-lg hover:bg-background-tertiary transition-colors">
            <ChevronRight className="h-5 w-5 rotate-180 text-foreground-muted" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-foreground-DEFAULT flex items-center gap-2">
              <Zap className="h-6 w-6 text-accent-DEFAULT" />
              Finding Details
            </h1>
            <p className="text-sm text-foreground-muted font-mono mt-1">{finding.id}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="outline" className={clsx('text-lg', config.color)}>
            <SeverityIcon className="h-4 w-4 mr-1" />
            {config.label}
          </Badge>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <Badge variant="outline" className="text-accent-DEFAULT border-accent-DEFAULT/30">
          <Code className="h-3 w-3 mr-1" />
          Source: {finding.source}
        </Badge>
        {finding.source_rule_id && (
          <Badge variant="outline">
            <FileText className="h-3 w-3 mr-1" />
            Rule: {finding.source_rule_id}
          </Badge>
        )}
        {finding.cwe_ids.length > 0 && (
          <Badge variant="outline">
            <AlertCircle className="h-3 w-3 mr-1" />
            CWE: {finding.cwe_ids.join(', ')}
          </Badge>
        )}
        {finding.owasp_categories.length > 0 && (
          <Badge variant="outline">
            <Shield className="h-3 w-3 mr-1" />
            OWASP: {finding.owasp_categories.join(', ')}
          </Badge>
        )}
      </div>
    </div>
  );
}

function FindingEvidenceSection({ evidenceList }: { evidenceList: any[] }) {
  if (!evidenceList || evidenceList.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <EmptyState icon="FileText" title="No Evidence" description="No structured evidence available for this finding." />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Evidence ({evidenceList.length})
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {evidenceList.map((evidence, idx) => (
            <div key={idx} className="p-4 rounded-lg border border-border-DEFAULT hover:bg-background-tertiary/50 transition-colors">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-medium text-foreground-DEFAULT">{evidence.title}</h4>
                    <Badge variant="outline" className="text-xs">{evidence.evidence_type}</Badge>
                  </div>
                  {evidence.description && (
                    <p className="text-sm text-foreground-muted mb-2">{evidence.description}</p>
                  )}
                  <div className="flex flex-wrap gap-3 text-xs text-foreground-muted">
                    {evidence.file_path && (
                      <span className="flex items-center gap-1">
                        <FileText className="h-3 w-3" />
                        <span className="font-mono truncate max-w-xs">{evidence.file_path}</span>
                        {evidence.line_start && (
                          <>
                            <span>:</span>
                            <span className="font-mono">{evidence.line_start}</span>
                            {evidence.line_end && evidence.line_end !== evidence.line_start && (
                              <>
                                <span>–</span>
                                <span className="font-mono">{evidence.line_end}</span>
                              </>
                            )}
                          </>
                        )}
                      </span>
                    )}
                    {evidence.content && Object.keys(evidence.content).length > 0 && (
                      <Button variant="ghost" size="sm" className="text-xs px-2 py-1">
                        <Eye className="h-3 w-3 mr-1" />
                        View Content
                      </Button>
                    )}
                  </div>
                </div>
              </div>
              {evidence.content && Object.keys(evidence.content).length > 0 && (
                <div className="mt-3 p-3 rounded bg-background-tertiary/50 border border-border-DEFAULT">
                  <pre className="text-xs font-mono text-foreground-muted overflow-x-auto max-h-60">
                    {JSON.stringify(evidence.content, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function ScannerFactsSection({ finding }: { finding: Finding }) {
  return (
    <Card className="border-l-4 border-accent-DEFAULT">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-accent-DEFAULT" />
          Scanner Facts (Authoritative)
        </CardTitle>
        <CardDescription>
          These facts come directly from the scanner and are not modified by AI analysis.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <dt className="text-xs font-medium text-foreground-muted uppercase tracking-wide">Scanner</dt>
              <dd className="font-mono text-sm text-foreground-DEFAULT mt-1 capitalize">{finding.source}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-foreground-muted uppercase tracking-wide">Rule ID</dt>
              <dd className="font-mono text-sm text-foreground-DEFAULT mt-1">{finding.source_rule_id || 'N/A'}</dd>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <dt className="text-xs font-medium text-foreground-muted uppercase tracking-wide">File</dt>
              <dd className="font-mono text-sm text-foreground-DEFAULT mt-1 truncate">{finding.location?.file || 'N/A'}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-foreground-muted uppercase tracking-wide">Line Range</dt>
              <dd className="font-mono text-sm text-foreground-DEFAULT mt-1">
                {finding.location?.line_start ? `${finding.location.line_start}${finding.location.line_end && finding.location.line_end !== finding.location.line_start ? `–${finding.location.line_end}` : ''}` : 'N/A'}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-foreground-muted uppercase tracking-wide">Scanner Severity</dt>
              <dd className="font-mono text-sm text-foreground-DEFAULT mt-1 capitalize">{finding.severity}</dd>
            </div>
          </div>
          {finding.code_snippet && (
            <div>
              <dt className="text-xs font-medium text-foreground-muted uppercase tracking-wide">Code Snippet</dt>
              <dd className="mt-2">
                <div className="p-4 rounded bg-background-tertiary/50 border border-border-DEFAULT overflow-x-auto">
                  <pre className="text-xs font-mono text-foreground-DEFAULT"><code>{finding.code_snippet}</code></pre>
                </div>
              </dd>
            </div>
          )}
          {finding.remediation_guidance && (
            <div>
              <dt className="text-xs font-medium text-foreground-muted uppercase tracking-wide">Scanner Remediation Guidance</dt>
              <dd className="mt-2 p-4 rounded bg-status-success/5 border border-status-success/30 text-sm text-status-success">
                {finding.remediation_guidance}
              </dd>
            </div>
          )}
        </dl>
      </CardContent>
    </Card>
  );
}

function AiAnalysisSection({
  finding,
  aiAnalysis,
  evidenceList,
  analyzeMutation,
  isAnalyzing,
  analysisFailed,
  onReanalyze
}: {
  finding: Finding;
  aiAnalysis: FindingAiAnalysis | null;
  evidenceList: any[];
  analyzeMutation: ReturnType<typeof useMutation>;
  isAnalyzing: boolean;
  analysisFailed: boolean;
  onReanalyze: () => void;
}) {
  const [showAnalysis, setShowAnalysis] = useState(false);

  const hasAnalysis = !!aiAnalysis;

  return (
    <Card className={hasAnalysis ? 'border-accent-DEFAULT/30' : ''}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-accent-DEFAULT" />
          AI Security Analysis
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Status */}
        <div className="flex flex-wrap items-center gap-3">
          {analysisFailed && (
            <Badge variant="outline" className="text-status-error">
              <AlertTriangle className="h-3 w-3 mr-1" />
              AI Analysis Failed
            </Badge>
          )}
          {hasAnalysis && !isAnalyzing && (
            <Badge variant="outline" className="text-status-success">
              <CheckCircle className="h-3 w-3 mr-1" />
              Analysis Available
            </Badge>
          )}
          {isAnalyzing && (
            <Badge variant="outline" className="text-status-warning animate-pulse">
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              Analyzing...
            </Badge>
          )}
          {!hasAnalysis && !isAnalyzing && !analysisFailed && (
            <Badge variant="outline" className="text-foreground-muted">
              <Bot className="h-3 w-3 mr-1" />
              Not Analyzed
            </Badge>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-3">
          {!hasAnalysis && !isAnalyzing && (
            <Button
              onClick={() => analyzeMutation.mutate(finding.id)}
              disabled={analyzeMutation.isPending}
              className="gap-2"
            >
              <Brain className="h-4 w-4" />
              <Sparkles className="h-4 w-4" />
              Analyze with AI
            </Button>
          )}
          {hasAnalysis && (
            <Button
              variant="outline"
              onClick={() => setShowAnalysis(!showAnalysis)}
              className="gap-2"
            >
              <Eye className={clsx('h-4 w-4', showAnalysis ? 'hidden' : '')} />
              <EyeOff className={clsx('h-4 w-4', !showAnalysis ? 'hidden' : '')} />
              {showAnalysis ? 'Hide AI Analysis' : 'Show AI Analysis'}
            </Button>
          )}
          {hasAnalysis && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onReanalyze}
              className="gap-1"
            >
              <RefreshCw className="h-3 w-3" />
              Re-analyze
            </Button>
          )}
        </div>

        {/* Analysis Content */}
        {showAnalysis && hasAnalysis && (
          <AiAnalysisPanel analysis={aiAnalysis} evidenceList={evidenceList} />
        )}
      </CardContent>
    </Card>
  );
}

export default function FindingDetailPage() {
  const { workspaceId } = useWorkspace();
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const findingId = params.id as string;

  const { data: finding, isLoading: findingLoading, error: findingError } = useQuery({
    queryKey: ['finding', findingId],
    queryFn: () => api.getFinding(workspaceId!, findingId),
    enabled: !!workspaceId && !!findingId,
    staleTime: 30 * 1000,
  });

  const { data: evidenceList, isLoading: evidenceLoading } = useQuery({
    queryKey: ['finding-evidence', findingId],
    queryFn: () => api.listFindingEvidence(findingId),
    enabled: !!findingId,
    staleTime: 30 * 1000,
  });

  const { data: aiAnalysis, isLoading: aiAnalysisLoading } = useQuery({
    queryKey: ['ai-analysis', findingId],
    queryFn: () => api.getFindingAiAnalysis(findingId),
    enabled: !!findingId,
    staleTime: 30 * 1000,
    retry: false,
  });

  const { data: aiAnalyses } = useQuery({
    queryKey: ['ai-analyses', findingId],
    queryFn: () => api.getFindingAiAnalyses(findingId),
    enabled: !!findingId,
    staleTime: 30 * 1000,
  });

  const { data: relationships } = useQuery({
    queryKey: ['finding-relationships', findingId],
    queryFn: () => api.listFindingRelationships(findingId),
    enabled: !!findingId,
    staleTime: 30 * 1000,
  });

  const { data: findingAttackPaths } = useQuery({
    queryKey: ['finding-attack-paths', findingId],
    queryFn: () => api.getFindingAttackPaths(findingId),
    enabled: !!findingId,
    staleTime: 30 * 1000,
  });

  const analyzeMutation = useMutation({
    mutationFn: (findingId: string) => api.startFindingAnalysisDirect(findingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-analysis', findingId] });
      queryClient.invalidateQueries({ queryKey: ['ai-analyses', findingId] });
    },
  });

  const reanalyzeMutation = useMutation({
    mutationFn: (findingId: string) => api.startFindingAnalysisDirect(findingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-analysis', findingId] });
      queryClient.invalidateQueries({ queryKey: ['ai-analyses', findingId] });
    },
  });

  const isAnalyzing = analyzeMutation.isPending || reanalyzeMutation.isPending;
  const analysisFailed = aiAnalysisLoading && !aiAnalysis;

  if (findingLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <Card><CardContent><Skeleton className="h-8 w-1/4" /></CardContent></Card>
        <Card><CardContent><Skeleton className="h-40 w-full" /></CardContent></Card>
      </div>
    );
  }

  if (findingError || !finding) {
    return (
      <div className="space-y-6">
        <EmptyState
          icon="AlertTriangle"
          title="Finding Not Found"
          description="The finding you're looking for doesn't exist or you don't have access to it."
          action={<Button onClick={() => router.push('/scans')}>Back to Scans</Button>}
        />
      </div>
    );
  }

  const onReanalyze = () => {
    reanalyzeMutation.mutate(findingId);
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <FindingDetailHeader finding={finding} />

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Scanner Facts */}
          <ScannerFactsSection finding={finding} />

          {/* AI Analysis */}
          <AiAnalysisSection
            finding={finding}
            aiAnalysis={aiAnalysis}
            evidenceList={evidenceList || []}
            analyzeMutation={analyzeMutation}
            isAnalyzing={isAnalyzing}
            analysisFailed={analysisFailed}
            onReanalyze={onReanalyze}
          />

          {/* Security Relationships */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GitBranch className="h-5 w-5 text-accent-DEFAULT" />
                Security Relationships
              </CardTitle>
              <CardDescription>
                Relationships to other findings (deterministic, AI-suggested, or human-confirmed).
              </CardDescription>
            </CardHeader>
            <CardContent>
              {(relationships && relationships.length > 0) || (findingAttackPaths && findingAttackPaths.length > 0) ? (
                <div className="space-y-4">
                  {relationships && relationships.length > 0 && (
                    <div className="space-y-3">
                      <h4 className="text-sm font-medium text-foreground-DEFAULT">Related Findings ({relationships.length})</h4>
                      <div className="space-y-2">
                        {relationships.map((rel, idx) => {
                          const isSource = rel.source_finding_id === finding.id;
                          const otherFinding = isSource ? rel.target_finding : rel.source_finding;
                          const direction = isSource ? '→' : '←';
                          const typeLabel = RELATIONSHIP_TYPE_LABELS[rel.relationship_type] || rel.relationship_type;
                          const sourceConfig = SOURCE_CONFIG[rel.source] || SOURCE_CONFIG.deterministic;
                          
                          return (
                            <Link key={idx} href={`/findings/${otherFinding?.id}`} className="flex items-center gap-3 p-3 rounded-lg border border-border-DEFAULT hover:bg-background-tertiary/50 transition-colors">
                              <div className={clsx('flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center', sourceConfig.bg)}>
                                <span className={clsx('text-xs font-mono', sourceConfig.color)}>{direction}</span>
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <span className="font-medium text-foreground-DEFAULT truncate">{otherFinding?.title || 'Unknown Finding'}</span>
                                  <Badge variant="outline" className="text-xs">{typeLabel}</Badge>
                                  <Badge variant="outline" className={clsx('text-xs', sourceConfig.color, sourceConfig.bg)}>
                                    {sourceConfig.label}
                                  </Badge>
                                </div>
                                <p className="text-xs text-foreground-muted truncate">{rel.rationale}</p>
                              </div>
                              <ConfidenceBar confidence={rel.confidence} />
                            </Link>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {findingAttackPaths && findingAttackPaths.length > 0 && (
                    <div className="space-y-3 pt-4 border-t border-border-DEFAULT">
                      <h4 className="text-sm font-medium text-foreground-DEFAULT">Attack Paths ({findingAttackPaths.length})</h4>
                      <div className="space-y-2">
                        {findingAttackPaths.map((path, idx) => {
                          const riskConfig = RISK_BAND_CONFIG[path.risk_band || 'informational'];
                          return (
                            <Link key={idx} href={`/attack-paths/${path.id}`} className="flex items-center gap-3 p-3 rounded-lg border border-border-DEFAULT hover:bg-background-tertiary/50 transition-colors">
                              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-accent-DEFAULT/10 flex items-center justify-center">
                                <GitBranch className="h-5 w-5 text-accent-DEFAULT" />
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="font-medium text-foreground-DEFAULT truncate">{path.title}</p>
                                <div className="flex items-center gap-2 text-xs text-foreground-muted mt-1">
                                  <Badge variant="outline" className={clsx(riskConfig.color, riskConfig.bg)}>
                                    {riskConfig.label}
                                  </Badge>
                                  <span>{path.node_count} nodes</span>
                                  {path.risk_score !== null && <span>Score: {path.risk_score}</span>}
                                </div>
                              </div>
                            </Link>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-8">
                  <GitBranch className="h-10 w-10 mx-auto mb-2 text-foreground-muted/50" />
                  <p className="text-foreground-muted">No relationships or attack paths found</p>
                  <p className="text-sm text-foreground-muted mt-1">Run correlation to discover relationships</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Evidence */}
          <FindingEvidenceSection evidenceList={evidenceList || []} />
        </div>

        {/* Sidebar - Metadata & History */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Info className="h-5 w-5" />
                Finding Info
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-foreground-muted">Status</dt>
                  <dd className="font-medium text-foreground-DEFAULT capitalize">{finding.status.replace('_', ' ')}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-foreground-muted">Confidence</dt>
                  <dd className="font-medium text-foreground-DEFAULT capitalize">{finding.confidence}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-foreground-muted">Risk Score</dt>
                  <dd className="font-medium text-foreground-DEFAULT">{finding.risk_score?.toFixed(1) || 'N/A'}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-foreground-muted">First Seen</dt>
                  <dd className="font-medium text-foreground-DEFAULT font-mono text-xs">{formatDate(finding.first_seen_at)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-foreground-muted">Last Seen</dt>
                  <dd className="font-medium text-foreground-DEFAULT font-mono text-xs">{formatDate(finding.last_seen_at)}</dd>
                </div>
                {finding.fixed_at && (
                  <div className="flex justify-between">
                    <dt className="text-foreground-muted">Fixed At</dt>
                    <dd className="font-medium text-status-success font-mono text-xs">{formatDate(finding.fixed_at)}</dd>
                  </div>
                )}
              </dl>

              <div className="pt-4 border-t border-border-DEFAULT">
                <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide mb-2">Scan Context</p>
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-foreground-muted">Scan ID</dt>
                    <dd className="font-mono text-xs truncate max-w-[150px]">{finding.scan_id}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-foreground-muted">Asset ID</dt>
                    <dd className="font-mono text-xs truncate max-w-[150px]">{finding.asset_id}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-foreground-muted">Workspace</dt>
                    <dd className="font-mono text-xs truncate max-w-[150px]">{finding.workspace_id}</dd>
                  </div>
                </dl>
              </div>
            </CardContent>
          </Card>

          {/* Correlation Actions */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5 text-accent-DEFAULT" />
                Correlation Actions
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button
                variant="outline"
                className="w-full gap-2"
                onClick={() => api.correlateFinding(findingId)}
              >
                <GitBranch className="h-4 w-4" />
                Run Deterministic Correlation
              </Button>
              <p className="text-xs text-foreground-muted text-center">
                Finds relationships based on shared files, components, CWE/OWASP categories
              </p>
            </CardContent          </Card>

          {/* AI Analysis History */}
          {aiAnalyses && aiAnalyses.length > 1 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <GitBranch className="h-5 w-5" />
                  Analysis History ({aiAnalyses.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {aiAnalyses.map((analysis, idx) => (
                    <div key={analysis.id} className="p-3 rounded-lg border border-border-DEFAULT hover:bg-background-tertiary/50 transition-colors">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-xs">
                            {idx === 0 ? 'Latest' : `v${aiAnalyses.length - idx}`}
                          </Badge>
                          <span className="text-xs text-foreground-muted font-mono">
                            {analysis.provider} / {analysis.model}
                          </span>
                        </div>
                        <ConfidenceBar confidence={analysis.confidence} />
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <Badge variant="outline" className="text-xs">{analysis.vulnerability_type}</Badge>
                        <Badge variant="outline" className="text-xs">{analysis.severity_assessment}</Badge>
                      </div>
                      <p className="mt-1 text-xs text-foreground-muted">{formatDate(analysis.created_at)}</p>
                    </div>
                  ))}
                </div>
              </CardContent            </Card>
          )}
        </div>
      </div>
    </div>
  );
}