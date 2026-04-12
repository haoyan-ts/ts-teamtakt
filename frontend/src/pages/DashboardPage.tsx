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
import { getDailyRecords, getAbsences } from '../api/dailyRecords';
import { getActiveTasks } from '../api/tasks';
import { getCategories } from '../api/categories';
import type { DailyRecord, Task, Category } from '../types/dailyRecord';

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
  isAbsent: boolean;
  today: string;
}

const TodayStatusCard = ({ records, isAbsent, today }: TodayStatusCardProps) => {
  const navigate = useNavigate();
  const todayRecord = records.find((r) => r.record_date === today);

  let label = 'No entry yet';
  let bgColor = '#f7fafc';
  let borderColor = '#e2e8f0';

  if (isAbsent) {
    label = 'Absent today';
    bgColor = '#ebf8ff';
    borderColor = '#bee3f8';
  } else if (todayRecord) {
    label = `${todayRecord.daily_work_logs.length} tasks — day load ${todayRecord.day_load ?? '?'}/5`;
    bgColor = '#f0fff4';
    borderColor = '#9ae6b4';
  }

  return (
    <div style={{ ...cardStyle, background: bgColor, borderColor }}>
      <h3 style={cardTitle}>Today — {today}</h3>
      <p style={{ margin: '0.25rem 0 0.75rem', color: '#4a5568' }}>{label}</p>
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
              <span style={{ color: '#2b6cb0', marginRight: '0.4rem' }}>▶</span>
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
              <span style={{ color: '#e53e3e', marginRight: '0.4rem' }}>⛔</span>
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
      <h3 style={cardTitle}>Personal Load Trend</h3>
      {withLoad.length === 0 ? (
        <p style={emptyText}>Not enough data yet.</p>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={withLoad}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis domain={[1, 5]} ticks={[1, 2, 3, 4, 5]} />
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
                    fill={(payload?.load ?? 0) >= 4 ? '#e53e3e' : '#3182ce'}
                    stroke="none"
                  />
                );
              }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
      <p style={{ ...metaText, marginTop: '0.25rem' }}>Red dots indicate day load ≥ 4</p>
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
            <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
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
                  borderBottom: '1px solid #e2e8f0',
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

export const DashboardPage = () => {
  const today = todayISO();
  const weekStart = mondayOf(today);
  const fourWeeksAgo = addDays(today, -28);

  const [records, setRecords] = useState<DailyRecord[]>([]);
  const [activeTasks, setActiveTasks] = useState<Task[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [isAbsent, setIsAbsent] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      getDailyRecords({ start_date: fourWeeksAgo, end_date: today }),
      getActiveTasks(),
      getCategories(),
      getAbsences({ start_date: today, end_date: today }),
    ])
      .then(([recs, active, cats, abs]) => {
        setRecords(recs);
        setActiveTasks(active);
        setCategories(cats);
        setIsAbsent(abs.length > 0);
      })
      .catch(() => setError('Failed to load dashboard data.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Loading dashboard…</div>;
  if (error) return <div style={{ color: '#e53e3e' }}>{error}</div>;

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto' }}>
      <h2 style={{ marginBottom: '1rem' }}>My Dashboard</h2>
      <TodayStatusCard records={records} isAbsent={isAbsent} today={today} />
      <div style={grid}>
        <RunningBlockedCard tasks={activeTasks} categories={categories} />
        <WeeklySummaryCard records={records} categories={categories} weekStart={weekStart} />
        <LoadTrendCard records={records} />
        <BlockerHistoryCard records={records} />
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const cardStyle: React.CSSProperties = {
  border: '1px solid #e2e8f0',
  borderRadius: '8px',
  padding: '1rem',
  background: '#fff',
};
const cardTitle: React.CSSProperties = { margin: '0 0 0.5rem', fontSize: '0.95rem', fontWeight: 600 };
const ctaBtn: React.CSSProperties = {
  padding: '0.4rem 1rem',
  background: '#3182ce',
  color: '#fff',
  border: 'none',
  borderRadius: '6px',
  cursor: 'pointer',
  fontWeight: 500,
};
const linkBtn: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: '#3182ce',
  cursor: 'pointer',
  padding: 0,
  fontSize: 'inherit',
  textDecoration: 'underline',
};
const metaText: React.CSSProperties = { fontSize: '0.8rem', color: '#718096', margin: 0 };
const emptyText: React.CSSProperties = { fontSize: '0.85rem', color: '#a0aec0', fontStyle: 'italic' };
const grid: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))',
  gap: '1rem',
  marginTop: '1rem',
};
const th: React.CSSProperties = { textAlign: 'left', padding: '0.3rem 0.5rem', fontWeight: 600, color: '#4a5568' };
const td: React.CSSProperties = { padding: '0.3rem 0.5rem' };
