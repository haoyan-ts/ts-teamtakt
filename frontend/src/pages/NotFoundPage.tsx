import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

export const NotFoundPage = () => {
  const { t } = useTranslation();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100vh', gap: '1rem' }}>
      <h1 style={{ fontSize: '2rem', fontWeight: 700 }}>404</h1>
      <Link to="/">{t('common.back')}</Link>
    </div>
  );
};
