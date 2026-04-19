import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { getTeamSettings, updateTeamSettings, type TeamSettings } from '../api/teams';

export const TeamBalanceSettingsPage = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const teamId = user?.team?.id;

  const [settings, setSettings] = useState<TeamSettings | null>(null);
  const [targets, setTargets] = useState<Record<string, number>>({});
  const [initialTargets, setInitialTargets] = useState<Record<string, number>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!teamId) return;
    getTeamSettings(teamId).then((s) => {
      setSettings(s);
      setTargets({ ...s.balance_targets });
      setInitialTargets({ ...s.balance_targets });
    });
  }, [teamId]);

  const total = Object.values(targets).reduce((a, b) => a + (b || 0), 0);

  const handleSave = async () => {
    if (!teamId) return;
    setSaving(true);
    setError('');
    try {
      await updateTeamSettings(teamId, { balance_targets: targets });
      setInitialTargets({ ...targets });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setError('Save failed.');
    } finally {
      setSaving(false);
    }
  };

  const isDirty = JSON.stringify(targets) !== JSON.stringify(initialTargets);

  const handleBack = () => {
    if (isDirty && !window.confirm('You have unsaved changes. Leave anyway?')) return;
    navigate('/team');
  };

  if (!teamId) return <div>Not assigned to a team.</div>;
  if (!settings) return <div>Loading…</div>;

  const inputStyle: React.CSSProperties = {
    width: '80px',
    border: '1px solid var(--border-strong)',
    borderRadius: 4,
    padding: '2px 6px',
    fontSize: '0.9rem',
    background: 'var(--bg)',
    color: 'var(--text-h)',
  };

  return (
    <div style={{ maxWidth: '500px', margin: '0 auto' }}>
      <h2>Balance Targets</h2>
      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
        Set target percentage for each category. Total: <strong style={{ color: total === 100 ? 'var(--success)' : 'var(--error)' }}>{total}%</strong>
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
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>%</span>
          </div>
        ))}
      </div>
      {error && <p style={{ color: 'var(--error)', fontSize: '0.85rem' }}>{error}</p>}
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <button
          onClick={handleSave}
          disabled={saving}
          style={{ padding: '0.4rem 1.2rem', background: 'var(--primary)', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        {saved && <span style={{ color: 'var(--success)', fontSize: '0.85rem', alignSelf: 'center' }}>Saved ✓</span>}
        <button onClick={handleBack} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.85rem', alignSelf: 'center' }}>← Back</button>
      </div>
    </div>
  );
};
