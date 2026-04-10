import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../hooks/useAuth';
import { authApi } from '../api/auth';
import client from '../api/client';

interface Team {
  id: string;
  name: string;
}

export const OnboardingPage = () => {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const [teams, setTeams] = useState<Team[]>([]);
  const [requested, setRequested] = useState<Set<string>>(new Set());

  useEffect(() => {
    client.get<Team[]>('/teams').then((res) => setTeams(res.data)).catch(() => {});
  }, []);

  const handleRequest = async (teamId: string) => {
    await client.post(`/teams/${teamId}/join-requests`).catch(() => {});
    setRequested((prev) => new Set(prev).add(teamId));
  };

  const handleSignOut = async () => {
    await authApi.logout().catch(() => {});
    logout();
    window.location.href = '/login';
  };

  return (
    <div style={{ maxWidth: '480px', margin: '4rem auto', padding: '2rem', textAlign: 'center' }}>
      <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>{t('onboarding.title')}</h1>
      <p style={{ color: '#6b7280', marginBottom: '2rem' }}>{t('onboarding.subtitle')}</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '2rem' }}>
        {teams.map((team) => (
          <div key={team.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem 1rem', border: '1px solid #e5e7eb', borderRadius: '6px' }}>
            <span>{team.name}</span>
            {requested.has(team.id) ? (
              <span style={{ color: '#6b7280', fontSize: '0.875rem' }}>{t('onboarding.pending')}</span>
            ) : (
              <button onClick={() => handleRequest(team.id)} style={{ padding: '0.375rem 0.75rem', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                {t('onboarding.requestJoin')}
              </button>
            )}
          </div>
        ))}
      </div>
      <button onClick={handleSignOut} style={{ background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer', textDecoration: 'underline' }}>
        {t('auth.signOut')}
      </button>
    </div>
  );
};
