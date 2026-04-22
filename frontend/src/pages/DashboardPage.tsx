import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { getDailyRecords, getEffortBreakdown } from '../api/dailyRecords';
import { getActiveTasks } from '../api/tasks';
import { getCategories } from '../api/categories';
import { getTeamMembers } from '../api/teams';
import type { TeamMember } from '../api/teams';
import type { DailyRecord, Task, Category, DailyEffortBreakdown } from '../types/dailyRecord';
import { useAuthStore } from '../stores/authStore';
import { EffortBreakdownChart } from '../components/dashboard/EffortBreakdownChart';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function addDays(iso: string, n: number): string {
  const d = new Date(iso);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function mondayOf(iso: string): string {
  const d = new Date(iso);
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + diff);
  return d.toISOString().slice(0, 10);
}

const PIE_COLORS = ['#3182ce', '#48bb78', '#ed8936', '#9f7aea', '#e53e3e', '#38b2ac'];

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface TodayStatusCardProps {
  records: DailyRecord[];
  today: string;
}

const TodayStatusCard = ({ records, today }: TodayStatusCardProps) => {
  const navigate = useNavigate();
  const todayRecord = records.find((r) => r.record_date === today);

  let label = 'No entry yet';
  let bgColor = 'var(--bg-tertiary)';
  let borderColor = 'var(--border)';

  if (todayRecord) {
    label = `${todayRecord.daily_work_logs.length} tasks — battery ${todayRecord.day_load !== null ? todayRecord.day_load + '%' : '—'}`;
    bgColor = 'var(--success-bg)';
    borderColor = 'var(--border)';
  }

  return (
    <div style={{ ...cardStyle, background: bgColor, borderColor }}>
      <h3 style={cardTitle}>Today — {today}</h3>
      <p style={{ margin: '0.25rem 0 0.75rem', color: 'var(--text-body)' }}>{label}</p>
      <button onClick={() => navigate(`/daily/${today}`)} style={ctaBtn}>
        {todayRecord ? "Edit today's record" : "Fill today's record"}
      </button>
    </div>
  );
};

interface RunningBlockedCardProps {
  tasks: Task[];
  categories: Category[];
}

const RunningBlockedCard = ({ tasks, categories }: RunningBlockedCardProps) => {
  const navigate = useNavigate();
  const categoryName = (id: string | null) =>
    categories.find((c) => c.id === id)?.name ?? '—';

  const running = tasks.filter((t) => t.status === 'running');
  const blocked = tasks.filter((t) => t.status === 'blocked');

  return (
    <div style={cardStyle}>
      <h3 style={cardTitle}>Running / Blocked Tasks</h3>
      {tasks.length === 0 ? (
        <p style={emptyText}>No running or blocked tasks.</p>
      ) : (
        <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
          {running.map((t) => (
            <li key={t.id} style={{ marginBottom: '0.3rem' }}>
              <span style={{ color: 'var(--primary)', marginRight: '0.4rem' }}>▶</span>
              <button
                style={linkBtn}
                onClick={() => navigate(`/daily/${todayISO()}`)}
              >
                {t.title}
              </button>
              <span style={metaText}> — {categoryName(t.category_id)}</span>
            </li>
          ))}
          {blocked.map((t) => (
            <li key={t.id} style={{ marginBottom: '0.3rem' }}>
              <span style={{ color: 'var(--error)', marginRight: '0.4rem' }}>⛔</span>
              <button
                style={linkBtn}
                onClick={() => navigate(`/daily/${todayISO()}`)}
              >
                {t.title}
              </button>
              <span style={metaText}> — {categoryName(t.category_id)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

interface WeeklySummaryCardProps {
  records: DailyRecord[];
  categories: Category[];
  weekStart: string;
}

const WeeklySummaryCard = ({ records, categories, weekStart }: WeeklySummaryCardProps) => {
  const weekDates = Array.from({ length: 5 }, (_, i) => addDays(weekStart, i));
  const weekRecords = records.filter((r) => weekDates.includes(r.record_date));
  const daysReported = weekRecords.length;
  const totalTasks = weekRecords.reduce((s, r) => s + r.daily_work_logs.length, 0);

  const effortByCategory: Record<string, number> = {};
  for (const rec of weekRecords) {
    for (const te of rec.daily_work_logs) {
      const catId = te.task?.category_id ?? 'unknown';
      effortByCategory[catId] = (effortByCategory[catId] ?? 0) + te.effort;
    }
  }
  const pieData = Object.entries(effortByCategory).map(([catId, value]) => ({
    name: categories.find((c) => c.id === catId)?.name ?? catId.slice(0, 6),
    value,
  }));

  return (
    <div style={cardStyle}>
      <h3 style={cardTitle}>This Week Summary</h3>
      <p style={metaText}>
        {daysReported} day{daysReported !== 1 ? 's' : ''} reported · {totalTasks} tasks total
      </p>
      {pieData.length > 0 ? (
        <ResponsiveContainer width="100%" height={200}>
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              innerRadius={40}
              outerRadius={80}
              dataKey="value"
              label={({ name, percent }: { name?: string; percent?: number }) =>
                `${name ?? ''} ${((percent ?? 0) * 100).toFixed(0)}%`
              }
            >
              {pieData.map((_, i) => (
                <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      ) : (
        <p style={emptyText}>No tasks this week.</p>
      )}
    </div>
  );
};

interface LoadTrendCardProps {
  records: DailyRecord[];
}

const LoadTrendCard = ({ records }: LoadTrendCardProps) => {
  const withLoad = [...records]
    .filter((r) => r.day_load !== null)
    .sort((a, b) => a.record_date.localeCompare(b.record_date))
    .slice(-20)
    .map((r) => ({ date: r.record_date.slice(5), load: r.day_load as number }));

  return (
    <div style={cardStyle}>
      <h3 style={cardTitle}>Personal Battery Trend</h3>
      {withLoad.length === 0 ? (
        <p style={emptyText}>Not enough data yet.</p>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={withLoad}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} />
            <Tooltip />
            <Legend />
            <Line
              type="monotone"
              dataKey="load"
              stroke="#3182ce"
              strokeWidth={2}
              dot={(props: { cx?: number; cy?: number; payload?: { date: string; load: number } }) => {
                const { cx = 0, cy = 0, payload } = props;
                return (
                  <circle
                    key={`dot-${payload?.date}`}
                    cx={cx}
                    cy={cy}
                    r={4}
                    fill={(payload?.load ?? 100) <= 25 ? '#e53e3e' : '#3182ce'}
                    stroke="none"
                  />
                );
              }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
      <p style={{ ...metaText, marginTop: '0.25rem' }}>Red dots indicate battery ≤ 25%</p>
    </div>
  );
};

interface BlockerHistoryCardProps {
  records: DailyRecord[];
}

const BlockerHistoryCard = ({ records }: BlockerHistoryCardProps) => {
  const today = todayISO();
  const twoWeeksAgo = addDays(today, -14);

  const recentRecords = records.filter((r) => r.record_date >= twoWeeksAgo);
  const blockers: { date: string; description: string; status: string }[] = [];
  for (const rec of recentRecords) {
    for (const te of rec.daily_work_logs) {
      if (te.blocker_text || te.blocker_type_id) {
        blockers.push({
          date: rec.record_date,
          description: te.task?.title ?? `Task ${te.task_id.slice(0, 6)}`,
          status: te.task?.status ?? 'unknown',
        });
      }
    }
  }
  blockers.sort((a, b) => b.date.localeCompare(a.date));

  return (
    <div style={cardStyle}>
      <h3 style={cardTitle}>Blocker History (last 2 weeks)</h3>
      {blockers.length === 0 ? (
        <p style={emptyText}>No blockers in the last 2 weeks.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid var(--border)' }}>
              <th style={th}>Date</th>
              <th style={th}>Task</th>
              <th style={th}>Status</th>
            </tr>
          </thead>
          <tbody>
            {blockers.map((b, i) => (
              <tr
                key={i}
                style={{
                  borderBottom: '1px solid var(--border)',
                  opacity: b.status === 'done' ? 0.6 : 1,
                  textDecoration: b.status === 'done' ? 'line-through' : 'none',
                }}
              >
                <td style={td}>{b.date}</td>
                <td style={td}>{b.description}</td>
                <td style={td}>{b.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main Dashboard page
// ---------------------------------------------------------------------------

interface TeamEnergyOverviewCardProps {
  members: TeamMember[];
  today: string;
}

const TeamEnergyOverviewCard = ({ members, today }: TeamEnergyOverviewCardProps) => {
  const [breakdowns, setBreakdowns] = useState<Record<string, DailyEffortBreakdown>>({});
  const [loadingIds, setLoadingIds] = useState<Set<string>>(new Set(members.map((m) => m.user_id)));

  useEffect(() => {
    members.forEach((m) => {
      getEffortBreakdown({ date: today, user_id: m.user_id })
        .then((bd) => setBreakdowns((prev) => ({ ...prev, [m.user_id]: bd })))
        .catch(() => {/* member data unavailable — skip silently */})
        .finally(() =>
          setLoadingIds((prev) => {
            const next = new Set(prev);
            next.delete(m.user_id);
            return next;
          })
        );
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [today]);

  return (
    <div style={{ ...cardStyle, gridColumn: '1 / -1' }}>
      <h3 style={cardTitle}>Team Energy Overview — {today}</h3>
      {members.length === 0 ? (
        <p style={emptyText}>No team members.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border)' }}>
                <th style={th}>Member</th>
                <th style={th}>Total Effort</th>
                <th style={th}>deep_focus</th>
                <th style={th}>collaborative</th>
                <th style={th}>admin</th>
                <th style={th}>creative</th>
                <th style={th}>reactive</th>
                <th style={th}>Unset</th>
                <th style={th}>Battery</th>
              </tr>
            </thead>
            <tbody>
              {members.map((m) => {
                const bd = breakdowns[m.user_id];
                const isLoading = loadingIds.has(m.user_id);
                const effortFor = (key: string | null) =>
                  bd?.by_energy_type.find((e) => e.energy_type === key)?.effort ?? 0;
                return (
                  <tr key={m.user_id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={td}>{m.display_name}</td>
                    {isLoading ? (
                      <td style={td} colSpan={8}><span style={emptyText}>Loading…</span></td>
                    ) : !bd ? (
                      <td style={td} colSpan={8}><span style={emptyText}>No data</span></td>
                    ) : (
                      <>
                        <td style={{ ...td, textAlign: 'center' }}>{bd.total_effort || '—'}</td>
                        <td style={{ ...td, textAlign: 'center' }}>{effortFor('deep_focus') || '—'}</td>
                        <td style={{ ...td, textAlign: 'center' }}>{effortFor('collaborative') || '—'}</td>
                        <td style={{ ...td, textAlign: 'center' }}>{effortFor('admin') || '—'}</td>
                        <td style={{ ...td, textAlign: 'center' }}>{effortFor('creative') || '—'}</td>
                        <td style={{ ...td, textAlign: 'center' }}>{effortFor('reactive') || '—'}</td>
                        <td style={{ ...td, textAlign: 'center' }}>{effortFor(null) || '—'}</td>
                        <td style={{ ...td, textAlign: 'center' }}>
                          {bd.battery_pct !== null ? `${bd.battery_pct}%` : '—'}
                        </td>
                      </>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export const DashboardPage = () => {
  const today = todayISO();
  const weekStart = mondayOf(today);
  const fourWeeksAgo = addDays(today, -28);

  const user = useAuthStore((s) => s.user);

  const [records, setRecords] = useState<DailyRecord[]>([]);
  const [activeTasks, setActiveTasks] = useState<Task[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [breakdown, setBreakdown] = useState<DailyEffortBreakdown | null>(null);
  const [breakdownLoading, setBreakdownLoading] = useState(true);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      getDailyRecords({ start_date: fourWeeksAgo, end_date: today }),
      getActiveTasks(),
      getCategories(),
    ])
      .then(([recs, active, cats]) => {
        setRecords(recs);
        setActiveTasks(active);
        setCategories(cats);
      })
      .catch(() => setError('Failed to load dashboard data.'))
      .finally(() => setLoading(false));
  }, [fourWeeksAgo, today]);

  useEffect(() => {
    let cancelled = false;
    getEffortBreakdown({ date: today })
      .then((bd) => { if (!cancelled) { setBreakdown(bd); setBreakdownLoading(false); } })
      .catch(() => { if (!cancelled) { setBreakdown(null); setBreakdownLoading(false); } });
    return () => { cancelled = true; };
  }, [today]);

  useEffect(() => {
    const teamId = user?.team?.id;
    if (user?.is_leader && teamId) {
      getTeamMembers(teamId)
        .then(setTeamMembers)
        .catch(() => setTeamMembers([]));
    }
  }, [user?.is_leader, user?.team?.id]);

  if (loading) return <div>Loading dashboard…</div>;
  if (error) return <div style={{ color: 'var(--error)' }}>{error}</div>;

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto' }}>
      <h2 style={{ marginBottom: '1rem' }}>My Dashboard</h2>
      <TodayStatusCard records={records} today={today} />
      <div style={grid}>
        <RunningBlockedCard tasks={activeTasks} categories={categories} />
        <WeeklySummaryCard records={records} categories={categories} weekStart={weekStart} />
        <EffortBreakdownChart breakdown={breakdown} loading={breakdownLoading} />
        <LoadTrendCard records={records} />
        <BlockerHistoryCard records={records} />
      </div>
      {user?.is_leader && teamMembers.length > 0 && (
        <div style={{ marginTop: '1.5rem' }}>
          <h3 style={{ marginBottom: '0.75rem', fontSize: '1rem', fontWeight: 600 }}>Team Dashboard</h3>
          <div style={grid}>
            <TeamEnergyOverviewCard members={teamMembers} today={today} />
          </div>
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const cardStyle: React.CSSProperties = {
  border: '1px solid var(--border)',
  borderRadius: '8px',
  padding: '1rem',
  background: 'var(--bg)',
};
const cardTitle: React.CSSProperties = { margin: '0 0 0.5rem', fontSize: '0.95rem', fontWeight: 600 };
const ctaBtn: React.CSSProperties = {
  padding: '0.4rem 1rem',
  background: 'var(--primary)',
  color: '#fff',
  border: 'none',
  borderRadius: '6px',
  cursor: 'pointer',
  fontWeight: 500,
};
const linkBtn: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'var(--primary)',
  cursor: 'pointer',
  padding: 0,
  fontSize: 'inherit',
  textDecoration: 'underline',
};
const metaText: React.CSSProperties = { fontSize: '0.8rem', color: 'var(--text-secondary)', margin: 0 };
const emptyText: React.CSSProperties = { fontSize: '0.85rem', color: 'var(--text-muted)', fontStyle: 'italic' };
const grid: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))',
  gap: '1rem',
  marginTop: '1rem',
};
const th: React.CSSProperties = { textAlign: 'left', padding: '0.3rem 0.5rem', fontWeight: 600, color: 'var(--text-body)' };
const td: React.CSSProperties = { padding: '0.3rem 0.5rem' };
