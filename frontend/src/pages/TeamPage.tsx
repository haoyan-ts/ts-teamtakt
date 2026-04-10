import { useEffect, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { useAuthStore } from '../stores/authStore';
import {
  getTeamMissingDays,
  getCategoryBalance,
  getOverloadMetrics,
  getBlockerMetrics,
  getFragmentationMetrics,
  getCarryoverAgingMetrics,
  getProjectEffortMetrics,
  type MissingDay,
  type MemberBalance,
  type OverloadEntry,
  type BlockerSummary,
  type FragmentationEntry,
  type CarryoverAgingEntry,
  type ProjectEffortEntry,
} from '../api/teams';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function mondayISO(from = new Date()) {
  const day = from.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  from.setDate(from.getDate() + diff);
  return from.toISOString().slice(0, 10);
}

const COLORS = ['#3182ce', '#48bb78', '#ed8936', '#9f7aea', '#e53e3e', '#38b2ac', '#d69e2e', '#667eea'];

// ---------------------------------------------------------------------------
// Shared card / style atoms
// ---------------------------------------------------------------------------

const cardStyle: React.CSSProperties = {
  border: '1px solid #e2e8f0',
  borderRadius: '8px',
  padding: '1rem',
  background: '#fff',
};
const cardTitle: React.CSSProperties = { margin: '0 0 0.75rem', fontSize: '0.95rem', fontWeight: 600 };
const emptyText: React.CSSProperties = { fontSize: '0.85rem', color: '#a0aec0', fontStyle: 'italic' };
const th: React.CSSProperties = { textAlign: 'left', padding: '0.3rem 0.5rem', fontWeight: 600, color: '#4a5568', fontSize: '0.8rem' };
const td: React.CSSProperties = { padding: '0.3rem 0.5rem', fontSize: '0.83rem' };

function MetricCard({ title, children, loading }: { title: string; children: React.ReactNode; loading: boolean }) {
  return (
    <div style={cardStyle}>
      <h3 style={cardTitle}>{title}</h3>
      {loading ? <p style={emptyText}>Loading…</p> : children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 1. Category Balance
// ---------------------------------------------------------------------------

function BalanceChart({ members }: { members: MemberBalance[]; targets: Record<string, number> }) {
  const categories = Array.from(new Set(members.flatMap((m) => Object.keys(m.categories))));
  if (members.length === 0 || categories.length === 0) {
    return <p style={emptyText}>No task data for this period.</p>;
  }

  const chartData = members.map((m) => ({ name: m.display_name.split(' ')[0], ...m.categories }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={chartData} layout="vertical" margin={{ left: 60 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
        <YAxis type="category" dataKey="name" width={60} tick={{ fontSize: 11 }} />
        <Tooltip formatter={(v) => typeof v === 'number' ? `${v.toFixed(1)}%` : String(v)} />
        <Legend wrapperStyle={{ fontSize: '0.75rem' }} />
        {categories.map((cat, i) => (
          <Bar key={cat} dataKey={cat} stackId="a" fill={COLORS[i % COLORS.length]} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// 2. Overload Detection
// ---------------------------------------------------------------------------

function OverloadPanel({ entries }: { entries: OverloadEntry[] }) {
  if (entries.length === 0) return <p style={emptyText}>No overload alerts this period. ✓</p>;
  const sorted = [...entries].sort(
    (a, b) =>
      (new Date(b.streak_end).getTime() - new Date(b.streak_start).getTime()) -
      (new Date(a.streak_end).getTime() - new Date(a.streak_start).getTime())
  );
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      {sorted.map((e) => {
        const days =
          Math.round((new Date(e.streak_end).getTime() - new Date(e.streak_start).getTime()) / 86400000) + 1;
        const color = days >= 5 ? '#e53e3e' : days >= 3 ? '#ed8936' : '#d69e2e';
        return (
          <div key={`${e.user_id}-${e.streak_start}`}
            style={{ padding: '0.4rem 0.6rem', borderLeft: `4px solid ${color}`, background: '#fffaf0', borderRadius: 4 }}>
            <strong style={{ fontSize: '0.88rem' }}>{e.display_name}</strong>
            <span style={{ fontSize: '0.78rem', marginLeft: '0.5rem', color: '#718096' }}>
              {e.streak_start} → {e.streak_end} ({days}d) · max load {e.max_load}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. Blocker Summary
// ---------------------------------------------------------------------------

function BlockerPanel({ summary }: { summary: BlockerSummary | null }) {
  if (!summary) return <p style={emptyText}>No data.</p>;
  if (summary.by_type.length === 0) return <p style={emptyText}>No blockers this period. ✓</p>;
  return (
    <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
      <div style={{ flex: '0 0 160px' }}>
        <ResponsiveContainer width={160} height={160}>
          <PieChart>
            <Pie data={summary.by_type} dataKey="count" nameKey="type" cx="50%" cy="50%" outerRadius={65} label={(e) => e.name ?? ''}>  
              {summary.by_type.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </div>
      {summary.recurring.length > 0 && (
        <div style={{ flex: 1, minWidth: 200 }}>
          <p style={{ ...th, marginBottom: '0.25rem' }}>Recurring Blockers</p>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={th}>Task</th>
                <th style={th}>Project</th>
                <th style={th}>Days</th>
              </tr>
            </thead>
            <tbody>
              {summary.recurring.map((r, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #e2e8f0' }}>
                  <td style={td}>{r.task_desc}</td>
                  <td style={td}>{r.project}</td>
                  <td style={td}>{r.days_blocked}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 4. Fragmentation
// ---------------------------------------------------------------------------

function FragmentationPanel({ entries }: { entries: FragmentationEntry[] }) {
  if (entries.length === 0) return <p style={emptyText}>No fragmentation events this period. ✓</p>;
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
          <th style={th}>Member</th>
          <th style={th}>Date</th>
          <th style={th}>Tasks</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((f, i) => (
          <tr key={i} style={{ borderBottom: '1px solid #f7fafc' }}>
            <td style={td}>{f.display_name}</td>
            <td style={td}>{f.date}</td>
            <td style={{ ...td, fontWeight: 600, color: '#e53e3e' }}>{f.task_count}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------------------
// 5. Carry-over Aging
// ---------------------------------------------------------------------------

function CarryoverPanel({ entries, threshold }: { entries: CarryoverAgingEntry[]; threshold: number }) {
  if (entries.length === 0) return <p style={emptyText}>No stale carry-overs. ✓</p>;
  const sorted = [...entries].sort((a, b) => b.working_days_aged - a.working_days_aged);
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
          <th style={th}>Member</th>
          <th style={th}>Task</th>
          <th style={th}>Project</th>
          <th style={th}>Since</th>
          <th style={th}>Working Days</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((e, i) => {
          const color = e.working_days_aged > threshold ? '#e53e3e' : e.working_days_aged >= threshold * 0.8 ? '#ed8936' : '#2d3748';
          return (
            <tr key={i} style={{ borderBottom: '1px solid #f7fafc' }}>
              <td style={td}>{e.display_name}</td>
              <td style={{ ...td, color: '#4a5568' }}>{e.task_desc}</td>
              <td style={td}>{e.project}</td>
              <td style={td}>{e.root_date}</td>
              <td style={{ ...td, fontWeight: 700, color }}>{e.working_days_aged}d</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------------------
// 6. Project Effort
// ---------------------------------------------------------------------------

function ProjectEffortPanel({ entries }: { entries: ProjectEffortEntry[] }) {
  if (entries.length === 0) return <p style={emptyText}>No project effort data.</p>;
  const [expanded, setExpanded] = useState<string | null>(null);
  const data = entries.map((e) => ({ name: e.name, effort: e.total_effort, id: e.project_id }));
  return (
    <div>
      <ResponsiveContainer width="100%" height={Math.max(120, entries.length * 30)}>
        <BarChart data={data} layout="vertical" margin={{ left: 60 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" />
          <YAxis type="category" dataKey="name" width={80} tick={{ fontSize: 11 }} />
          <Tooltip />
          <Bar dataKey="effort" fill="#3182ce" />
        </BarChart>
      </ResponsiveContainer>
      <div style={{ marginTop: '0.5rem' }}>
        {entries.map((e) => (
          <div key={e.project_id}>
            <button
              onClick={() => setExpanded(expanded === e.project_id ? null : e.project_id)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.82rem', color: '#3182ce', padding: '2px 0' }}
            >
              {expanded === e.project_id ? '▾' : '▸'} {e.name} ({e.total_effort} effort pts)
            </button>
            {expanded === e.project_id && (
              <ul style={{ margin: '0.25rem 0 0.25rem 1rem', padding: 0, listStyle: 'none', fontSize: '0.8rem', color: '#4a5568' }}>
                {e.member_effort.map((m) => (
                  <li key={m.user_id}>{m.display_name}: {m.effort}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Unreported today
// ---------------------------------------------------------------------------

function UnreportedCard({ teamId, today }: { teamId: string; today: string }) {
  const [missing, setMissing] = useState<MissingDay[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTeamMissingDays(teamId, { start_date: today, end_date: today })
      .then(setMissing)
      .catch(() => setMissing([]))
      .finally(() => setLoading(false));
  }, [teamId, today]);

  return (
    <MetricCard title={`Unreported Today (${today})`} loading={loading}>
      {missing.length === 0 ? (
        <p style={emptyText}>All members have reported. ✓</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
              <th style={th}>Member</th>
              <th style={th}>Last Reported</th>
              <th style={th}>Consecutive Missing</th>
            </tr>
          </thead>
          <tbody>
            {missing.map((m) => (
              <tr key={m.user_id} style={{ borderBottom: '1px solid #e2e8f0' }}>
                <td style={td}>{m.display_name}</td>
                <td style={td}>{m.last_reported ?? '—'}</td>
                <td style={td}>{m.consecutive_missing}d</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </MetricCard>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export const TeamPage = () => {
  const { user } = useAuthStore();
  const teamId = user?.team?.id;

  const [startDate, setStartDate] = useState(mondayISO());
  const [endDate, setEndDate] = useState(todayISO());

  // metric states
  const [balance, setBalance] = useState<{ members: MemberBalance[]; targets: Record<string, number> } | null>(null);
  const [overload, setOverload] = useState<OverloadEntry[]>([]);
  const [blockers, setBlockers] = useState<BlockerSummary | null>(null);
  const [fragmentation, setFragmentation] = useState<FragmentationEntry[]>([]);
  const [carryover, setCarryover] = useState<CarryoverAgingEntry[]>([]);
  const [projects, setProjects] = useState<ProjectEffortEntry[]>([]);
  const [agingThreshold, setAgingThreshold] = useState(5);

  const [loads, setLoads] = useState({
    balance: true, overload: true, blockers: true,
    fragmentation: true, carryover: true, projects: true,
  });

  const params = { start_date: startDate, end_date: endDate };

  useEffect(() => {
    if (!teamId) return;
    setLoads({ balance: true, overload: true, blockers: true, fragmentation: true, carryover: true, projects: true });

    getCategoryBalance(teamId, params)
      .then((d) => setBalance({ members: d.members, targets: d.targets }))
      .catch(() => setBalance(null))
      .finally(() => setLoads((l) => ({ ...l, balance: false })));

    getOverloadMetrics(teamId, params)
      .then(setOverload)
      .catch(() => setOverload([]))
      .finally(() => setLoads((l) => ({ ...l, overload: false })));

    getBlockerMetrics(teamId, params)
      .then(setBlockers)
      .catch(() => setBlockers(null))
      .finally(() => setLoads((l) => ({ ...l, blockers: false })));

    getFragmentationMetrics(teamId, params)
      .then(setFragmentation)
      .catch(() => setFragmentation([]))
      .finally(() => setLoads((l) => ({ ...l, fragmentation: false })));

    getCarryoverAgingMetrics(teamId, params)
      .then(setCarryover)
      .catch(() => setCarryover([]))
      .finally(() => setLoads((l) => ({ ...l, carryover: false })));

    getProjectEffortMetrics(teamId, params)
      .then(setProjects)
      .catch(() => setProjects([]))
      .finally(() => setLoads((l) => ({ ...l, projects: false })));

    // load aging threshold from settings
    import('../api/teams').then(({ getTeamSettings }) => {
      getTeamSettings(teamId).then((s) => setAgingThreshold(s.carryover_aging_days)).catch(() => {});
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [teamId, startDate, endDate]);

  if (!teamId) {
    return <div>You are not assigned to a team.</div>;
  }

  const grid: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))',
    gap: '1rem',
  };

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto' }}>
      {/* Header + date range */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <h2 style={{ margin: 0 }}>Team Dashboard</h2>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', fontSize: '0.85rem' }}>
          <label>From <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
            style={{ border: '1px solid #cbd5e0', borderRadius: 4, padding: '2px 6px', fontSize: '0.83rem' }} /></label>
          <label>To <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
            style={{ border: '1px solid #cbd5e0', borderRadius: 4, padding: '2px 6px', fontSize: '0.83rem' }} /></label>
          <a href="/team/settings/balance" style={{ marginLeft: '0.5rem', fontSize: '0.8rem', color: '#3182ce' }}>⚙ Settings</a>
        </div>
      </div>

      {/* Unreported */}
      <div style={{ marginBottom: '1rem' }}>
        <UnreportedCard teamId={teamId} today={todayISO()} />
      </div>

      {/* 2×3 grid of metric panels */}
      <div style={grid}>
        <MetricCard title="Category Balance" loading={loads.balance}>
          {balance ? (
            <BalanceChart members={balance.members} targets={balance.targets} />
          ) : (
            <p style={emptyText}>Could not load balance data.</p>
          )}
        </MetricCard>

        <MetricCard title="Overload Alerts" loading={loads.overload}>
          <OverloadPanel entries={overload} />
        </MetricCard>

        <MetricCard title="Blocker Summary" loading={loads.blockers}>
          <BlockerPanel summary={blockers} />
        </MetricCard>

        <MetricCard title="Fragmentation" loading={loads.fragmentation}>
          <FragmentationPanel entries={fragmentation} />
        </MetricCard>

        <MetricCard title="Carry-over Aging" loading={loads.carryover}>
          <CarryoverPanel entries={carryover} threshold={agingThreshold} />
        </MetricCard>

        <MetricCard title="Project Effort" loading={loads.projects}>
          <ProjectEffortPanel entries={projects} />
        </MetricCard>
      </div>
    </div>
  );
};
