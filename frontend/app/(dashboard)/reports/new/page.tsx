'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { GenerateReportRequest, ReportType, ReportFormat, ReportStatus } from '@/lib/api';
import { useAuthContext } from '@/components/providers/AuthProvider';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select';
import { Checkbox } from '@/components/ui/Checkbox';
import { Textarea } from '@/components/ui/Textarea';
import { DatePicker } from '@/components/ui/DatePicker';
import { AssetMultiSelect } from '@/components/ui/AssetMultiSelect';
import { SeverityMultiSelect } from '@/components/ui/SeverityMultiSelect';
import { useAuth } from '@/hooks/useAuth';
import { Link } from 'next/navigation';
import { format } from 'date-fns';
import {
  ArrowLeft, FileText, Shield, Bug, Zap, RotateCcw, Brain,
  Calendar, Filter, Sparkles
} from 'lucide-react';

const REPORT_TYPES = [
  {
    value: 'executive_summary',
    label: 'Executive Security Summary',
    description: 'Concise overview for executives and stakeholders. Includes overall posture, critical risks, remediation progress, and recommended actions.',
    icon: Shield,
  },
  {
    value: 'technical_vulnerability',
    label: 'Technical Vulnerability Report',
    description: 'Detailed technical findings with evidence, locations, AI analysis, remediation status, and verification outcomes.',
    icon: Bug,
  },
  {
    value: 'remediation_progress',
    label: 'Remediation Progress Report',
    description: 'Track remediation proposals from generation through approval, application, and verification.',
    icon: RotateCcw,
  },
  {
    value: 'verification_regression',
    label: 'Verification & Regression Report',
    description: 'Independent fix verification results, evidence comparisons, regression test outcomes, and human review decisions.',
    icon: Zap,
  },
  {
    value: 'asset_security_posture',
    label: 'Asset Security Posture Report',
    description: 'Per-asset security posture including scan coverage, findings, risk scores, and authorization status.',
    icon: Shield,
  },
];

const REPORT_FORMATS = [
  { value: 'pdf', label: 'PDF', description: 'Professional formatted document for sharing and archival' },
  { value: 'json', label: 'JSON', description: 'Structured data for programmatic consumption and integration' },
];

export default function NewReportPage() {
  const router = useRouter();
  const { currentWorkspace } = useAuthContext();
  const { profile } = useAuth();
  const [selectedType, setSelectedType] = useState<ReportType>('executive_summary');
  const [format, setFormat] = useState<ReportFormat>('pdf');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [periodStart, setPeriodStart] = useState<Date | null>(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000));
  const [periodEnd, setPeriodEnd] = useState<Date | null>(new Date());
  const [includeAiNarrative, setIncludeAiNarrative] = useState(false);
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);
  const [selectedSeverities, setSelectedSeverities] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState(1);

  const handleGenerate = async () => {
    if (!currentWorkspace || !title.trim()) {
      setError('Please enter a report title');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const request: GenerateReportRequest = {
        workspace_id: currentWorkspace.id,
        report_type: selectedType,
        title: title.trim(),
        description: description.trim() || undefined,
        format,
        period_start: periodStart?.toISOString(),
        period_end: periodEnd?.toISOString(),
        included_asset_ids: selectedAssets,
        severity_filters: selectedSeverities,
        filters: {},
        include_ai_narrative: includeAiNarrative,
      };

      const response = await api.generateReport(request);
      router.push(`/reports/${response.report.id}`);
    } catch (err: any) {
      setError(err.message || 'Failed to generate report');
    } finally {
      setLoading(false);
    }
  };

  const typeOption = REPORT_TYPES.find(t => t.value === selectedType);

  if (!currentWorkspace) {
    return (
      <div className="p-6 text-center">
        <Shield className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <p className="text-gray-500">No workspace selected</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Generate Security Report</h1>
          <p className="text-gray-500">Create a professional security report for your workspace</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Step 1: Report Type Selection */}
      <Card>
        <CardHeader>
          <CardTitle>Step 1: Choose Report Type</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {REPORT_TYPES.map(type => (
              <Button
                key={type.value}
                variant={selectedType === type.value ? 'default' : 'outline'}
                className="h-32 w-full flex-col items-start justify-between p-4 text-left"
                onClick={() => setSelectedType(type.value)}
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-accent-glow">
                    <type.icon className="h-6 w-6 text-accent-DEFAULT" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">{type.label}</p>
                    <p className="text-xs text-gray-500">{type.description}</p>
                  </div>
                </div>
                {selectedType === type.value && (
                  <div className="flex items-center gap-2 text-sm text-accent-DEFAULT">
                    <Sparkles className="h-4 w-4" />
                    Selected
                  </div>
                )}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Step 2: Report Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>Step 2: Configure Report</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="title">Report Title *</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., Q4 2024 Executive Security Summary"
                required
              />
            </div>
            <div>
              <Label htmlFor="format">Format</Label>
              <Select value={format} onValueChange={(v) => setFormat(v as ReportFormat)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {REPORT_FORMATS.map(f => (
                    <SelectItem key={f.value} value={f.value}>
                      <div className="flex flex-col">
                        <span className="font-medium">{f.label}</span>
                        <span className="text-xs text-gray-500">{f.description}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div>
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description of the report scope and purpose"
              rows={3}
            />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label htmlFor="periodStart">Period Start</Label>
              <DatePicker
                id="periodStart"
                selected={periodStart}
                onChange={setPeriodStart}
                selectsStart
                startDate={periodStart}
                endDate={periodEnd}
              />
            </div>
            <div>
              <Label htmlFor="periodEnd">Period End</Label>
              <DatePicker
                id="periodEnd"
                selected={periodEnd}
                onChange={setPeriodEnd}
                selectsEnd
                startDate={periodStart}
                endDate={periodEnd}
              />
            </div>
          </div>

          <div>
            <Label>Asset Filter (Optional)</Label>
            <p className="text-sm text-gray-500 mb-2">Select specific assets to include. Leave empty to include all workspace assets.</p>
            <AssetMultiSelect
              workspaceId={currentWorkspace.id}
              selected={selectedAssets}
              onChange={setSelectedAssets}
              placeholder="Search and select assets..."
            />
          </div>

          <div>
            <Label>Severity Filter (Optional)</Label>
            <p className="text-sm text-gray-500 mb-2">Filter findings by severity. Leave empty to include all severities.</p>
            <SeverityMultiSelect
              selected={selectedSeverities}
              onChange={setSelectedSeverities}
            />
          </div>

          <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg">
            <Checkbox
              id="aiNarrative"
              checked={includeAiNarrative}
              onChange={(e) => setIncludeAiNarrative(e.target.checked)}
            />
            <div>
              <Label htmlFor="aiNarrative" className="font-medium text-gray-900">
                Include AI-Generated Executive Narrative
                <Sparkles className="h-4 w-4 inline ml-1 text-accent-DEFAULT" />
              </Label>
              <p className="text-sm text-gray-500">
                Uses AI to generate a natural language summary of key findings and recommendations.
                <span className="text-accent-DEFAULT font-medium"> Advisory only — does not modify metrics or findings.</span>
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Preview Summary */}
      <Card className="border-accent-DEFAULT/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Report Preview
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">Type</span>
              <span className="font-medium">{typeOption?.label || selectedType}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Format</span>
              <span className="font-medium">{format.toUpperCase()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Period</span>
              <span className="font-medium">
                {periodStart ? format(periodStart, 'MMM d, yyyy') : 'Not set'} -
                {periodEnd ? format(periodEnd, 'MMM d, yyyy') : 'Not set'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Assets</span>
              <span className="font-medium">{selectedAssets.length > 0 ? `${selectedAssets.length} selected` : 'All workspace assets'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Severities</span>
              <span className="font-medium">{selectedSeverities.length > 0 ? selectedSeverities.join(', ') : 'All severities'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">AI Narrative</span>
              <span className="font-medium">{includeAiNarrative ? 'Included (advisory)' : 'Not included'}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Generate Button */}
      <div className="flex justify-end gap-3 pt-4 border-t">
        <Button variant="secondary" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Cancel
        </Button>
        <Button
          onClick={handleGenerate}
          disabled={loading || !title.trim()}
          className="px-6"
        >
          {loading ? (
            <>
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Generating...
            </>
          ) : (
            'Generate Report'
          )}
        </Button>
      </div>
    </div>
  );
}