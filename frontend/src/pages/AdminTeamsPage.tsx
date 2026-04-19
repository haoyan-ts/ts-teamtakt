import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  listTeams,
  createTeam,
  deleteTeam,
} from '../api/teams';
import type { TeamSummary } from '../api/teams';

// ---------------------------------------------------------------------------
// Confirmation dialog (same pattern as AdminListsPage)
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
// Create-team modal
// ---------------------------------------------------------------------------

function CreateTeamModal({
  onCreated,
  onClose,
}: {
  onCreated: () => void;
  onClose: () => void;
}) {
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    const trimmed = name.trim();
    if (!trimmed) { setError('Team name cannot be empty.'); return; }
    setSaving(true);
    try {
      await createTeam(trimmed);
      onCreated();
      onClose();
    } catch {
      setError('Failed to create team. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
      <div style={{ background: 'var(--bg)', borderRadius: '8px', padding: '1.5rem', width: '360px' }}>
        <h3 style={{ margin: '0 0 1rem' }}>Create Team</h3>
        <input
          style={{ ...inputStyle, display: 'block', width: '100%', boxSizing: 'border-box', marginBottom: '0.5rem' }}
          placeholder="Team name"
          value={name}
          onChange={(e) => { setName(e.target.value); setError(''); }}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          autoFocus
        />
        {error && <p style={{ color: 'var(--error)', fontSize: '0.8rem', margin: '0 0 0.5rem' }}>{error}</p>}
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '1rem' }}>
          <button onClick={onClose} style={cancelBtn}>Cancel</button>
          <button onClick={submit} disabled={saving} style={primaryBtn}>
            {saving ? 'Creating…' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export const AdminTeamsPage = () => {
  const [teams, setTeams] = useState<TeamSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [dissolveTarget, setDissolveTarget] = useState<TeamSummary | null>(null);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const reload = () => {
    setLoading(true);
    listTeams()
      .then(setTeams)
      .finally(() => setLoading(false));
  };

  useEffect(() => { reload(); }, []);

  const dissolve = async () => {
    if (!dissolveTarget) return;
    setError('');
    try {
      await deleteTeam(dissolveTarget.id);
      setDissolveTarget(null);
      reload();
    } catch (err: unknown) {
      setDissolveTarget(null);
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        setError('Cannot dissolve this team — remove or reassign all members first.');
      } else {
        setError('Failed to dissolve team. Please try again.');
      }
    }
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      {showCreate && (
        <CreateTeamModal onCreated={reload} onClose={() => setShowCreate(false)} />
      )}
      {dissolveTarget && (
        <ConfirmDialog
          message={`Dissolve team "${dissolveTarget.name}"? This cannot be undone.`}
          onConfirm={dissolve}
          onCancel={() => setDissolveTarget(null)}
        />
      )}

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <h2 style={{ margin: 0 }}>Teams (Admin)</h2>
        <button style={primaryBtn} onClick={() => setShowCreate(true)}>Create Team</button>
      </div>

      {error && <p style={{ color: 'var(--error)', marginBottom: '1rem' }}>{error}</p>}

      {loading ? (
        <p>Loading…</p>
      ) : teams.length === 0 ? (
        <p style={{ color: 'var(--text-secondary)' }}>No teams yet. Create one to get started.</p>
      ) : (
        <div style={sectionStyle}>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={th}>Name</th>
                <th style={th}>Members</th>
                <th style={th}>Leaders</th>
                <th style={th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {teams.map((team) => (
                <tr key={team.id}>
                  <td style={td}><strong>{team.name}</strong></td>
                  <td style={td}>{team.member_count}</td>
                  <td style={td}>{team.leaders.join(', ') || '—'}</td>
                  <td style={td}>
                    <div style={{ display: 'flex', gap: '0.4rem' }}>
                      <button style={tinyBtn} onClick={() => navigate(`/admin/teams/${team.id}`)}>
                        Edit
                      </button>
                      <button style={dangerTinyBtn} onClick={() => setDissolveTarget(team)}>
                        Dissolve
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const sectionStyle: React.CSSProperties = {
  border: '1px solid var(--border)', borderRadius: '8px', padding: '1rem', background: 'var(--bg)',
};
const tableStyle: React.CSSProperties = {
  width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem',
};
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
