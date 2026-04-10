import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../hooks/useAuth';
import { authApi } from '../api/auth';

export const LoginPage = () => {
  const { t } = useTranslation();
  const { setToken, fetchMe, token } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tokenParam = params.get('token');
    if (tokenParam) {
      setLoading(true);
      setToken(tokenParam);
      fetchMe().then(() => {
        navigate('/', { replace: true });
      }).finally(() => setLoading(false));
    } else if (token) {
      navigate('/', { replace: true });
    }
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <p>{t('auth.signingIn')}</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', flexDirection: 'column', gap: '1.5rem' }}>
      <h1 style={{ fontSize: '2rem', fontWeight: 700 }}>TeamTakt</h1>
      <button
        onClick={() => { window.location.href = authApi.getLoginUrl(); }}
        style={{ padding: '0.75rem 1.5rem', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '6px', fontSize: '1rem', cursor: 'pointer' }}
      >
        {t('auth.signIn')}
      </button>
    </div>
  );
};
