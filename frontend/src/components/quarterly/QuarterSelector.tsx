interface QuarterSelectorProps {
  value: string;
  onChange: (q: string) => void;
}

function currentQuarter(): string {
  const now = new Date();
  const y = now.getFullYear();
  const q = Math.ceil((now.getMonth() + 1) / 3);
  return `${y}Q${q}`;
}

function listRecentQuarters(count = 8): string[] {
  const quarters: string[] = [];
  const now = new Date();
  let y = now.getFullYear();
  let q = Math.ceil((now.getMonth() + 1) / 3);
  for (let i = 0; i < count; i++) {
    quarters.push(`${y}Q${q}`);
    q--;
    if (q === 0) { q = 4; y--; }
  }
  return quarters;
}

export const QuarterSelector = ({ value, onChange }: QuarterSelectorProps) => {
  const options = listRecentQuarters();

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        padding: '0.375rem 0.75rem',
        border: '1px solid #e5e7eb',
        borderRadius: '6px',
        fontSize: '0.875rem',
        background: 'white',
      }}
    >
      {options.map((q) => (
        <option key={q} value={q}>{q}</option>
      ))}
    </select>
  );
};

export { currentQuarter };
