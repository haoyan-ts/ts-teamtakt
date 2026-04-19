import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { updateUserProfile } from '../api/users';
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

  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name);
      setLocale(user.preferred_locale);
    }
  }, [user]);

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
    </div>
  );
};
