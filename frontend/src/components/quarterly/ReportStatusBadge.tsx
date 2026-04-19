type ReportStatus = 'generating' | 'draft' | 'finalized';

interface ReportStatusBadgeProps {
  status: ReportStatus;
}

const CONFIG: Record<ReportStatus, { label: string; bg: string; color: string }> = {
  generating: { label: 'Generating…', bg: 'var(--warning-bg)', color: 'var(--warning)' },
  draft:       { label: 'Draft',       bg: 'var(--bg-info)',    color: 'var(--primary)' },
  finalized:   { label: 'Finalized',   bg: 'var(--success-bg)', color: 'var(--success)' },
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
