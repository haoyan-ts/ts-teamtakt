import { useEffect, useState } from 'react';
import { useAuthStore } from '../stores/authStore';
import { getTeamSettings, updateTeamSettings, type TeamSettings } from '../api/teams';

export const TeamBalanceSettingsPage = () => {
  const { user } = useAuthStore();
  const teamId = user?.team?.id;

  const [settings, setSettings] = useState<TeamSettings | null>(null);
  const [targets, setTargets] = useState<Record<string, number>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!teamId) return;
    getTeamSettings(teamId).then((s) => {
      setSettings(s);
      setTargets({ ...s.balance_targets });
    });
  }, [teamId]);

  const total = Object.values(targets).reduce((a, b) => a + (b || 0), 0);

  const handleSave = async () => {
    if (!teamId) return;
    setSaving(true);
    setError('');
    try {
      await updateTeamSettings(teamId, { balance_targets: targets });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setError('Save failed.');
    } finally {
      setSaving(false);
    }
  };

  if (!teamId) return <div>Not assigned to a team.</div>;
  if (!settings) return <div>Loading…</div>;

  const inputStyle: React.CSSProperties = {
    width: '80px',
    border: '1px solid #cbd5e0',
    borderRadius: 4,
    padding: '2px 6px',
    fontSize: '0.9rem',
  };

  return (
    <div style={{ maxWidth: '500px', margin: '0 auto' }}>
      <h2>Balance Targets</h2>
      <p style={{ fontSize: '0.85rem', color: '#718096' }}>
        Set target percentage for each category. Total: <strong style={{ color: total === 100 ? '#38a169' : '#e53e3e' }}>{total}%</strong>
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1rem' }}>
        {Object.entries(targets).map(([cat, val]) => (
          <div key={cat} style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span style={{ minWidth: '120px', fontSize: '0.9rem' }}>{cat}</span>
            <input
              type="number"
              min={0}
              max={100}
              value={val}
              onChange={(e) => setTargets((t) => ({ ...t, [cat]: Number(e.target.value) }))}
              style={inputStyle}
            />
            <span style={{ fontSize: '0.85rem', color: '#718096' }}>%</span>
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
