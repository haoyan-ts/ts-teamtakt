import { useTranslation } from 'react-i18next';
import { cancelBtn, dangerBtn } from './adminStyles';

export function ConfirmDialog({
  message,
  onConfirm,
  onCancel,
}: {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
    >
      <div style={{ background: 'var(--bg)', borderRadius: '8px', padding: '1.5rem', maxWidth: '400px' }}>
        <p style={{ margin: '0 0 1rem' }}>{message}</p>
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
          <button onClick={onCancel} style={cancelBtn}>{t('adminLists.confirm.cancel')}</button>
          <button onClick={onConfirm} style={dangerBtn}>{t('adminLists.confirm.confirm')}</button>
        </div>
      </div>
    </div>
  );
}
