import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getCurrentUser, disconnectMs365, ms365Reconnect, updateUserProfile, syncAvatarFromMs365, connectGithub, unlinkGithub } from '../api/users';
import { useAuthStore } from '../stores/authStore';

const LOCALES = ['en', 'ja', 'zh', 'ko'] as const;
const LOCALE_LABELS: Record<string, string> = { en: 'English', ja: '日本語', zh: '中文', ko: '한국어' };

export const ProfileSettingsPage = () => {
  const { t } = useTranslation();
  const { user, setUser } = useAuthStore();

  const [displayName, setDisplayName] = useState('');
  const [locale, setLocale] = useState('en');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [ms365Disconnecting, setMs365Disconnecting] = useState(false);
  const [avatarSyncing, setAvatarSyncing] = useState(false);
  const [avatarSyncError, setAvatarSyncError] = useState('');
  const [githubUnlinking, setGithubUnlinking] = useState(false);

  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name);
      setLocale(user.preferred_locale);
    }
  }, [user]);

  // Refresh user data when returning from MS365 OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('ms365') === 'connected') {
      getCurrentUser().then(setUser).catch(() => undefined);
      window.history.replaceState({}, '', window.location.pathname);
    }
    if (params.get('github') === 'connected') {
      getCurrentUser().then(setUser).catch(() => undefined);
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [setUser]);

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSaved(false);
    try {
      const updated = await updateUserProfile({
        display_name: displayName.trim() || undefined,
        preferred_locale: locale,
      });
      setUser(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      setError(t('profile.saveError'));
    } finally {
      setSaving(false);
    }
  };

  const handleMs365Reconnect = async () => {
    const redirectUrl = await ms365Reconnect();
    window.location.href = redirectUrl;
  };

  const handleMs365Disconnect = async () => {
    setMs365Disconnecting(true);
    try {
      await disconnectMs365();
      if (user) setUser({ ...user, ms365_connected: false });
    } finally {
      setMs365Disconnecting(false);
    }
  };

  const handleSyncAvatar = async () => {
    setAvatarSyncing(true);
    setAvatarSyncError('');
    try {
      const { avatar_url } = await syncAvatarFromMs365();
      if (user) setUser({ ...user, avatar_url });
    } catch (err: unknown) {
      const status =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { status?: number } }).response?.status
          : undefined;
      setAvatarSyncError(
        status === 422
          ? t('profile.avatarSyncReconnect')
          : t('profile.avatarSyncError'),
      );
    } finally {
      setAvatarSyncing(false);
    }
  };

  const handleGithubConnect = async () => {
    const redirectUrl = await connectGithub();
    window.location.href = redirectUrl;
  };

  const handleGithubUnlink = async () => {
    setGithubUnlinking(true);
    try {
      await unlinkGithub();
      if (user) setUser({ ...user, github_linked: false, github_login: null });
    } finally {
      setGithubUnlinking(false);
    }
  };

  const labelStyle: React.CSSProperties = {
    display: 'block',
    marginBottom: '0.35rem',
    fontWeight: 600,
    fontSize: '0.85rem',
    color: 'var(--text-body)',
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    maxWidth: '360px',
    padding: '0.5rem 0.75rem',
    fontSize: '0.9rem',
    border: '1px solid var(--border)',
    borderRadius: '6px',
    background: 'var(--bg-secondary)',
    color: 'var(--text-body)',
  };

  return (
    <div style={{ padding: '2rem', maxWidth: '600px' }}>
      <h1 style={{ marginTop: 0, marginBottom: '1.5rem', fontSize: '1.25rem' }}>
        {t('profile.title')}
      </h1>

      {/* Avatar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
        {user?.avatar_url ? (
          <img
            src={user.avatar_url}
            alt={user.display_name}
            style={{ width: 64, height: 64, borderRadius: '50%', objectFit: 'cover', border: '2px solid var(--border)' }}
          />
        ) : (
          <div style={{
            width: 64, height: 64, borderRadius: '50%',
            background: 'var(--bg-secondary)', border: '2px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '1.75rem', color: 'var(--text-muted)',
          }}>
            {user?.display_name?.[0]?.toUpperCase() ?? '?'}
          </div>
        )}
        <div>
          {user?.ms365_connected && (
            <button
              onClick={handleSyncAvatar}
              disabled={avatarSyncing}
              style={{
                padding: '0.35rem 0.9rem',
                fontSize: '0.82rem',
                background: 'transparent',
                border: '1px solid var(--border)',
                borderRadius: '6px',
                cursor: avatarSyncing ? 'not-allowed' : 'pointer',
                opacity: avatarSyncing ? 0.6 : 1,
                color: 'var(--text-body)',
              }}
            >
              {avatarSyncing ? t('profile.avatarSyncing') : t('profile.avatarSync')}
            </button>
          )}
          {avatarSyncError && (
            <div style={{ marginTop: '0.35rem', fontSize: '0.8rem', color: 'var(--error)' }}>
              {avatarSyncError}
            </div>
          )}
        </div>
      </div>

      <div style={{ marginBottom: '0.5rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
        {t('profile.email')}: {user?.email ?? '—'}
      </div>

      <div style={{ marginBottom: '1.25rem' }}>
        <label htmlFor="display-name" style={labelStyle}>{t('profile.displayName')}</label>
        <input
          id="display-name"
          type="text"
          value={displayName}
          maxLength={100}
          onChange={(e) => setDisplayName(e.target.value)}
          style={inputStyle}
        />
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <label htmlFor="preferred-locale" style={labelStyle}>{t('profile.preferredLocale')}</label>
        <select
          id="preferred-locale"
          value={locale}
          onChange={(e) => setLocale(e.target.value)}
          style={inputStyle}
        >
          {LOCALES.map((l) => (
            <option key={l} value={l}>{LOCALE_LABELS[l]}</option>
          ))}
        </select>
      </div>

      {error && (
        <div style={{ marginBottom: '1rem', color: 'var(--error)', fontSize: '0.85rem' }}>
          {error}
        </div>
      )}

      <button
        onClick={handleSave}
        disabled={saving || !displayName.trim()}
        style={{
          padding: '0.55rem 1.25rem',
          background: 'var(--primary)',
          color: '#fff',
          border: 'none',
          borderRadius: '6px',
          fontWeight: 600,
          cursor: saving || !displayName.trim() ? 'not-allowed' : 'pointer',
          opacity: saving || !displayName.trim() ? 0.6 : 1,
        }}
      >
        {saving ? t('profile.saving') : t('profile.save')}
      </button>

      {saved && (
        <span style={{ marginLeft: '1rem', color: 'var(--success)', fontSize: '0.85rem' }}>
          {t('profile.saved')}
        </span>
      )}

      {/* ── Permissions ─────────────────────────────────────────────────── */}
      <hr style={{ margin: '2rem 0', border: 'none', borderTop: '1px solid var(--border)' }} />
      <h2 style={{ marginTop: 0, marginBottom: '1rem', fontSize: '1rem' }}>
        {t('profile.permissions.title')}
      </h2>

      {/* MS365 */}
      <div style={{ marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.35rem' }}>
          <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
            {t('profile.permissions.ms365.label')}
          </span>
          {user?.ms365_connected ? (
            <span style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              padding: '0.15rem 0.55rem',
              borderRadius: '99px',
              background: 'var(--success-bg, #d1fae5)',
              color: 'var(--success, #065f46)',
            }}>
              {t('profile.permissions.connected')}
            </span>
          ) : (
            <span style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              padding: '0.15rem 0.55rem',
              borderRadius: '99px',
              background: 'var(--warning-bg, #fef3c7)',
              color: 'var(--warning, #92400e)',
            }}>
              {t('profile.permissions.notConnected')}
            </span>
          )}
        </div>
        <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '0.6rem' }}>
          {t('profile.permissions.ms365.description')}
        </div>
        {user?.ms365_connected ? (
          <button
            onClick={handleMs365Disconnect}
            disabled={ms365Disconnecting}
            style={{
              padding: '0.4rem 1rem',
              fontSize: '0.85rem',
              background: 'transparent',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              cursor: ms365Disconnecting ? 'not-allowed' : 'pointer',
              opacity: ms365Disconnecting ? 0.6 : 1,
              color: 'var(--text-body)',
            }}
          >
            {ms365Disconnecting ? t('profile.permissions.disconnecting') : t('profile.permissions.disconnect')}
          </button>
        ) : (
          <button
            onClick={handleMs365Reconnect}
            style={{
              padding: '0.4rem 1rem',
              fontSize: '0.85rem',
              background: 'var(--primary)',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              color: '#fff',
              fontWeight: 600,
            }}
          >
            {t('profile.permissions.reconnect')}
          </button>
        )}
      </div>

      {/* GitHub */}
      <div style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.35rem' }}>
          <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
            {t('profile.permissions.github.label')}
          </span>
          {user?.github_linked ? (
            <span style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              padding: '0.15rem 0.55rem',
              borderRadius: '99px',
              background: 'var(--success-bg, #d1fae5)',
              color: 'var(--success, #065f46)',
            }}>
              {t('profile.permissions.connected')}
            </span>
          ) : (
            <span style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              padding: '0.15rem 0.55rem',
              borderRadius: '99px',
              background: 'var(--warning-bg, #fef3c7)',
              color: 'var(--warning, #92400e)',
            }}>
              {t('profile.permissions.notConnected')}
            </span>
          )}
        </div>
        {user?.github_linked && user?.github_login && (
          <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
            {t('profile.permissions.github.connectedAs', { login: user.github_login })}
          </div>
        )}
        <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '0.6rem' }}>
          {t('profile.permissions.github.description')}
        </div>
        {user?.github_linked ? (
          <button
            onClick={handleGithubUnlink}
            disabled={githubUnlinking}
            style={{
              padding: '0.4rem 1rem',
              fontSize: '0.85rem',
              background: 'transparent',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              cursor: githubUnlinking ? 'not-allowed' : 'pointer',
              opacity: githubUnlinking ? 0.6 : 1,
              color: 'var(--text-body)',
            }}
          >
            {githubUnlinking ? t('profile.permissions.disconnecting') : t('profile.permissions.disconnect')}
          </button>
        ) : (
          <button
            onClick={handleGithubConnect}
            style={{
              padding: '0.4rem 1rem',
              fontSize: '0.85rem',
              background: 'var(--primary)',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              color: '#fff',
              fontWeight: 600,
            }}
          >
            {t('profile.permissions.github.connect')}
          </button>
        )}
      </div>
    </div>
  );
};
