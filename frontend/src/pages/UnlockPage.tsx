import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { getTeamMembers, type TeamMember } from '../api/teams';
import {
  listUnlockGrants,
  createUnlockGrant,
  revokeUnlockGrant,
  type UnlockGrant,
} from '../api/reports';

export const UnlockPage = () => {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const teamId = user?.team?.id ?? null;

  const [members, setMembers] = useState<TeamMember[]>([]);
  const [grants, setGrants] = useState<UnlockGrant[]>([]);
  const [loadingMembers, setLoadingMembers] = useState(true);
  const [loadingGrants, setLoadingGrants] = useState(true);

  // Per-member grant date inputs
  const [dateInputs, setDateInputs] = useState<Record<string, string>>({});
  const [creating, setCreating] = useState<Record<string, boolean>>({});
  const [revoking, setRevoking] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!teamId) return;
    setLoadingMembers(true);
    getTeamMembers(teamId)
      .then(setMembers)
      .finally(() => setLoadingMembers(false));
    refreshGrants();
  }, [teamId]);

  const refreshGrants = async () => {
    setLoadingGrants(true);
    try {
      const gs = await listUnlockGrants();
      setGrants(gs);
    } finally {
      setLoadingGrants(false);
    }
  };

  const handleGrant = async (userId: string) => {
    const date = dateInputs[userId];
    if (!date) {
      setErrors((e) => ({ ...e, [userId]: 'Please select a date.' }));
      return;
    }
    setCreating((c) => ({ ...c, [userId]: true }));
    setErrors((e) => ({ ...e, [userId]: '' }));
    try {
      await createUnlockGrant(userId, date);
      await refreshGrants();
      setDateInputs((d) => ({ ...d, [userId]: '' }));
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setErrors((e) => ({ ...e, [userId]: detail ?? 'Failed to create grant.' }));
    } finally {
      setCreating((c) => ({ ...c, [userId]: false }));
    }
  };

  const handleRevoke = async (grantId: string) => {
    setRevoking((r) => ({ ...r, [grantId]: true }));
    try {
      await revokeUnlockGrant(grantId);
      await refreshGrants();
    } finally {
      setRevoking((r) => ({ ...r, [grantId]: false }));
    }
  };

  if (!teamId) {
    return <p style={{ color: 'var(--error)' }}>You are not assigned to a team.</p>;
  }

  const card: React.CSSProperties = { border: '1px solid var(--border)', borderRadius: 8, padding: '1rem', background: 'var(--bg)', marginBottom: '0.75rem' };
  const inputStyle: React.CSSProperties = { border: '1px solid var(--border-strong)', borderRadius: 4, padding: '3px 8px', fontSize: '0.85rem', background: 'var(--bg)', color: 'var(--text-h)' };
  const btn = (color: string, disabled: boolean): React.CSSProperties => ({
    padding: '0.3rem 0.75rem', background: disabled ? 'var(--text-muted)' : color, color: '#fff',
    border: 'none', borderRadius: 5, cursor: disabled ? 'not-allowed' : 'pointer', fontSize: '0.82rem',
  });

  return (
    <div style={{ maxWidth: 700, margin: '0 auto' }}>
      <button
        onClick={() => navigate('/team')}
        style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', padding: 0, fontSize: '0.85rem', marginBottom: '1rem', display: 'block' }}
      >
        ← Back
      </button>
      <h2 style={{ marginBottom: '0.25rem' }}>Unlock Edit Window</h2>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
        Grant a member access to edit a specific past date after the edit window has closed.
        Grants are single-use per (member, date). Revoke at any time.
      </p>

      {/* Active grants */}
      <section style={{ marginBottom: '2rem' }}>
        <h3 style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>Active Unlock Grants</h3>
        {loadingGrants ? (
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Loading…</p>
        ) : grants.length === 0 ? (
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No active grants.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border)' }}>
                <th style={{ textAlign: 'left', padding: '4px 8px' }}>Member</th>
                <th style={{ textAlign: 'left', padding: '4px 8px' }}>Date</th>
                <th style={{ textAlign: 'left', padding: '4px 8px' }}>Granted At</th>
                <th style={{ padding: '4px 8px' }}></th>
              </tr>
            </thead>
            <tbody>
              {grants.map((g) => {
                const member = members.find((m) => m.user_id === g.user_id);
                const isRevoking = revoking[g.id] ?? false;
                return (
                  <tr key={g.id} style={{ borderBottom: '1px solid var(--bg-tertiary)' }}>
                    <td style={{ padding: '5px 8px' }}>{member?.display_name ?? g.user_id.slice(0, 8)}</td>
                    <td style={{ padding: '5px 8px' }}>{g.record_date}</td>
                    <td style={{ padding: '5px 8px', color: 'var(--text-secondary)' }}>{new Date(g.granted_at).toLocaleString()}</td>
                    <td style={{ padding: '5px 8px' }}>
                      <button onClick={() => handleRevoke(g.id)} disabled={isRevoking} style={btn('var(--error)', isRevoking)}>
                        {isRevoking ? 'Revoking…' : 'Revoke'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      {/* Grant form per member */}
      <section>
        <h3 style={{ fontSize: '0.95rem', marginBottom: '0.5rem' }}>Grant Unlock by Member</h3>
        {loadingMembers ? (
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Loading members…</p>
        ) : (
          members.map((m) => {
            const isCreating = creating[m.user_id] ?? false;
            const errMsg = errors[m.user_id] ?? '';
            return (
              <div key={m.user_id} style={card}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{m.display_name}</span>
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                    <input
                      type="date"
                      value={dateInputs[m.user_id] ?? ''}
                      onChange={(e) => setDateInputs((d) => ({ ...d, [m.user_id]: e.target.value }))}
                      style={inputStyle}
                    />
                    <button onClick={() => handleGrant(m.user_id)} disabled={isCreating} style={btn('var(--primary)', isCreating)}>
                      {isCreating ? 'Granting…' : 'Grant Unlock'}
                    </button>
                  </div>
                </div>
                {errMsg && <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: 'var(--error)' }}>{errMsg}</p>}
              </div>
            );
          })
        )}
      </section>
    </div>
  );
};
