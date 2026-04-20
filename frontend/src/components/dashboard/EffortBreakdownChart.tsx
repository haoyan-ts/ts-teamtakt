import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import type { DailyEffortBreakdown } from '../../types/dailyRecord';
import { ENERGY_TYPE_META } from '../tasks/energyTypeMeta';
import type { EnergyType } from '../../types/dailyRecord';

interface Props {
  breakdown: DailyEffortBreakdown | null;
  loading?: boolean;
}

const cardStyle: React.CSSProperties = {
  border: '1px solid var(--border)',
  borderRadius: '8px',
  padding: '1rem',
  background: 'var(--bg)',
};
const cardTitle: React.CSSProperties = { margin: '0 0 0.5rem', fontSize: '0.95rem', fontWeight: 600 };
const metaText: React.CSSProperties = { fontSize: '0.8rem', color: 'var(--text-secondary)', margin: 0 };
const emptyText: React.CSSProperties = { fontSize: '0.85rem', color: 'var(--text-muted)', fontStyle: 'italic' };

function batteryColor(pct: number): string {
  if (pct <= 25) return '#e53e3e';
  if (pct <= 50) return '#ed8936';
  return '#48bb78';
}

export const EffortBreakdownChart = ({ breakdown, loading }: Props) => {
  if (loading) {
    return (
      <div style={cardStyle}>
        <h3 style={cardTitle}>Today's Effort by Energy Type</h3>
        <p style={emptyText}>Loading…</p>
      </div>
    );
  }

  if (!breakdown || breakdown.total_effort === 0) {
    return (
      <div style={cardStyle}>
        <h3 style={cardTitle}>Today's Effort by Energy Type</h3>
        <p style={emptyText}>No effort logged today.</p>
      </div>
    );
  }

  const chartData = breakdown.by_energy_type.map((item) => {
    const meta = item.energy_type ? ENERGY_TYPE_META[item.energy_type as EnergyType] : null;
    return {
      name: meta ? meta.icon + ' ' + item.energy_type : item.energy_type ?? 'Unset',
      effort: item.effort,
      color: meta?.color ?? 'var(--text-muted)',
    };
  });

  return (
    <div style={cardStyle}>
      <h3 style={cardTitle}>Today's Effort by Energy Type</h3>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', marginBottom: '0.5rem' }}>
        <p style={metaText}>Total effort: <strong>{breakdown.total_effort}</strong></p>
        {breakdown.battery_pct !== null ? (
          <p style={{ ...metaText, color: batteryColor(breakdown.battery_pct) }}>
            Battery: <strong>{breakdown.battery_pct}%</strong>
          </p>
        ) : (
          <p style={metaText}>Battery: —</p>
        )}
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" tick={{ fontSize: 10 }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
          <Tooltip />
          <Bar dataKey="effort" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};
