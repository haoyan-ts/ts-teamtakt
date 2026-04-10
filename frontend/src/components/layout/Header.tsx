import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/useAuth';
import { authApi } from '../../api/auth';
import { NotificationBell } from './NotificationBell';

const LOCALES = ['en', 'ja', 'zh', 'ko'] as const;
const LOCALE_LABELS: Record<string, string> = { en: 'EN', ja: 'JA', zh: 'ZH', ko: 'KO' };

export const Header = ({ onMenuToggle }: { onMenuToggle?: () => void }) => {
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuth();

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
    <header style={{ display: 'flex', alignItems: 'center', padding: '0 1rem', height: '56px', borderBottom: '1px solid #e5e7eb', background: '#fff' }}>
      <button onClick={onMenuToggle} style={{ marginRight: '1rem', background: 'none', border: 'none', fontSize: '1.25rem', cursor: 'pointer' }}>☰</button>
      <div style={{ flex: 1 }} />
      <NotificationBell />
      <select value={i18n.language} onChange={handleLocaleChange} style={{ marginRight: '1rem', padding: '0.25rem 0.5rem', borderRadius: '4px', border: '1px solid #d1d5db' }}>
        {LOCALES.map((loc) => (
          <option key={loc} value={loc}>{LOCALE_LABELS[loc]}</option>
        ))}
      </select>
      {user && (
        <span style={{ marginRight: '1rem', fontWeight: 500 }}>{user.display_name}</span>
      )}
      <button onClick={handleSignOut} style={{ background: 'none', border: '1px solid #d1d5db', padding: '0.25rem 0.75rem', borderRadius: '4px', cursor: 'pointer' }}>
        {t('auth.signOut')}
      </button>
    </header>
  );
};
