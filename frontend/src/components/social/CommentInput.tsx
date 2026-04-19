import { useState, useRef } from 'react';

interface CommentInputProps {
  onSubmit: (body: string) => Promise<void>;
  placeholder?: string;
  autoFocus?: boolean;
  onCancel?: () => void;
}

export const CommentInput = ({
  onSubmit,
  placeholder = 'Write a comment…',
  autoFocus = false,
  onCancel,
}: CommentInputProps) => {
  const [body, setBody] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = async () => {
    const trimmed = body.trim();
    if (!trimmed || trimmed.length > 4000) return;
    setSubmitting(true);
    try {
      await onSubmit(trimmed);
      setBody('');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      <textarea
        ref={textareaRef}
        autoFocus={autoFocus}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            handleSubmit();
          }
        }}
        placeholder={placeholder}
        rows={3}
        maxLength={4000}
        style={{
          width: '100%',
          padding: '0.5rem',
          border: '1px solid var(--border-subtle)',
          borderRadius: '6px',
          fontFamily: 'inherit',
          fontSize: '0.875rem',
          resize: 'vertical',
          boxSizing: 'border-box',
          background: 'var(--bg)',
          color: 'var(--text-h)',
        }}
      />
      <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', alignItems: 'center' }}>
        <span style={{ fontSize: '0.75rem', color: body.length > 3800 ? 'var(--error)' : 'var(--text-muted)' }}>
          {body.length}/4000
        </span>
        {onCancel && (
          <button
            onClick={onCancel}
            style={{
              padding: '0.375rem 0.75rem',
              border: '1px solid var(--border-subtle)',
              borderRadius: '6px',
              background: 'var(--bg)',
              cursor: 'pointer',
              fontSize: '0.875rem',
            }}
          >
            Cancel
          </button>
        )}
        <button
          onClick={handleSubmit}
          disabled={submitting || !body.trim()}
          style={{
            padding: '0.375rem 0.75rem',
            border: 'none',
            borderRadius: '6px',
            background: body.trim() ? 'var(--primary)' : 'var(--primary-bg)',
            color: 'white',
            cursor: body.trim() && !submitting ? 'pointer' : 'not-allowed',
            fontSize: '0.875rem',
          }}
        >
          {submitting ? 'Posting…' : 'Post (Ctrl+Enter)'}
        </button>
      </div>
    </div>
  );
};
