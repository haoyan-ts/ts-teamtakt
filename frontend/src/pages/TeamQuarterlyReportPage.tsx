import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import type { QuarterlyReport } from '../api/quarterlyReports';
import { listTeamQuarterlyReports } from '../api/quarterlyReports';
import { QuarterSelector } from '../components/quarterly/QuarterSelector';
import { currentQuarter } from '../components/quarterly/quarterUtils';
import { ReportStatusBadge } from '../components/quarterly/ReportStatusBadge';
import { ReportSection } from '../components/quarterly/ReportSection';
import { useAuth } from '../hooks/useAuth';

const SECTION_TITLES: Record<string, string> = {
  qualitative: 'Qualitative Assessment',
  quantitative: 'Quantitative Summary',
  highlights: 'Highlights',
  overall: 'Overall Reflection',
};

export const TeamQuarterlyReportPage = () => {
  const { quarter: paramQuarter } = useParams<{ quarter?: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [quarter, setQuarter] = useState(paramQuarter || currentQuarter());
  const [reports, setReports] = useState<QuarterlyReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedReport, setSelectedReport] = useState<QuarterlyReport | null>(null);

  const teamId = user?.team?.id;

  const fetchReports = useCallback(async (q: string) => {
    if (!teamId) return;
    setLoading(true);
    setError(null);
    setSelectedReport(null);
    try {
      const data = await listTeamQuarterlyReports(teamId, q);
      setReports(data);
    } catch {
      setError('Failed to load reports.');
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    fetchReports(quarter);
    if (quarter !== paramQuarter) {
      navigate(`/team/quarterly/${quarter}`, { replace: true });
    }
  }, [quarter, fetchReports, navigate, paramQuarter]);

  if (!teamId) {
    return <p style={{ color: 'var(--text-muted)' }}>Not assigned to a team.</p>;
  }

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 700 }}>Team Quarterly Reports</h1>
        <QuarterSelector value={quarter} onChange={setQuarter} />
      </div>

      {error && (
        <div style={{ color: 'var(--error)', background: 'var(--error-bg)', border: '1px solid var(--error-bg)', borderRadius: '6px', padding: '0.75rem', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {loading && <p style={{ color: 'var(--text-muted)' }}>Loading…</p>}

      {!loading && !selectedReport && (
        <>
          {reports.length === 0 ? (
            <p style={{ color: 'var(--text-muted)' }}>No finalized reports for {quarter}.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {reports.map((r) => (
                <button
                  key={r.id}
                  onClick={() => setSelectedReport(r)}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '1rem 1.25rem',
                    background: 'var(--bg)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    textAlign: 'left',
                    width: '100%',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, color: 'var(--text-h)', fontSize: '1rem' }}>
                      Team Member
                    </div>
                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.125rem' }}>
                      {r.finalized_at ? `Finalized ${new Date(r.finalized_at).toLocaleDateString()}` : ''}
                    </div>
                  </div>
                  <ReportStatusBadge status={r.status} />
                </button>
              ))}
            </div>
          )}
        </>
      )}

      {selectedReport && (
        <div>
          <button
            onClick={() => setSelectedReport(null)}
            style={{ marginBottom: '1rem', fontSize: '0.875rem', color: 'var(--primary)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
          >
            ← Back to list
          </button>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700 }}>
              {quarter} Report
            </h2>
            <ReportStatusBadge status={selectedReport.status} />
          </div>
          {selectedReport.sections && Object.entries(SECTION_TITLES).map(([key, title]) => (
            <ReportSection
              key={key}
              title={title}
              content={selectedReport.sections?.[key as keyof typeof selectedReport.sections] ?? ''}
              editable={false}
            />
          ))}
        </div>
      )}
    </div>
  );
};
