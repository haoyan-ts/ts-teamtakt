import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/useAuth';

export const Sidebar = ({ isOpen }: { isOpen: boolean }) => {
  const { t } = useTranslation();
  const { user } = useAuth();

  const navLinkStyle = ({ isActive }: { isActive: boolean }) => ({
    display: 'block',
    padding: '0.75rem 1.5rem',
    color: isActive ? 'var(--primary)' : 'var(--text-h)',
    textDecoration: 'none',
    fontWeight: isActive ? 600 : 400,
    background: isActive ? 'var(--primary-bg)' : 'transparent',
    borderLeft: isActive ? '3px solid var(--primary)' : '3px solid transparent',
  });

  return (
    <nav style={{
      width: isOpen ? '240px' : '0',
      overflow: 'hidden',
      transition: 'width 0.2s',
      background: 'var(--bg-secondary)',
      borderRight: '1px solid var(--border-subtle)',
      flexShrink: 0,
      height: '100%',
    }}>
      <div style={{ padding: '1rem 1.5rem', fontWeight: 700, fontSize: '1.125rem', borderBottom: '1px solid var(--border-subtle)' }}>
        TeamTakt
      </div>
      <NavLink to="/" end style={navLinkStyle}>{t('nav.dashboard')}</NavLink>
      <NavLink to="/feed" style={navLinkStyle}>{t('nav.feed')}</NavLink>
      <NavLink to="/reports/quarterly" style={navLinkStyle}>{t('nav.quarterlyReport')}</NavLink>
      {!user?.lobby && user?.team && (
        <NavLink to="/team/members" style={navLinkStyle}>{t('nav.myTeam', 'My Team')}</NavLink>
      )}
      {user?.is_leader && (
        <NavLink to="/team" style={navLinkStyle}>{t('nav.team')}</NavLink>
      )}
      {user?.is_leader && (
        <NavLink to="/team/quarterly" style={navLinkStyle}>{t('nav.teamQuarterlyReport')}</NavLink>
      )}
      {user?.is_leader && (
        <NavLink to="/team/sharing" style={navLinkStyle}>{t('nav.crossTeamSharing', 'Cross-Team Sharing')}</NavLink>
      )}
      <NavLink to="/projects" style={navLinkStyle}>{t('nav.projects', 'Projects')}</NavLink>
      {user?.is_admin && (
        <NavLink to="/admin/lists" style={navLinkStyle}>{t('nav.admin')}</NavLink>
      )}
      {user?.is_admin && (
        <NavLink to="/admin/teams" style={navLinkStyle}>{t('nav.adminTeams', 'Teams')}</NavLink>
      )}
      <NavLink to="/settings" style={navLinkStyle}>{t('nav.settings')}</NavLink>
    </nav>
  );
};
