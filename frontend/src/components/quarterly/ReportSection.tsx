import { useState } from 'react';

interface ReportSectionProps {
  title: string;
  content: string;
  editable?: boolean;
  onSave?: (newContent: string) => Promise<void>;
}

export const ReportSection = ({ title, content, editable = false, onSave }: ReportSectionProps) => {
  const [open, setOpen] = useState(true);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(content);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!onSave) return;
    setSaving(true);
    try {
      await onSave(draft);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: '8px', overflow: 'hidden', marginBottom: '0.75rem' }}>
      {/* Accordion header */}
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          display: 'flex',
          width: '100%',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '0.75rem 1rem',
          background: '#f9fafb',
          border: 'none',
          cursor: 'pointer',
          fontWeight: 600,
          fontSize: '0.9375rem',
          color: '#111827',
        }}
      >
        <span>{title}</span>
        <span style={{ fontSize: '1rem', transform: open ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }}>›</span>
      </button>

      {open && (
        <div style={{ padding: '0.75rem 1rem' }}>
          {editing ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={10}
                style={{
                  width: '100%',
                  padding: '0.5rem',
                  border: '1px solid #e5e7eb',
                  borderRadius: '6px',
                  fontFamily: 'inherit',
                  fontSize: '0.875rem',
                  resize: 'vertical',
                  boxSizing: 'border-box',
                }}
              />
              <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                <button
                  onClick={() => { setDraft(content); setEditing(false); }}
                  style={{ padding: '0.375rem 0.75rem', border: '1px solid #e5e7eb', borderRadius: '6px', background: 'white', cursor: 'pointer', fontSize: '0.875rem' }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  style={{ padding: '0.375rem 0.75rem', border: 'none', borderRadius: '6px', background: '#2563eb', color: 'white', cursor: saving ? 'not-allowed' : 'pointer', fontSize: '0.875rem' }}
                >
                  {saving ? 'Saving…' : 'Save'}
                </button>
              </div>
            </div>
          ) : (
            <div>
              <p style={{ margin: 0, fontSize: '0.875rem', whiteSpace: 'pre-wrap', color: '#374151', lineHeight: 1.7 }}>
                {content || <em style={{ color: '#9ca3af' }}>No content yet.</em>}
              </p>
              {editable && (
                <button
                  onClick={() => { setDraft(content); setEditing(true); }}
                  style={{ marginTop: '0.5rem', fontSize: '0.8125rem', color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                >
                  Edit
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
