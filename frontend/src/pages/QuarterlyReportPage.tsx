import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import type { QuarterlyReport } from '../api/quarterlyReports';
import {
  getQuarterlyReport,
  updateQuarterlyReport,
  finalizeQuarterlyReport,
} from '../api/quarterlyReports';
import { QuarterSelector } from '../components/quarterly/QuarterSelector';
import { currentQuarter } from '../components/quarterly/quarterUtils';
import { ReportStatusBadge } from '../components/quarterly/ReportStatusBadge';
import { ReportSection } from '../components/quarterly/ReportSection';
import { GenerationPanel } from '../components/quarterly/GenerationPanel';

const SECTION_TITLES: Record<string, string> = {
  qualitative: 'Qualitative Assessment',
  quantitative: 'Quantitative Summary',
  highlights: 'Highlights',
  overall: 'Overall Reflection',
};

export const QuarterlyReportPage = () => {
  const { quarter: paramQuarter } = useParams<{ quarter?: string }>();
  const navigate = useNavigate();
  const [quarter, setQuarter] = useState(paramQuarter || currentQuarter());
  const [report, setReport] = useState<QuarterlyReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [finalizing, setFinalizing] = useState(false);

  const fetchReport = useCallback(async (q: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getQuarterlyReport(q);
      setReport(data);
    } catch (e: unknown) {
      if (e && typeof e === 'object' && 'response' in e && (e as { response?: { status?: number } }).response?.status === 404) {
        setReport(null);
      } else {
        setError('Failed to load report.');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReport(quarter);
    if (quarter !== paramQuarter) {
      navigate(`/reports/quarterly/${quarter}`, { replace: true });
    }
  }, [quarter, fetchReport, navigate, paramQuarter]);

  const handleQuarterChange = (q: string) => {
    setQuarter(q);
  };

  const handleSaveSection = async (key: string, content: string) => {
    if (!report) return;
    const updated = await updateQuarterlyReport(quarter, {
      sections: { ...report.sections, [key]: content },
    });
    setReport(updated);
  };

  const handleFinalize = async () => {
    if (!report) return;
    if (!confirm('Finalize this report? It will be visible to your leader and cannot be moved back to draft.')) return;
    setFinalizing(true);
    try {
      const updated = await finalizeQuarterlyReport(quarter);
      setReport(updated);
    } finally {
      setFinalizing(false);
    }
  };

  const handleBack = () => {
    if (isDraft && !window.confirm('You may have unsaved section edits. Leave anyway?')) return;
    navigate(-1);
  };

  const isDraft = report?.status === 'draft';
  const isFinalized = report?.status === 'finalized';

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <button
        onClick={handleBack}
        style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', padding: 0, fontSize: '0.85rem', marginBottom: '1rem', display: 'block' }}
      >
        ← Back
      </button>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 700 }}>Quarterly Report</h1>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <QuarterSelector value={quarter} onChange={handleQuarterChange} />
          {report && <ReportStatusBadge status={report.status} />}
        </div>
      </div>

      {error && (
        <div style={{ color: 'var(--error)', background: 'var(--error-bg)', border: '1px solid var(--error-bg)', borderRadius: '6px', padding: '0.75rem', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {loading && <p style={{ color: 'var(--text-muted)' }}>Loading…</p>}

      {!loading && (
        <>
          {/* Generation panel — always shown unless finalized */}
          {!isFinalized && (
            <div style={{ marginBottom: '1.5rem' }}>
              <GenerationPanel
                quarter={quarter}
                existing={report}
                onGenerated={(r) => { setReport(r); setTimeout(() => fetchReport(quarter), 8000); }}
              />
            </div>
          )}

          {/* Report sections */}
          {(isDraft || isFinalized) && report?.sections && (
            <>
              {Object.entries(SECTION_TITLES).map(([key, title]) => (
                <ReportSection
                  key={key}
                  title={title}
                  content={report.sections?.[key as keyof typeof report.sections] ?? ''}
                  editable={isDraft}
                  onSave={isDraft ? (c) => handleSaveSection(key, c) : undefined}
                />
              ))}

              {isDraft && (
                <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-end' }}>
                  <button
                    onClick={handleFinalize}
                    disabled={finalizing}
                    style={{
                      padding: '0.5rem 1.5rem',
                      border: 'none',
                      borderRadius: '6px',
                      background: finalizing ? 'var(--primary-bg)' : 'var(--success)',
                      color: 'white',
                      cursor: finalizing ? 'not-allowed' : 'pointer',
                      fontWeight: 600,
                      fontSize: '0.875rem',
                    }}
                  >
                    {finalizing ? 'Finalizing…' : 'Finalize Report'}
                  </button>
                </div>
              )}

              {isFinalized && report.finalized_at && (
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                  Finalized on {new Date(report.finalized_at).toLocaleDateString()}
                </p>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
};
