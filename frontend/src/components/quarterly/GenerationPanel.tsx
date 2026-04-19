import { useState } from 'react';
import type { QuarterlyReport } from '../../api/quarterlyReports';
import { generateQuarterlyReport, regenerateQuarterlyReport } from '../../api/quarterlyReports';
import { GuidanceInput } from './GuidanceInput';

interface GenerationPanelProps {
  quarter: string;
  existing: QuarterlyReport | null;
  onGenerated: (report: QuarterlyReport) => void;
}

export const GenerationPanel = ({ quarter, existing, onGenerated }: GenerationPanelProps) => {
  const [guidance, setGuidance] = useState(existing?.guidance_text ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isGenerating = existing?.status === 'generating';

  const handleGenerate = async () => {
    setBusy(true);
    setError(null);
    try {
      const report = existing
        ? await regenerateQuarterlyReport(quarter, { guidance_text: guidance || null })
        : await generateQuarterlyReport({ quarter, guidance_text: guidance || null });
      onGenerated(report);
    } catch {
      setError('Generation failed. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{
      background: 'var(--bg)',
      border: '1px solid var(--border-subtle)',
      borderRadius: '10px',
      padding: '1.25rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '1rem',
    }}>
      <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700 }}>
        {existing ? 'Regenerate Report' : 'Generate Quarterly Report'}
      </h3>

      <GuidanceInput value={guidance} onChange={setGuidance} disabled={isGenerating || busy} />

      {error && (
        <div style={{ color: 'var(--error)', fontSize: '0.875rem' }}>{error}</div>
      )}

      {isGenerating && (
        <div style={{ color: 'var(--warning)', background: 'var(--warning-bg)', borderRadius: '6px', padding: '0.625rem', fontSize: '0.875rem' }}>
          Generation in progress — this may take a minute. Refresh to check status.
        </div>
      )}

      <button
        onClick={handleGenerate}
        disabled={busy || isGenerating}
        style={{
          alignSelf: 'flex-start',
          padding: '0.5rem 1.25rem',
          border: 'none',
          borderRadius: '6px',
          background: busy || isGenerating ? 'var(--primary-bg)' : 'var(--primary)',
          color: 'white',
          cursor: busy || isGenerating ? 'not-allowed' : 'pointer',
          fontWeight: 600,
          fontSize: '0.875rem',
        }}
      >
        {busy ? 'Submitting…' : existing ? 'Regenerate' : 'Generate'}
      </button>
    </div>
  );
};
