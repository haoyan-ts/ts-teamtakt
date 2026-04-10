type ReportStatus = 'generating' | 'draft' | 'finalized';

interface ReportStatusBadgeProps {
  status: ReportStatus;
}

const CONFIG: Record<ReportStatus, { label: string; bg: string; color: string }> = {
  generating: { label: 'Generating…', bg: '#fef9c3', color: '#854d0e' },
  draft:       { label: 'Draft',       bg: '#e0f2fe', color: '#075985' },
  finalized:   { label: 'Finalized',   bg: '#dcfce7', color: '#166534' },
};

export const ReportStatusBadge = ({ status }: ReportStatusBadgeProps) => {
  const c = CONFIG[status];
  return (
    <span style={{
      display: 'inline-block',
      padding: '0.2rem 0.7rem',
      borderRadius: '999px',
      background: c.bg,
      color: c.color,
      fontWeight: 600,
      fontSize: '0.8125rem',
    }}>
      {c.label}
    </span>
  );
};
