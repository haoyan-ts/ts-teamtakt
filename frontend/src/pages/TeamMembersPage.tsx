import { useEffect, useState } from 'react';
import { getTeamMembers } from '../api/teams';
import type { TeamMember } from '../api/teams';
import { useAuth } from '../hooks/useAuth';

export const TeamMembersPage = () => {
  const { user } = useAuth();
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user?.team?.id) return;
    setLoading(true);
    getTeamMembers(user.team.id)
      .then(setMembers)
      .catch(() => setError('Failed to load team members.'))
      .finally(() => setLoading(false));
  }, [user?.team?.id]);

  if (!user?.team) {
    return <p style={{ color: '#718096' }}>You are not currently assigned to a team.</p>;
  }

  return (
    <div style={{ maxWidth: '700px', margin: '0 auto' }}>
      <h2 style={{ marginBottom: '1rem' }}>{user.team.name}</h2>

      {loading && <p>Loading…</p>}
      {error && <p style={{ color: '#e53e3e' }}>{error}</p>}

      {!loading && !error && (
        <div style={sectionStyle}>
          <h3 style={sectionTitle}>Members</h3>
          {members.length === 0 ? (
            <p style={{ color: '#718096', fontSize: '0.85rem' }}>No active members.</p>
          ) : (
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={th}>Name</th>
                  <th style={th}>Email</th>
                  <th style={th}>Role</th>
                  <th style={th}>Joined</th>
                </tr>
              </thead>
              <tbody>
                {members.map((m) => (
                  <tr key={m.user_id}>
                    <td style={td}>{m.display_name}</td>
                    <td style={{ ...td, maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={m.email}>
                      {m.email}
                    </td>
                    <td style={td}>{m.is_leader ? 'Leader' : 'Member'}</td>
                    <td style={td}>{new Date(m.joined_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
};

const sectionStyle: React.CSSProperties = {
  border: '1px solid #e2e8f0', borderRadius: '8px', padding: '1rem', background: '#fff',
};
const sectionTitle: React.CSSProperties = { margin: '0 0 0.75rem', fontSize: '1rem', fontWeight: 600 };
const tableStyle: React.CSSProperties = { width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' };
const th: React.CSSProperties = {
  textAlign: 'left', padding: '0.3rem 0.5rem', fontWeight: 600, borderBottom: '2px solid #e2e8f0',
};
const td: React.CSSProperties = { padding: '0.4rem 0.5rem', verticalAlign: 'middle' };
