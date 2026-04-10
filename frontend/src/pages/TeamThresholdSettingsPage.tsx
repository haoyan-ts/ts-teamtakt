import { useEffect, useState } from 'react';
import { useAuthStore } from '../stores/authStore';
import { getTeamSettings, updateTeamSettings, type TeamSettings } from '../api/teams';

type ThresholdField = Pick<
  TeamSettings,
  'overload_load_threshold' | 'overload_streak_days' | 'fragmentation_task_threshold' | 'carryover_aging_days'
>;

const FIELDS: { key: keyof ThresholdField; label: string; min: number; max: number; hint: string }[] = [
  { key: 'overload_load_threshold', label: 'Overload: Load threshold (1–5)', min: 1, max: 5, hint: 'Day load value that counts as high load' },
  { key: 'overload_streak_days', label: 'Overload: Consecutive days (1–10)', min: 1, max: 10, hint: 'How many consecutive high-load days triggers an alert' },
  { key: 'fragmentation_task_threshold', label: 'Fragmentation: Max tasks/day (1–20)', min: 1, max: 20, hint: 'Task count per day above which fragmentation is flagged' },
  { key: 'carryover_aging_days', label: 'Carry-over aging: Days threshold (1–30)', min: 1, max: 30, hint: 'Working days after which a carry-over is considered stale' },
];

export const TeamThresholdSettingsPage = () => {
  const { user } = useAuthStore();
  const teamId = user?.team?.id;

  const [values, setValues] = useState<ThresholdField>({
    overload_load_threshold: 4,
    overload_streak_days: 3,
    fragmentation_task_threshold: 8,
    carryover_aging_days: 5,
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!teamId) return;
    getTeamSettings(teamId).then((s) => {
      setValues({
        overload_load_threshold: s.overload_load_threshold,
        overload_streak_days: s.overload_streak_days,
        fragmentation_task_threshold: s.fragmentation_task_threshold,
        carryover_aging_days: s.carryover_aging_days,
      });
    });
  }, [teamId]);

  const handleSave = async () => {
    if (!teamId) return;
    setSaving(true);
    setError('');
    try {
      await updateTeamSettings(teamId, values);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setError('Save failed.');
    } finally {
      setSaving(false);
    }
  };

  if (!teamId) return <div>Not assigned to a team.</div>;

  const inputStyle: React.CSSProperties = {
    width: '80px',
    border: '1px solid #cbd5e0',
    borderRadius: 4,
    padding: '2px 6px',
    fontSize: '0.9rem',
  };

  return (
    <div style={{ maxWidth: '500px', margin: '0 auto' }}>
      <h2>Metric Thresholds</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '1rem' }}>
        {FIELDS.map(({ key, label, min, max, hint }) => (
          <div key={key}>
            <label style={{ display: 'block', fontSize: '0.88rem', fontWeight: 600, marginBottom: '2px' }}>{label}</label>
            <p style={{ fontSize: '0.78rem', color: '#718096', margin: '0 0 4px' }}>{hint}</p>
            <input
              type="number"
              min={min}
              max={max}
              value={values[key]}
              onChange={(e) => setValues((v) => ({ ...v, [key]: Number(e.target.value) }))}
              style={inputStyle}
            />
          </div>
        ))}
      </div>
      {error && <p style={{ color: '#e53e3e', fontSize: '0.85rem' }}>{error}</p>}
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <button
          onClick={handleSave}
          disabled={saving}
          style={{ padding: '0.4rem 1.2rem', background: '#3182ce', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        {saved && <span style={{ color: '#38a169', fontSize: '0.85rem', alignSelf: 'center' }}>Saved ✓</span>}
        <a href="/team" style={{ alignSelf: 'center', fontSize: '0.85rem', color: '#718096' }}>← Back</a>
      </div>
    </div>
  );
};
