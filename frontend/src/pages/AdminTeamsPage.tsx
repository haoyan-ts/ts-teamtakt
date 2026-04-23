import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  listTeams,
  createTeam,
  deleteTeam,
} from '../api/teams';
import type { TeamSummary } from '../api/teams';
import { ConfirmDialog } from '../components/admin/ConfirmDialog';
import {
  sectionStyle,
  tableStyle,
  th,
  tdMiddle,
  inputStyle,
  primaryBtn,
  tinyBtn,
  dangerTinyBtn,
  cancelBtn,
  dangerBtn,
} from '../components/admin/adminStyles';

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
  const { t } = useTranslation();
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    const trimmed = name.trim();
    if (!trimmed) { setError(t('adminTeams.createModal.emptyError')); return; }
    setSaving(true);
    try {
      await createTeam(trimmed);
      onCreated();
      onClose();
    } catch {
      setError(t('adminTeams.createModal.createError'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
      <div style={{ background: 'var(--bg)', borderRadius: '8px', padding: '1.5rem', width: '360px' }}>
        <h3 style={{ margin: '0 0 1rem' }}>{t('adminTeams.createModal.title')}</h3>
        <input
          style={{ ...inputStyle, display: 'block', width: '100%', boxSizing: 'border-box', marginBottom: '0.5rem' }}
          placeholder={t('adminTeams.createModal.namePlaceholder')}
          value={name}
          onChange={(e) => { setName(e.target.value); setError(''); }}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          autoFocus
        />
        {error && <p style={{ color: 'var(--error)', fontSize: '0.8rem', margin: '0 0 0.5rem' }}>{error}</p>}
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '1rem' }}>
          <button onClick={onClose} style={cancelBtn}>{t('adminLists.confirm.cancel')}</button>
          <button onClick={submit} disabled={saving} style={primaryBtn}>
            {saving ? t('adminTeams.createModal.creating') : t('adminTeams.createModal.create')}
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
  const { t } = useTranslation();
  const [teams, setTeams] = useState<TeamSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [dissolveTarget, setDissolveTarget] = useState<TeamSummary | null>(null);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const reload = useCallback(() => {
    setLoading(true);
    listTeams()
      .then(setTeams)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    listTeams()
      .then(setTeams)
      .finally(() => setLoading(false));
  }, []);

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
        setError(t('adminTeams.dissolveConflict'));
      } else {
        setError(t('adminTeams.dissolveError'));
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
          message={t('adminTeams.dissolveConfirm', { name: dissolveTarget.name })}
          onConfirm={dissolve}
          onCancel={() => setDissolveTarget(null)}
        />
      )}

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <h2 style={{ margin: 0 }}>{t('adminTeams.pageTitle')}</h2>
        <button style={primaryBtn} onClick={() => setShowCreate(true)}>{t('adminTeams.createBtn')}</button>
      </div>

      {error && <p style={{ color: 'var(--error)', marginBottom: '1rem' }}>{error}</p>}

      {loading ? (
        <p>{t('adminLists.loading')}</p>
      ) : teams.length === 0 ? (
        <p style={{ color: 'var(--text-secondary)' }}>{t('adminTeams.empty')}</p>
      ) : (
        <div style={sectionStyle}>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={th}>{t('adminTeams.col.name')}</th>
                <th style={th}>{t('adminTeams.col.members')}</th>
                <th style={th}>{t('adminTeams.col.leaders')}</th>
                <th style={th}>{t('adminTeams.col.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {teams.map((team) => (
                <tr key={team.id}>
                  <td style={tdMiddle}><strong>{team.name}</strong></td>
                  <td style={tdMiddle}>{team.member_count}</td>
                  <td style={tdMiddle}>{team.leaders.join(', ') || '—'}</td>
                  <td style={tdMiddle}>
                    <div style={{ display: 'flex', gap: '0.4rem' }}>
                      <button style={tinyBtn} onClick={() => navigate(`/admin/teams/${team.id}`)}>
                        {t('adminTeams.col.edit')}
                      </button>
                      <button style={dangerTinyBtn} onClick={() => setDissolveTarget(team)}>
                        {t('adminTeams.col.dissolve')}
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

// Re-export for any downstream imports
export { cancelBtn, dangerBtn };
