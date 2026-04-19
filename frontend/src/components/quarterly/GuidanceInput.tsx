interface GuidanceInputProps {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}

export const GuidanceInput = ({ value, onChange, disabled = false }: GuidanceInputProps) => {
  const MAX = 2000;
  const remaining = MAX - value.length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
      <label style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-body)' }}>
        Guidance for AI (optional)
      </label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value.slice(0, MAX))}
        disabled={disabled}
        rows={4}
        maxLength={MAX}
        placeholder="Describe anything specific you want the AI to focus on or emphasize…"
        style={{
          width: '100%',
          padding: '0.5rem',
          border: '1px solid var(--border-subtle)',
          borderRadius: '6px',
          fontFamily: 'inherit',
          fontSize: '0.875rem',
          resize: 'vertical',
          boxSizing: 'border-box',
          opacity: disabled ? 0.6 : 1,
        }}
      />
      <span style={{ fontSize: '0.75rem', color: remaining < 200 ? 'var(--error)' : 'var(--text-muted)', alignSelf: 'flex-end' }}>
        {remaining} characters remaining
      </span>
    </div>
  );
};
