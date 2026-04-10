import { useState } from 'react';
import { useAuthStore } from '../stores/authStore';
import client from '../api/client';

type Scope = 'my' | 'team' | 'bulk';
type Format = 'csv' | 'xlsx';

export const ExportPage = () => {
  const user = useAuthStore((s) => s.user);
  const isLeader = user?.is_leader ?? false;
  const isAdmin = user?.is_admin ?? false;

  const [scope, setScope] = useState<Scope>('my');
  const [format, setFormat] = useState<Format>('csv');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState('');
  const [teamId, setTeamId] = useState<number | ''>('');

  const handleDownload = async () => {
    setError('');
    setDownloading(true);
    try {
      let url = '';
      const params = new URLSearchParams({ format });
      if (startDate) params.set('start_date', startDate);
      if (endDate) params.set('end_date', endDate);

      if (scope === 'my') {
        url = `/api/v1/export/my-records?${params}`;
      } else if (scope === 'team') {
        if (!teamId) { setError('Please enter your team ID.'); setDownloading(false); return; }
        url = `/api/v1/export/team/${teamId}?${params}`;
      } else {
        url = `/api/v1/export/bulk?${params}`;
      }

      // Trigger download via fetch + blob to allow auth header
      const response = await client.get(url, { responseType: 'blob' });
      const blob = new Blob([response.data as BlobPart]);
      const anchor = document.createElement('a');
      anchor.href = URL.createObjectURL(blob);
      const ext = format;
      const base = scope === 'bulk' ? 'all-data' : scope === 'team' ? `team-${teamId}` : 'my-records';
      anchor.download = `${base}-export.${ext}`;
      anchor.click();
      URL.revokeObjectURL(anchor.href);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? 'Export failed. Check your permissions and date range.');
    } finally {
      setDownloading(false);
    }
  };

  const row: React.CSSProperties = { display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' };
  const label: React.CSSProperties = { fontSize: '0.85rem', fontWeight: 600, display: 'block', marginBottom: '0.25rem' };
  const radioBtn = (active: boolean): React.CSSProperties => ({
    padding: '0.35rem 0.8rem',
    border: `1px solid ${active ? '#3182ce' : '#cbd5e0'}`,
    borderRadius: 6,
    cursor: 'pointer',
    background: active ? '#ebf8ff' : '#fff',
    color: active ? '#2b6cb0' : '#4a5568',
    fontSize: '0.85rem',
    fontWeight: active ? 600 : 400,
  });
  const input: React.CSSProperties = { border: '1px solid #cbd5e0', borderRadius: 4, padding: '4px 8px', fontSize: '0.85rem' };

  return (
    <div style={{ maxWidth: 540, margin: '0 auto' }}>
      <h2 style={{ marginBottom: '1.5rem' }}>Export Data</h2>

      {/* Scope */}
      <div style={{ marginBottom: '1rem' }}>
        <div style={label}>Scope</div>
        <div style={row}>
          <button style={radioBtn(scope === 'my')} onClick={() => setScope('my')}>My Records</button>
          {isLeader && (
            <button style={radioBtn(scope === 'team')} onClick={() => setScope('team')}>Team Records</button>
          )}
          {isAdmin && (
            <button style={radioBtn(scope === 'bulk')} onClick={() => setScope('bulk')}>All Data (Admin)</button>
          )}
        </div>
      </div>

      {scope === 'team' && (
        <div style={{ marginBottom: '1rem' }}>
          <label style={label}>Team ID</label>
          <input type="number" min={1} value={teamId} onChange={(e) => setTeamId(Number(e.target.value) || '')}
            style={input} placeholder="e.g. 1" />
        </div>
      )}

      {/* Format */}
      <div style={{ marginBottom: '1rem' }}>
        <div style={label}>Format</div>
        <div style={row}>
          <button style={radioBtn(format === 'csv')} onClick={() => setFormat('csv')}>CSV</button>
          <button style={radioBtn(format === 'xlsx')} onClick={() => setFormat('xlsx')}>XLSX (Excel)</button>
        </div>
      </div>

      {/* Date range (hidden for bulk admin export) */}
      {scope !== 'bulk' && (
        <div style={{ marginBottom: '1rem' }}>
          <div style={label}>Date Range (optional)</div>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} style={input} />
            <span style={{ fontSize: '0.85rem' }}>–</span>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} style={input} />
          </div>
        </div>
      )}

      {error && <p style={{ color: '#e53e3e', fontSize: '0.85rem', marginBottom: '0.75rem' }}>{error}</p>}

      <button
        onClick={handleDownload}
        disabled={downloading}
        style={{
          padding: '0.5rem 1.5rem',
          background: downloading ? '#a0aec0' : '#3182ce',
          color: '#fff',
          border: 'none',
          borderRadius: 6,
          cursor: downloading ? 'not-allowed' : 'pointer',
          fontWeight: 600,
        }}>
        {downloading ? 'Preparing…' : '↓ Download'}
      </button>

      <div style={{ marginTop: '1.5rem', fontSize: '0.8rem', color: '#a0aec0', lineHeight: 1.5 }}>
        <strong>Notes:</strong><br />
        • CSV: UTF-8 BOM, one row per task entry.<br />
        • XLSX my/team: Sheet 1 = Daily Records, Sheet 2 = Task Entries.<br />
        • XLSX bulk: separate sheets per entity type.
      </div>
    </div>
  );
};
