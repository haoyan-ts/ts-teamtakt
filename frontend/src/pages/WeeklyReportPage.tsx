import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';
import {
  generateWeeklyReport,
  getWeeklyReport,
  createEmailDraft,
  getEmailDraft,
  updateEmailDraft,
  sendEmailDraft,
  type WeeklyReportSummary,
  type WeeklyEmailDraft,
} from '../api/reports';

function mondayBefore(d = new Date()) {
  const day = d.getDay();
  // last completed week = previous Mon
  const offset = day === 0 ? -13 : -6 - (day - 1);
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
}

function weekLabel(weekStart: string) {
  const d = new Date(weekStart);
  const end = new Date(d);
  end.setDate(end.getDate() + 6);
  return `${d.toLocaleDateString()} – ${end.toLocaleDateString()}`;
}

function fmt5minLeft(sentAt: string) {
  const elapsed = (Date.now() - new Date(sentAt).getTime()) / 1000;
  const remaining = Math.max(0, 300 - elapsed);
  return `${Math.ceil(remaining / 60)}m ${Math.ceil(remaining % 60)}s`;
}

// ---------------------------------------------------------------------------
// Email Editor section
// ---------------------------------------------------------------------------

function EmailEditor({
  weekStart,
  onBack,
}: {
  weekStart: string;
  onBack: () => void;
}) {
  const [draft, setDraft] = useState<WeeklyEmailDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [sending, setSending] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState('');
  const [cooldown, setCooldown] = useState(false);

  const checkCooldown = useCallback((d: WeeklyEmailDraft) => {
    if (d.status === 'sent' && d.last_sent_at) {
      const elapsed = (Date.now() - new Date(d.last_sent_at).getTime()) / 1000;
      setCooldown(elapsed < 300);
    }
  }, []);

  const loadDraft = useCallback(async () => {
    const d = await getEmailDraft(weekStart);
    if (d) { setDraft(d); checkCooldown(d); }
    setLoading(false);
  }, [weekStart, checkCooldown]);

  useEffect(() => { loadDraft(); }, [loadDraft]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError('');
    try {
      const d = await createEmailDraft(weekStart);
      setDraft(d);
    } catch {
      setError('Generation failed. Check that your weekly report is generated first.');
    } finally {
      setGenerating(false);
    }
  };

  const handleChange = (field: keyof WeeklyEmailDraft['body_sections'] | 'subject', value: string) => {
    if (!draft) return;
    if (field === 'subject') {
      setDraft({ ...draft, subject: value });
    } else {
      setDraft({ ...draft, body_sections: { ...draft.body_sections, [field]: value } });
    }
  };

  const handleSave = async () => {
    if (!draft) return;
    try {
      const updated = await updateEmailDraft(draft.id, {
        subject: draft.subject,
        body_sections: draft.body_sections,
      });
      setDraft(updated);
    } catch { /* ignore */ }
  };

  const handleSend = async () => {
    if (!draft) return;
    setSending(true);
    setError('');
    try {
      const sent = await sendEmailDraft(draft.id);
      setDraft(sent);
      setCooldown(true);
      setTimeout(() => setCooldown(false), 300000);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? 'Send failed.');
    } finally {
      setSending(false);
      setShowConfirm(false);
    }
  };

  if (loading) return <div>Loading draft…</div>;

  const sent = draft?.status === 'sent';

  return (
    <div style={{ maxWidth: '700px', margin: '0 auto' }}>
      <button onClick={onBack} style={{ marginBottom: '1rem', background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', fontSize: '0.85rem' }}>
        ← Back to Report
      </button>
      <h3>Weekly Email Draft — {weekLabel(weekStart)}</h3>

      {!draft ? (
        <div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>No draft yet. Generate one with AI:</p>
          <button onClick={handleGenerate} disabled={generating}
            style={{ padding: '0.4rem 1rem', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
            {generating ? 'Generating…' : '✨ Generate Draft'}
          </button>
          {error && <p style={{ color: 'var(--error)', fontSize: '0.85rem', marginTop: '0.5rem' }}>{error}</p>}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {sent && (
            <div style={{ background: 'var(--success-bg)', border: '1px solid var(--success-bg)', borderRadius: 6, padding: '0.5rem 0.75rem', fontSize: '0.85rem', color: 'var(--success)' }}>
              ✓ Sent at {new Date(draft.last_sent_at!).toLocaleString()}
              {cooldown && <span style={{ marginLeft: '1rem', color: 'var(--text-secondary)' }}>Cooldown: {fmt5minLeft(draft.last_sent_at!)}</span>}
            </div>
          )}
          <div>
            <label style={{ display: 'block', fontWeight: 600, fontSize: '0.85rem', marginBottom: 2 }}>Subject</label>
            <input value={draft.subject} onChange={(e) => handleChange('subject', e.target.value)}
              style={{ width: '100%', border: '1px solid var(--border-strong)', borderRadius: 4, padding: '4px 8px', fontSize: '0.88rem', background: 'var(--bg)', color: 'var(--text-h)' }} />
          </div>
          {(['tasks', 'highlights', 'next_week'] as const).map((section) => (
            <div key={section}>
              <label style={{ display: 'block', fontWeight: 600, fontSize: '0.85rem', marginBottom: 2, textTransform: 'capitalize' }}>
                {section === 'tasks' ? '業務' : section === 'highlights' ? '〇・×' : '予定'}
              </label>
              <textarea
                value={draft.body_sections[section]}
                onChange={(e) => handleChange(section, e.target.value)}
                rows={5}
                style={{ width: '100%', border: '1px solid var(--border-strong)', borderRadius: 4, padding: '6px 8px', fontSize: '0.85rem', fontFamily: 'inherit', resize: 'vertical', background: 'var(--bg)', color: 'var(--text-h)' }}
              />
            </div>
          ))}
          {error && <p style={{ color: 'var(--error)', fontSize: '0.85rem' }}>{error}</p>}
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button onClick={handleSave}
              style={{ padding: '0.4rem 1rem', background: 'var(--primary)', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: '0.85rem' }}>
              Save Draft
            </button>
            <button onClick={handleGenerate} disabled={generating}
              style={{ padding: '0.4rem 1rem', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: '0.85rem' }}>
              {generating ? 'Regenerating…' : '↻ Regenerate'}
            </button>
            <button
              onClick={() => setShowConfirm(true)}
              disabled={sent && cooldown}
              style={{ padding: '0.4rem 1rem', background: sent && cooldown ? 'var(--text-muted)' : 'var(--success)', color: '#fff', border: 'none', borderRadius: 6, cursor: sent && cooldown ? 'not-allowed' : 'pointer', fontSize: '0.85rem' }}>
              Send Email
            </button>
          </div>
        </div>
      )}

      {/* Confirm dialog */}
      {showConfirm && draft && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000,
        }}>
          <div style={{ background: 'var(--bg)', borderRadius: 10, padding: '1.5rem', maxWidth: 500, width: '90%' }}>
            <h4 style={{ margin: '0 0 0.5rem' }}>Send Email?</h4>
            <p style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>Subject: <strong>{draft.subject}</strong></p>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              The email will be sent from your account to your leader and configured CC addresses.
            </p>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button onClick={handleSend} disabled={sending}
                style={{ padding: '0.4rem 1rem', background: 'var(--success)', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
                {sending ? 'Sending…' : 'Confirm Send'}
              </button>
              <button onClick={() => setShowConfirm(false)}
                style={{ padding: '0.4rem 1rem', background: 'none', border: '1px solid var(--border-strong)', borderRadius: 6, cursor: 'pointer' }}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Report dashboard
// ---------------------------------------------------------------------------

export const WeeklyReportPage = () => {
  const { week_start } = useParams<{ week_start?: string }>();
  const navigate = useNavigate();

  const [weekStart, setWeekStart] = useState(week_start ?? mondayBefore());
  const [report, setReport] = useState<WeeklyReportSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [showEmail, setShowEmail] = useState(false);

  useEffect(() => {
    setLoading(true);
    getWeeklyReport(weekStart)
      .then(setReport)
      .finally(() => setLoading(false));
  }, [weekStart]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const r = await generateWeeklyReport(weekStart);
      setReport(r);
    } catch {
      alert('Generation failed. The edit window may still be open for this week.');
    } finally {
      setGenerating(false);
    }
  };

  const handleWeekChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const d = new Date(e.target.value);
    // snap to Monday
    const mon = d.getDay() === 1 ? d : (() => { const t = new Date(d); const off = t.getDay() === 0 ? -6 : 1 - t.getDay(); t.setDate(t.getDate() + off); return t; })();
    const iso = mon.toISOString().slice(0, 10);
    setWeekStart(iso);
    navigate(`/reports/weekly/${iso}`, { replace: true });
    setShowEmail(false);
  };

  if (showEmail) {
    return <EmailEditor weekStart={weekStart} onBack={() => setShowEmail(false)} />;
  }

  const card: React.CSSProperties = { border: '1px solid var(--border)', borderRadius: 8, padding: '1rem', background: 'var(--bg)' };
  const cardTitle: React.CSSProperties = { margin: '0 0 0.75rem', fontSize: '0.95rem', fontWeight: 600 };

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <h2 style={{ margin: 0 }}>Weekly Report</h2>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <label style={{ fontSize: '0.85rem' }}>
            Week starting: <input type="date" value={weekStart} onChange={handleWeekChange}
              style={{ border: '1px solid var(--border-strong)', borderRadius: 4, padding: '2px 6px', fontSize: '0.83rem', background: 'var(--bg)', color: 'var(--text-h)' }} />
          </label>
          {report && (
            <>
              <a href={`/api/v1/export/my-records?start_date=${weekStart}&end_date=${new Date(new Date(weekStart).getTime() + 6 * 86400000).toISOString().slice(0, 10)}&format=csv`}
                style={{ fontSize: '0.82rem', color: 'var(--primary)', marginLeft: '0.5rem' }}>↓ CSV</a>
              <a href={`/api/v1/export/my-records?start_date=${weekStart}&end_date=${new Date(new Date(weekStart).getTime() + 6 * 86400000).toISOString().slice(0, 10)}&format=xlsx`}
                style={{ fontSize: '0.82rem', color: 'var(--primary)' }}>↓ XLSX</a>
              <button onClick={() => setShowEmail(true)}
                style={{ padding: '0.3rem 0.8rem', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: '0.82rem' }}>
                ✉ Email Draft
              </button>
            </>
          )}
        </div>
      </div>

      {loading ? (
        <p>Loading…</p>
      ) : !report ? (
        <div style={{ ...card, textAlign: 'center', padding: '2rem' }}>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>No report for {weekLabel(weekStart)} yet.</p>
          <button onClick={handleGenerate} disabled={generating}
            style={{ padding: '0.5rem 1.5rem', background: 'var(--primary)', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
            {generating ? 'Generating…' : 'Generate Report'}
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: '1rem' }}>
          {/* KPI row */}
          <div style={{ ...card, gridColumn: '1 / -1', display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
            {[
              { label: 'Days Reported', value: report.data.days_reported },
              { label: 'Avg Load', value: report.data.avg_day_load?.toFixed(1) ?? '—' },
              { label: 'Carry-overs', value: report.data.carry_over_count },
              { label: 'Blockers', value: report.data.blocker_count },
            ].map((kpi) => (
              <div key={kpi.label} style={{ textAlign: 'center', flex: '1 1 80px' }}>
                <div style={{ fontSize: '1.6rem', fontWeight: 700 }}>{kpi.value}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{kpi.label}</div>
              </div>
            ))}
          </div>

          {/* Category breakdown */}
          <div style={card}>
            <h3 style={cardTitle}>Category Breakdown</h3>
            {Object.keys(report.data.category_breakdown).length === 0 ? (
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No data.</p>
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <BarChart
                  data={Object.entries(report.data.category_breakdown).map(([k, v]) => ({ name: k, pct: v }))}
                  layout="vertical" margin={{ left: 60 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" unit="%" domain={[0, 100]} tick={{ fontSize: 10 }} />
                  <YAxis type="category" dataKey="name" width={60} tick={{ fontSize: 10 }} />
                  <Tooltip formatter={(v) => typeof v === 'number' ? `${v.toFixed(1)}%` : String(v)} />
                  <Bar dataKey="pct" fill="#3182ce" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Top projects */}
          <div style={card}>
            <h3 style={cardTitle}>Top Projects</h3>
            {report.data.top_projects.length === 0 ? (
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No data.</p>
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <BarChart
                  data={report.data.top_projects.map((p) => ({ name: p.name, effort: p.effort }))}
                  layout="vertical" margin={{ left: 80 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" tick={{ fontSize: 10 }} />
                  <YAxis type="category" dataKey="name" width={80} tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="effort" fill="#48bb78" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Tag distribution */}
          <div style={card}>
            <h3 style={cardTitle}>Self-assessment Tags</h3>
            {Object.keys(report.data.tag_distribution).length === 0 ? (
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No data.</p>
            ) : (
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: '0.85rem' }}>
                {Object.entries(report.data.tag_distribution).map(([tag, count]) => (
                  <li key={tag} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', borderBottom: '1px solid var(--bg-tertiary)' }}>
                    <span>{tag}</span><strong>{count}</strong>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
