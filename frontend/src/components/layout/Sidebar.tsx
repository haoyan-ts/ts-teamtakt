import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/useAuth';

export const Sidebar = ({ isOpen }: { isOpen: boolean }) => {
  const { t } = useTranslation();
  const { user } = useAuth();

  const navLinkStyle = ({ isActive }: { isActive: boolean }) => ({
    display: 'block',
    padding: '0.75rem 1.5rem',
    color: isActive ? '#2563eb' : '#374151',
    textDecoration: 'none',
    fontWeight: isActive ? 600 : 400,
    background: isActive ? '#eff6ff' : 'transparent',
    borderLeft: isActive ? '3px solid #2563eb' : '3px solid transparent',
  });

  return (
    <nav style={{
      width: isOpen ? '240px' : '0',
      overflow: 'hidden',
      transition: 'width 0.2s',
      background: '#f9fafb',
      borderRight: '1px solid #e5e7eb',
      flexShrink: 0,
      height: '100%',
    }}>
      <div style={{ padding: '1rem 1.5rem', fontWeight: 700, fontSize: '1.125rem', borderBottom: '1px solid #e5e7eb' }}>
        TeamTakt
      </div>
      <NavLink to="/" end style={navLinkStyle}>{t('nav.dashboard')}</NavLink>
      <NavLink to="/feed" style={navLinkStyle}>{t('nav.feed')}</NavLink>
      <NavLink to="/reports/quarterly" style={navLinkStyle}>{t('nav.quarterlyReport')}</NavLink>
      {user?.is_leader && (
        <NavLink to="/team" style={navLinkStyle}>{t('nav.team')}</NavLink>
      )}
      {user?.is_leader && (
        <NavLink to="/team/quarterly" style={navLinkStyle}>{t('nav.teamQuarterlyReport')}</NavLink>
      )}
      {user?.is_admin && (
        <NavLink to="/admin" style={navLinkStyle}>{t('nav.admin')}</NavLink>
      )}
      <NavLink to="/settings" style={navLinkStyle}>{t('nav.settings')}</NavLink>
    </nav>
  );
};
