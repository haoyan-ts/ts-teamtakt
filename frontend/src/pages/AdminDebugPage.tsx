import { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import {
  debugSendEmail,
  debugSendTeamsMessage,
} from '../api/adminSettings';

// ---------------------------------------------------------------------------
// Styles (inline, consistent with existing admin pages)
// ---------------------------------------------------------------------------

const card: React.CSSProperties = {
  background: 'var(--bg)',
  border: '1px solid var(--border-subtle)',
  borderRadius: '8px',
  padding: '1.5rem',
  marginBottom: '1.5rem',
  maxWidth: '560px',
};

const labelStyle: React.CSSProperties = {
  display: 'block',
  marginBottom: '0.25rem',
  fontWeight: 500,
  fontSize: '0.875rem',
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '0.5rem 0.75rem',
  border: '1px solid var(--border-subtle)',
  borderRadius: '4px',
  background: 'var(--bg-secondary)',
  color: 'var(--text-h)',
  fontSize: '0.875rem',
  boxSizing: 'border-box',
};

const primaryBtn: React.CSSProperties = {
  padding: '0.5rem 1.25rem',
  background: 'var(--primary)',
  color: '#fff',
  border: 'none',
  borderRadius: '4px',
  cursor: 'pointer',
  fontWeight: 500,
};

const disabledBtn: React.CSSProperties = {
  ...primaryBtn,
  opacity: 0.6,
  cursor: 'not-allowed',
};

const fieldGroup: React.CSSProperties = { marginBottom: '1rem' };

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBanner({ ok, message }: { ok: boolean; message: string }) {
  return (
    <div
      style={{
        marginTop: '0.75rem',
        padding: '0.5rem 0.75rem',
        borderRadius: '4px',
        background: ok ? 'var(--success-bg, #d1fae5)' : 'var(--error-bg, #fee2e2)',
        color: ok ? 'var(--success, #065f46)' : 'var(--error, #991b1b)',
        fontSize: '0.875rem',
      }}
    >
      {message}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Email form
// ---------------------------------------------------------------------------

function EmailForm({ adminEmail }: { adminEmail: string }) {
  const [fromAddress, setFromAddress] = useState(adminEmail);
  const [toAddress, setToAddress] = useState('');
  const [subject, setSubject] = useState('[DEBUG] Test Email');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    try {
      await debugSendEmail({ from_address: fromAddress, to_address: toAddress, subject });
      setResult({ ok: true, message: 'Email sent successfully.' });
    } catch (err: unknown) {
      const raw =
        err &&
        typeof err === 'object' &&
        'response' in err
          ? (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
          : undefined;
      const detail = typeof raw === 'string' ? raw : 'Email delivery failed.';
      setResult({ ok: false, message: detail });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={card}>
      <h3 style={{ margin: '0 0 1rem', fontSize: '1rem' }}>Send Test Email</h3>
      <form onSubmit={handleSubmit}>
        <div style={fieldGroup}>
          <label style={labelStyle} htmlFor="debug-from">
            From (MS365 account to send from)
          </label>
          <input
            id="debug-from"
            type="email"
            required
            value={fromAddress}
            onChange={(e) => setFromAddress(e.target.value)}
            style={inputStyle}
          />
        </div>
        <div style={fieldGroup}>
          <label style={labelStyle} htmlFor="debug-to">
            To (recipient)
          </label>
          <input
            id="debug-to"
            type="email"
            required
            value={toAddress}
            onChange={(e) => setToAddress(e.target.value)}
            style={inputStyle}
          />
        </div>
        <div style={fieldGroup}>
          <label style={labelStyle} htmlFor="debug-subject">
            Subject
          </label>
          <input
            id="debug-subject"
            type="text"
            required
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            style={inputStyle}
          />
        </div>
        <button type="submit" style={loading ? disabledBtn : primaryBtn} disabled={loading}>
          {loading ? 'Sending…' : 'Send Test Email'}
        </button>
      </form>
      {result && <StatusBanner ok={result.ok} message={result.message} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Teams form
// ---------------------------------------------------------------------------

function TeamsForm() {
  const [channelLink, setChannelLink] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    try {
      await debugSendTeamsMessage({
        channel_link: channelLink,
        message: message || undefined,
      });
      setResult({ ok: true, message: 'Teams message posted successfully.' });
    } catch (err: unknown) {
      const raw =
        err &&
        typeof err === 'object' &&
        'response' in err
          ? (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
          : undefined;
      const detail = typeof raw === 'string' ? raw : 'Teams message delivery failed.';
      setResult({ ok: false, message: detail });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={card}>
      <h3 style={{ margin: '0 0 1rem', fontSize: '1rem' }}>Send Test Teams Message</h3>
      <form onSubmit={handleSubmit}>
        <div style={fieldGroup}>
          <label style={labelStyle} htmlFor="debug-channel-link">
            Teams Channel Link
          </label>
          <input
            id="debug-channel-link"
            type="url"
            required
            placeholder="https://teams.microsoft.com/l/channel/…"
            value={channelLink}
            onChange={(e) => setChannelLink(e.target.value)}
            style={inputStyle}
          />
        </div>
        <div style={fieldGroup}>
          <label style={labelStyle} htmlFor="debug-message">
            Message body (HTML supported)
          </label>
          <textarea
            id="debug-message"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="<p>This is a <strong>test</strong> message from TeamTakt admin debug tools.</p>"
            rows={6}
            style={{ ...inputStyle, resize: 'vertical', fontFamily: 'monospace' }}
          />
        </div>
        <button type="submit" style={loading ? disabledBtn : primaryBtn} disabled={loading}>
          {loading ? 'Sending…' : 'Send Test Teams Message'}
        </button>
      </form>
      {result && <StatusBanner ok={result.ok} message={result.message} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function AdminDebugPage() {
  const { user } = useAuth();

  return (
    <div style={{ padding: '1.5rem' }}>
      <h2 style={{ margin: '0 0 0.25rem' }}>Debug Notifications</h2>
      <p style={{ margin: '0 0 1.5rem', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
        Send test notifications to verify delivery. Test messages are prefixed with [DEBUG] and do
        not consume idempotency keys or appear in notification logs.
      </p>
      <EmailForm adminEmail={user?.email ?? ''} />
      <TeamsForm />
    </div>
  );
}
