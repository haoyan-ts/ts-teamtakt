import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';
import { generateWeeklyReport, getWeeklyReport, type WeeklyReportSummary } from '../api/reports';

function firstDayOfMonth(ym?: string) {
  if (!ym) {
    const now = new Date();
    // default to last completed month
    now.setDate(1);
    now.setMonth(now.getMonth() - 1);
    return now.toISOString().slice(0, 7);
  }
  return ym;
}

function monthDateRange(ym: string) {
  const start = `${ym}-01`;
  const d = new Date(`${ym}-01`);
  d.setMonth(d.getMonth() + 1);
  d.setDate(d.getDate() - 1);
  const end = d.toISOString().slice(0, 10);
  return { start, end };
}

/** Collect all Mondays within [start, end] to fetch weekly reports */
function mondaysInRange(ymStart: string, ymEnd: string) {
  const start = new Date(`${ymStart}-01`);
  const end = new Date(ymEnd);
  // Advance to first Monday
  while (start.getDay() !== 1) start.setDate(start.getDate() + 1);
  const mondays: string[] = [];
  while (start <= end) {
    mondays.push(start.toISOString().slice(0, 10));
    start.setDate(start.getDate() + 7);
  }
  return mondays;
}

function aggregateReports(reports: WeeklyReportSummary[]): WeeklyReportSummary['data'] {
  const merged: WeeklyReportSummary['data'] = {
    days_reported: 0,
    avg_day_load: 0,
    carry_over_count: 0,
    blocker_count: 0,
    category_breakdown: {},
    top_projects: [],
    tag_distribution: {},
  };
  let loadSum = 0; let loadCount = 0;
  const projMap: Record<string, number> = {};
  for (const r of reports) {
    const d = r.data;
    merged.days_reported += d.days_reported;
    merged.carry_over_count += d.carry_over_count;
    merged.blocker_count += d.blocker_count;
    if (d.avg_day_load != null) { loadSum += d.avg_day_load * d.days_reported; loadCount += d.days_reported; }
    for (const [k, v] of Object.entries(d.category_breakdown)) {
      merged.category_breakdown[k] = ((merged.category_breakdown[k] ?? 0) + v);
    }
    for (const p of d.top_projects) {
      projMap[p.name] = (projMap[p.name] ?? 0) + p.effort;
    }
    for (const [t, c] of Object.entries(d.tag_distribution)) {
      merged.tag_distribution[t] = ((merged.tag_distribution[t] ?? 0) + (c as number));
    }
  }
  if (loadCount) merged.avg_day_load = loadSum / loadCount;
  merged.top_projects = Object.entries(projMap).map(([name, effort]) => ({ name, effort }))
    .sort((a, b) => b.effort - a.effort).slice(0, 5);
  return merged;
}

export const MonthlyReportPage = () => {
  const { ym } = useParams<{ ym?: string }>();
  const navigate = useNavigate();
  const [month, setMonth] = useState(firstDayOfMonth(ym));
  const [reports, setReports] = useState<WeeklyReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    setLoading(true);
    const { start, end } = monthDateRange(month);
    const mondays = mondaysInRange(start, end);
    Promise.all(mondays.map((m) => getWeeklyReport(m).then((r) => r).catch(() => null)))
      .then((results) => setReports(results.filter((r): r is WeeklyReportSummary => r !== null)))
      .finally(() => setLoading(false));
  }, [month]);

  const handleGenerate = async () => {
    setGenerating(true);
    const { start, end } = monthDateRange(month);
    const mondays = mondaysInRange(start, end);
    try {
      await Promise.all(mondays.map((m) => generateWeeklyReport(m).catch(() => null)));
      const results = await Promise.all(mondays.map((m) => getWeeklyReport(m).catch(() => null)));
      setReports(results.filter((r): r is WeeklyReportSummary => r !== null));
    } finally {
      setGenerating(false);
    }
  };

  const handleMonthChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setMonth(e.target.value);
    navigate(`/reports/monthly/${e.target.value}`, { replace: true });
  };

  const { start, end } = monthDateRange(month);
  const data = reports.length ? aggregateReports(reports) : null;

  const card: React.CSSProperties = { border: '1px solid var(--border)', borderRadius: 8, padding: '1rem', background: 'var(--bg)' };
  const cardTitle: React.CSSProperties = { margin: '0 0 0.75rem', fontSize: '0.95rem', fontWeight: 600 };

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <h2 style={{ margin: 0 }}>Monthly Report</h2>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <label style={{ fontSize: '0.85rem' }}>
            Month: <input type="month" value={month} onChange={handleMonthChange}
              style={{ border: '1px solid var(--border-strong)', borderRadius: 4, padding: '2px 6px', fontSize: '0.83rem', background: 'var(--bg)', color: 'var(--text-h)' }} />
          </label>
          {data && (
            <>
              <a href={`/api/v1/export/my-records?start_date=${start}&end_date=${end}&format=csv`}
                style={{ fontSize: '0.82rem', color: 'var(--primary)' }}>↓ CSV</a>
              <a href={`/api/v1/export/my-records?start_date=${start}&end_date=${end}&format=xlsx`}
                style={{ fontSize: '0.82rem', color: 'var(--primary)' }}>↓ XLSX</a>
            </>
          )}
        </div>
      </div>

      {loading ? (
        <p>Loading…</p>
      ) : !data ? (
        <div style={{ ...card, textAlign: 'center', padding: '2rem' }}>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>No reports found for {month}.</p>
          <button onClick={handleGenerate} disabled={generating}
            style={{ padding: '0.5rem 1.5rem', background: 'var(--primary)', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
            {generating ? 'Generating…' : 'Generate All Weekly Reports'}
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: '1rem' }}>
          {/* KPI row */}
          <div style={{ ...card, gridColumn: '1 / -1', display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
            {[
              { label: 'Days Reported', value: data.days_reported },
              { label: 'Avg Battery %', value: data.avg_day_load != null ? data.avg_day_load.toFixed(1) + '%' : '—' },
              { label: 'Total Carry-overs', value: data.carry_over_count },
              { label: 'Total Blockers', value: data.blocker_count },
              { label: 'Weeks with Data', value: reports.length },
            ].map((kpi) => (
              <div key={kpi.label} style={{ textAlign: 'center', flex: '1 1 80px' }}>
                <div style={{ fontSize: '1.6rem', fontWeight: 700 }}>{kpi.value}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{kpi.label}</div>
              </div>
            ))}
          </div>

          {/* Week-by-week load trend */}
          <div style={{ ...card, gridColumn: '1 / -1' }}>
            <h3 style={cardTitle}>Battery % Trend by Week</h3>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart
                data={reports.map((r) => ({ week: r.week_start.slice(5), load: r.data.avg_day_load?.toFixed(2) ?? 0 }))}
                margin={{ left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="week" tick={{ fontSize: 10 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey="load" fill="#3182ce" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Category breakdown */}
          <div style={card}>
            <h3 style={cardTitle}>Category Breakdown</h3>
            {Object.keys(data.category_breakdown).length === 0 ? (
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No data.</p>
            ) : (
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: '0.85rem' }}>
                {Object.entries(data.category_breakdown)
                  .sort((a, b) => b[1] - a[1])
                  .map(([k, v]) => (
                    <li key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', borderBottom: '1px solid var(--bg-tertiary)' }}>
                      <span>{k}</span><strong>{v.toFixed(1)}%</strong>
                    </li>
                  ))}
              </ul>
            )}
          </div>

          {/* Top projects */}
          <div style={card}>
            <h3 style={cardTitle}>Top Projects</h3>
            {data.top_projects.length === 0 ? (
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No data.</p>
            ) : (
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: '0.85rem' }}>
                {data.top_projects.map((p) => (
                  <li key={p.name} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', borderBottom: '1px solid var(--bg-tertiary)' }}>
                    <span>{p.name}</span><strong>{p.effort}</strong>
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
