import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getNotificationPreferences,
  updateNotificationPreferences,
  type NotificationPreference,
} from '../api/notifications';

const TRIGGER_LABELS: Record<string, string> = {
  missing_day: 'Missing day reminder',
  edit_window_closing: 'Edit window closing',
  blocker_aging: 'Blocker aging',
  team_member_blocked: 'Team member blocked',
  social_reaction: 'Social reactions',
  weekly_report_ready: 'Weekly report ready',
  quarterly_draft_ready: 'Quarterly draft ready',
  team_join_request: 'Team join request',
};

const thStyle: React.CSSProperties = {
  padding: '0.4rem 0.75rem',
  fontWeight: 600,
  fontSize: '0.83rem',
  color: 'var(--text-body)',
  textAlign: 'center',
  borderBottom: '2px solid var(--border)',
};
const tdStyle: React.CSSProperties = {
  padding: '0.5rem 0.75rem',
  fontSize: '0.85rem',
  borderBottom: '1px solid var(--bg-tertiary)',
};

function Toggle({ checked, disabled, onChange }: { checked: boolean; disabled?: boolean; onChange: (v: boolean) => void }) {
  return (
    <label style={{ display: 'inline-flex', alignItems: 'center', cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.4 : 1 }}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)}
        style={{ width: 16, height: 16 }} />
    </label>
  );
}

export const NotificationPreferencesPage = () => {
  const navigate = useNavigate();
  const [prefs, setPrefs] = useState<NotificationPreference[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getNotificationPreferences().then(setPrefs).catch(() => {});
  }, []);

  const update = (triggerType: string, field: 'channel_email' | 'channel_teams', value: boolean) => {
    setPrefs((prev) =>
      prev.map((p) => (p.trigger_type === triggerType ? { ...p, [field]: value } : p))
    );
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      await updateNotificationPreferences(prefs);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setError('Save failed.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto' }}>
      <button
        onClick={() => navigate('/')}
        style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', padding: 0, fontSize: '0.85rem', marginBottom: '1rem', display: 'block' }}
      >
        ← Back
      </button>
      <h2>Notification Preferences</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th style={{ ...thStyle, textAlign: 'left' }}>Trigger</th>
            <th style={thStyle}>In-app</th>
            <th style={thStyle}>Email</th>
            <th style={thStyle}>Teams</th>
          </tr>
        </thead>
        <tbody>
          {prefs.map((p) => (
            <tr key={p.trigger_type}>
              <td style={tdStyle}>{TRIGGER_LABELS[p.trigger_type] ?? p.trigger_type}</td>
              <td style={{ ...tdStyle, textAlign: 'center' }}>
                <Toggle checked disabled onChange={() => {}} />
              </td>
              <td style={{ ...tdStyle, textAlign: 'center' }}>
                <Toggle checked={p.channel_email} onChange={(v) => update(p.trigger_type, 'channel_email', v)} />
              </td>
              <td style={{ ...tdStyle, textAlign: 'center' }}>
                <Toggle checked={p.channel_teams} onChange={(v) => update(p.trigger_type, 'channel_teams', v)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        {error && <span style={{ color: 'var(--error)', fontSize: '0.85rem' }}>{error}</span>}
        <button
          onClick={handleSave}
          disabled={saving}
          style={{ padding: '0.4rem 1.2rem', background: 'var(--primary)', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        {saved && <span style={{ color: 'var(--success)', fontSize: '0.85rem' }}>Saved ✓</span>}
      </div>
    </div>
  );
};
