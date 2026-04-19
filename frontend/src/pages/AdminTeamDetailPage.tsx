import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  getTeamMembers,
  renameTeam,
  assignMember,
  removeMember,
} from '../api/teams';
import type { TeamMember } from '../api/teams';
import { listUsers, updateUserRoles } from '../api/users';
import type { User } from '../api/users';

// ---------------------------------------------------------------------------
// Confirmation dialog
// ---------------------------------------------------------------------------

function ConfirmDialog({
  message,
  onConfirm,
  onCancel,
}: {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
      <div style={{ background: 'var(--bg)', borderRadius: '8px', padding: '1.5rem', maxWidth: '400px' }}>
        <p style={{ margin: '0 0 1rem' }}>{message}</p>
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
          <button onClick={onCancel} style={cancelBtn}>Cancel</button>
          <button onClick={onConfirm} style={dangerBtn}>Confirm</button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rename section
// ---------------------------------------------------------------------------

function RenameSection({ teamId, currentName, onRenamed }: { teamId: string; currentName: string; onRenamed: (name: string) => void }) {
  const [name, setName] = useState(currentName);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  // Sync if parent name changes (e.g. after first load)
  useEffect(() => { setName(currentName); }, [currentName]);

  const save = async () => {
    const trimmed = name.trim();
    if (!trimmed) { setError('Name cannot be empty.'); return; }
    setSaving(true);
    setError('');
    setSaved(false);
    try {
      const updated = await renameTeam(teamId, trimmed);
      onRenamed(updated.name);
      setSaved(true);
    } catch {
      setError('Failed to rename team. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section style={sectionStyle}>
      <h3 style={sectionTitle}>Rename Team</h3>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <input
          style={{ ...inputStyle, flex: 1 }}
          value={name}
          onChange={(e) => { setName(e.target.value); setSaved(false); setError(''); }}
          onKeyDown={(e) => e.key === 'Enter' && save()}
        />
        <button style={primaryBtn} onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
      {error && <p style={{ color: 'var(--error)', fontSize: '0.8rem', marginTop: '0.4rem' }}>{error}</p>}
      {saved && <p style={{ color: 'var(--success)', fontSize: '0.8rem', marginTop: '0.4rem' }}>Saved.</p>}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Members section
// ---------------------------------------------------------------------------

function MembersSection({ teamId }: { teamId: string }) {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [removeTarget, setRemoveTarget] = useState<TeamMember | null>(null);
  const [error, setError] = useState('');

  const reload = useCallback(() => {
    setLoading(true);
    getTeamMembers(teamId)
      .then(setMembers)
      .finally(() => setLoading(false));
  }, [teamId]);

  useEffect(() => {
    getTeamMembers(teamId)
      .then(setMembers)
      .finally(() => setLoading(false));
  }, [teamId]);

  const toggleLeader = async (member: TeamMember) => {
    setError('');
    try {
      await updateUserRoles(member.user_id, { is_leader: !member.is_leader });
      reload();
    } catch {
      setError('Failed to update leader status.');
    }
  };

  const confirmRemove = async () => {
    if (!removeTarget) return;
    setError('');
    try {
      await removeMember(teamId, removeTarget.user_id);
      setRemoveTarget(null);
      reload();
    } catch {
      setRemoveTarget(null);
      setError('Failed to remove member. Please try again.');
    }
  };

  if (loading) return <section style={sectionStyle}><p>Loading members…</p></section>;

  return (
    <section style={sectionStyle}>
      {removeTarget && (
        <ConfirmDialog
          message={`Remove ${removeTarget.display_name} from this team?`}
          onConfirm={confirmRemove}
          onCancel={() => setRemoveTarget(null)}
        />
      )}
      <h3 style={sectionTitle}>Members</h3>
      {error && <p style={{ color: 'var(--error)', fontSize: '0.8rem', marginBottom: '0.5rem' }}>{error}</p>}
      {members.length === 0 ? (
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>No active members.</p>
      ) : (
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={th}>Name</th>
              <th style={th}>Email</th>
              <th style={th}>Leader</th>
              <th style={th}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.user_id}>
                <td style={td}>{m.display_name}</td>
                <td title={m.email} style={{ ...td, maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.email}</td>
                <td style={td}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={m.is_leader}
                      onChange={() => toggleLeader(m)}
                    />
                    {m.is_leader ? 'Yes' : 'No'}
                  </label>
                </td>
                <td style={td}>
                  <button style={dangerTinyBtn} onClick={() => setRemoveTarget(m)}>
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Assign user section
// ---------------------------------------------------------------------------

function AssignUserSection({ teamId, onAssigned }: { teamId: string; onAssigned: () => void }) {
  const [allUsers, setAllUsers] = useState<User[]>([]);
  const [members, setMembers] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const reload = useCallback(async () => {
    const [users, currentMembers] = await Promise.all([
      listUsers(),
      getTeamMembers(teamId),
    ]);
    setAllUsers(users);
    setMembers(new Set(currentMembers.map((m) => m.user_id)));
  }, [teamId]);

  useEffect(() => {
    Promise.all([
      listUsers(),
      getTeamMembers(teamId),
    ]).then(([users, currentMembers]) => {
      setAllUsers(users);
      setMembers(new Set(currentMembers.map((m) => m.user_id)));
    });
  }, [teamId]);

  const assign = async () => {
    if (!selected) return;
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      await assignMember(teamId, selected);
      setSelected('');
      setSuccess('User assigned successfully.');
      onAssigned();
      reload();
    } catch {
      setError('Failed to assign user. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section style={sectionStyle}>
      <h3 style={sectionTitle}>Assign User to Team</h3>
      <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
        Assigning a user who already belongs to another team will close their previous membership.
      </p>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <select
          style={{ ...inputStyle, flex: 1 }}
          value={selected}
          onChange={(e) => { setSelected(e.target.value); setSuccess(''); setError(''); }}
        >
          <option value="">— select a user —</option>
          {allUsers.map((u) => (
            <option key={u.id} value={u.id} disabled={members.has(u.id)}>
              {u.display_name} ({u.email}){members.has(u.id) ? ' — already a member' : ''}
            </option>
          ))}
        </select>
        <button style={primaryBtn} onClick={assign} disabled={!selected || saving}>
          {saving ? 'Assigning…' : 'Assign'}
        </button>
      </div>
      {error && <p style={{ color: 'var(--error)', fontSize: '0.8rem', marginTop: '0.4rem' }}>{error}</p>}
      {success && <p style={{ color: 'var(--success)', fontSize: '0.8rem', marginTop: '0.4rem' }}>{success}</p>}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export const AdminTeamDetailPage = () => {
  const { teamId } = useParams<{ teamId: string }>();
  const navigate = useNavigate();
  const [teamName, setTeamName] = useState('');
  const [membersKey, setMembersKey] = useState(0); // bump to trigger MembersSection reload

  // We don't have a single-team GET endpoint, so resolve the name from the members section
  // or simply let the rename section show an empty field initially.
  // Instead, we'll retrieve the name from the teams list if available.
  useEffect(() => {
    // Fetch team name on mount via members listing (team name comes from the list endpoint).
    // Since we only have listTeams() (admin) and no GET /teams/:id, we fetch the list.
    import('../api/teams').then(({ listTeams }) => {
      listTeams().then((teams) => {
        const found = teams.find((t) => t.id === teamId);
        if (found) setTeamName(found.name);
      });
    });
  }, [teamId]);

  if (!teamId) return <p>Invalid team ID.</p>;

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <button
        style={{ ...tinyBtn, marginBottom: '1rem' }}
        onClick={() => navigate('/admin/teams')}
      >
        ← Back to Teams
      </button>
      <h2 style={{ marginBottom: '1rem' }}>
        Edit Team{teamName ? `: ${teamName}` : ''}
      </h2>

      <RenameSection
        teamId={teamId}
        currentName={teamName}
        onRenamed={(name) => setTeamName(name)}
      />
      <MembersSection key={membersKey} teamId={teamId} />
      <AssignUserSection teamId={teamId} onAssigned={() => setMembersKey((k) => k + 1)} />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const sectionStyle: React.CSSProperties = {
  border: '1px solid var(--border)', borderRadius: '8px', padding: '1rem',
  marginBottom: '1rem', background: 'var(--bg)',
};
const sectionTitle: React.CSSProperties = { margin: '0 0 0.75rem', fontSize: '1rem', fontWeight: 600 };
const tableStyle: React.CSSProperties = { width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' };
const th: React.CSSProperties = {
  textAlign: 'left', padding: '0.3rem 0.5rem', fontWeight: 600, borderBottom: '2px solid var(--border)',
};
const td: React.CSSProperties = { padding: '0.4rem 0.5rem', verticalAlign: 'middle' };
const inputStyle: React.CSSProperties = {
  border: '1px solid var(--border)', borderRadius: '4px', padding: '0.3rem 0.5rem',
  background: 'var(--bg)', color: 'var(--text-h)',
};
const primaryBtn: React.CSSProperties = {
  padding: '0.35rem 0.75rem', background: 'var(--primary)', color: '#fff', border: 'none',
  borderRadius: '4px', cursor: 'pointer', fontWeight: 500,
};
const tinyBtn: React.CSSProperties = {
  padding: '0.2rem 0.5rem', background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
  borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem',
};
const dangerTinyBtn: React.CSSProperties = {
  ...tinyBtn, background: 'var(--error-bg)', border: '1px solid var(--error-bg)', color: 'var(--error)',
};
const cancelBtn: React.CSSProperties = { ...tinyBtn, padding: '0.4rem 1rem' };
const dangerBtn: React.CSSProperties = {
  ...primaryBtn, background: 'var(--error)', padding: '0.4rem 1rem',
};
