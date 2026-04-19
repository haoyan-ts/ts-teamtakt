import { listRecentQuarters } from './quarterUtils';

interface QuarterSelectorProps {
  value: string;
  onChange: (q: string) => void;
}

export const QuarterSelector = ({ value, onChange }: QuarterSelectorProps) => {
  const options = listRecentQuarters();

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        padding: '0.375rem 0.75rem',
        border: '1px solid var(--border-subtle)',
        borderRadius: '6px',
        fontSize: '0.875rem',
        background: 'var(--bg)',
        color: 'var(--text-h)',
      }}
    >
      {options.map((q) => (
        <option key={q} value={q}>{q}</option>
      ))}
    </select>
  );
};
