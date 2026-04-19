import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/useAuth';
import { authApi } from '../../api/auth';
import { NotificationBell } from './NotificationBell';
import { useTheme } from '../../context/useTheme';

const LOCALES = ['en', 'ja', 'zh', 'ko'] as const;
const LOCALE_LABELS: Record<string, string> = { en: 'EN', ja: 'JA', zh: 'ZH', ko: 'KO' };

export const Header = ({ onMenuToggle }: { onMenuToggle?: () => void }) => {
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const handleLocaleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    i18n.changeLanguage(e.target.value);
    localStorage.setItem('locale', e.target.value);
  };

  const handleSignOut = async () => {
    await authApi.logout().catch(() => {});
    logout();
    window.location.href = '/login';
  };

  return (
    <header style={{ display: 'flex', alignItems: 'center', padding: '0 1rem', height: '56px', borderBottom: '1px solid var(--border-subtle)', background: 'var(--bg)' }}>
      <button onClick={onMenuToggle} style={{ marginRight: '1rem', background: 'none', border: 'none', fontSize: '1.25rem', cursor: 'pointer' }}>☰</button>
      <div style={{ flex: 1 }} />
      <button
        onClick={toggleTheme}
        style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.1rem', marginRight: '0.25rem', padding: '2px 6px' }}
        aria-label="Toggle theme"
      >
        {theme === 'dark' ? '☀️' : '🌙'}
      </button>
      <NotificationBell />
      <select value={i18n.language} onChange={handleLocaleChange} style={{ marginRight: '1rem', padding: '0.25rem 0.5rem', borderRadius: '4px', border: '1px solid var(--border-strong)', background: 'var(--bg)', color: 'var(--text-h)' }}>
        {LOCALES.map((loc) => (
          <option key={loc} value={loc}>{LOCALE_LABELS[loc]}</option>
        ))}
      </select>
      {user && (
        <span style={{ marginRight: '1rem', fontWeight: 500 }}>{user.display_name}</span>
      )}
      <button onClick={handleSignOut} style={{ background: 'none', border: '1px solid var(--border-strong)', padding: '0.25rem 0.75rem', borderRadius: '4px', cursor: 'pointer', color: 'var(--text-h)' }}>
        {t('auth.signOut')}
      </button>
    </header>
  );
};
