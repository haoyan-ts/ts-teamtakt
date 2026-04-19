import { useEffect, useState } from 'react';
import { listUsers, type User } from '../api/users';
import {
  listSharingGrants,
  createSharingGrant,
  revokeSharingGrant,
  type SharingGrant,
} from '../api/sharingGrants';

export const CrossTeamSharingPage = () => {
  const [grants, setGrants] = useState<SharingGrant[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedLeaderId, setSelectedLeaderId] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = async () => {
    try {
      const [g, u] = await Promise.all([listSharingGrants(), listUsers()]);
      setGrants(g);
      setUsers(u);
    } catch {
      setError('Failed to load sharing grants.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { reload(); }, []);

  const activeGrants = grants.filter((g) => g.revoked_at === null);

  const grant = async () => {
    if (!selectedLeaderId) return;
    setSaving(true);
    setError(null);
    try {
      await createSharingGrant({ granted_to_leader_id: selectedLeaderId });
      setSelectedLeaderId('');
      reload();
    } catch {
      setError('Failed to grant access. The leader may already have access.');
    } finally {
      setSaving(false);
    }
  };

  const revoke = async (id: string) => {
    setError(null);
    try {
      await revokeSharingGrant(id);
      reload();
    } catch {
      setError('Failed to revoke access.');
    }
  };

  const leaderName = (id: string) =>
    users.find((u) => u.id === id)?.display_name ?? id;

  const eligibleLeaders = users.filter(
    (u) =>
      u.is_leader &&
      !activeGrants.some((g) => g.granted_to_leader_id === u.id)
  );

  if (loading) return <p>Loading…</p>;

  return (
    <div style={{ maxWidth: '700px', margin: '0 auto' }}>
      <h2 style={{ marginBottom: '0.25rem' }}>Cross-Team Data Sharing</h2>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
        Grant another team leader read access to your team's records.
        Access is <strong>non-transitive</strong> — a grantee cannot re-share with others.
      </p>

      {error && (
        <p style={{ color: 'var(--error)', marginBottom: '1rem' }}>{error}</p>
      )}

      <section style={sectionStyle}>
        <h3 style={sectionTitle}>Active grants ({activeGrants.length})</h3>
        {activeGrants.length === 0 ? (
          <p style={emptyMsg}>No active grants. Your team data is private.</p>
        ) : (
          <ul style={listStyle}>
            {activeGrants.map((g) => (
              <li key={g.id} style={itemStyle}>
                <span style={{ flex: 1 }}>
                  {leaderName(g.granted_to_leader_id)}
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginLeft: '0.5rem' }}>
                    granted {new Date(g.granted_at).toLocaleDateString()}
                  </span>
                </span>
                <button style={dangerBtn} onClick={() => revoke(g.id)}>Revoke</button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section style={sectionStyle}>
        <h3 style={sectionTitle}>Grant access</h3>
        {eligibleLeaders.length === 0 ? (
          <p style={emptyMsg}>All available leaders already have access, or no other leaders exist.</p>
        ) : (
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <select
              style={selectStyle}
              value={selectedLeaderId}
              onChange={(e) => setSelectedLeaderId(e.target.value)}
            >
              <option value="">Select a leader…</option>
              {eligibleLeaders.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.display_name} ({u.email})
                </option>
              ))}
            </select>
            <button
              style={primaryBtn}
              onClick={grant}
              disabled={!selectedLeaderId || saving}
            >
              {saving ? 'Granting…' : 'Grant Access'}
            </button>
          </div>
        )}
      </section>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const sectionStyle: React.CSSProperties = {
  border: '1px solid var(--border)',
  borderRadius: '8px',
  padding: '1rem',
  marginBottom: '1rem',
  background: 'var(--bg)',
};
const sectionTitle: React.CSSProperties = { margin: '0 0 0.75rem', fontSize: '1rem', fontWeight: 600 };
const listStyle: React.CSSProperties = { margin: 0, padding: 0, listStyle: 'none' };
const itemStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '0.5rem',
  padding: '0.35rem 0',
  borderBottom: '1px solid var(--border-subtle)',
};
const emptyMsg: React.CSSProperties = { margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' };
const selectStyle: React.CSSProperties = {
  flex: 1,
  border: '1px solid var(--border)',
  borderRadius: '4px',
  padding: '0.35rem 0.5rem',
  background: 'var(--bg)',
  color: 'var(--text-h)',
};
const primaryBtn: React.CSSProperties = {
  padding: '0.35rem 0.75rem',
  background: 'var(--primary)',
  color: '#fff',
  border: 'none',
  borderRadius: '4px',
  cursor: 'pointer',
  fontWeight: 500,
};
const dangerBtn: React.CSSProperties = {
  padding: '0.2rem 0.5rem',
  background: 'transparent',
  border: '1px solid var(--error)',
  borderRadius: '4px',
  cursor: 'pointer',
  fontSize: '0.75rem',
  color: 'var(--error)',
};
