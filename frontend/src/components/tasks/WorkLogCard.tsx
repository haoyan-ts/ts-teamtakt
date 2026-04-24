import { useState } from 'react';
import { updateTask } from '../../api/tasks';
import type {
  DailyWorkLogFormEntry,
  SelfAssessmentTag,
  Task,
} from '../../types/dailyRecord';

interface WorkLogCardProps {
  log: DailyWorkLogFormEntry;
  index: number;
  totalLogs: number;
  tags: SelfAssessmentTag[];
  isEditable: boolean;
  accentColor?: string;
  onEdit: () => void;
  onRemove: (index: number) => void;
  onMoveUp: (index: number) => void;
  onMoveDown: (index: number) => void;
  onTaskUpdated: (index: number, updated: Task) => void;
}

export const WorkLogCard = ({
  log,
  index,
  totalLogs,
  tags,
  isEditable,
  accentColor,
  onEdit,
  onRemove,
  onMoveUp,
  onMoveDown,
  onTaskUpdated,
}: WorkLogCardProps) => {
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);

  const handleStatusChange = async (newStatus: Task['status']) => {
    setStatusUpdating(true);
    setUpdateError(null);
    try {
      const updated = await updateTask(log.task.id, { status: newStatus });
      onTaskUpdated(index, updated);
    } catch {
      setUpdateError('Failed to update status.');
    } finally {
      setStatusUpdating(false);
    }
  };

  const primaryTagRef = log.self_assessment_tags.find((t) => t.is_primary);
  const primaryTag = primaryTagRef
    ? tags.find((t) => t.id === primaryTagRef.self_assessment_tag_id)
    : undefined;

  const statusColor: Record<string, string> = {
    todo: 'var(--text-muted)',
    running: 'var(--primary)',
    done: 'var(--success)',
    blocked: 'var(--error)',
  };

  const s = cardStyles;

  return (
    <div
      style={{
        ...s.card,
        ...(accentColor ? { borderLeft: `4px solid ${accentColor}` } : {}),
      }}
    >
      {/* Header row: status + title + GH link + actions */}
      <div style={s.header}>
        <div style={s.taskMeta}>
          <span
            style={{
              ...s.statusBadge,
              background: statusColor[log.task.status] ?? 'var(--text-muted)',
            }}
          >
            {log.task.status === 'blocked' ? '🚧 blocked' : log.task.status}
          </span>
          {log.task.status !== 'blocked' && (['todo', 'running', 'done'] as const).map((st) => (
            <button
              key={st}
              type="button"
              onClick={() => handleStatusChange(st)}
              disabled={!isEditable || statusUpdating || log.task.status === st}
              style={{
                ...s.statusBtn,
                background: log.task.status === st ? (statusColor[st] ?? 'var(--text-muted)') : 'transparent',
                color: log.task.status === st ? '#fff' : (statusColor[st] ?? 'var(--text-muted)'),
                borderColor: statusColor[st] ?? 'var(--text-muted)',
                opacity: (!isEditable || statusUpdating) ? 0.5 : 1,
                cursor: (!isEditable || statusUpdating || log.task.status === st) ? 'default' : 'pointer',
              }}
              title={`Set status to ${st}`}
            >
              {st}
            </button>
          ))}

          <span style={s.taskTitle} title={log.task.title}>
            {log.task.title}
          </span>

          {log.task.github_issue_url && (
            <a
              href={log.task.github_issue_url}
              target="_blank"
              rel="noopener noreferrer"
              style={s.ghLink}
              title="Open GitHub Issue"
            >
              #GH
            </a>
          )}
        </div>

        {/* Reorder + remove + edit */}
        <div style={s.actions}>
          <button
            type="button"
            disabled={index === 0}
            onClick={() => onMoveUp(index)}
            style={s.iconBtn}
            title="Move up"
          >
            ▲
          </button>
          <button
            type="button"
            disabled={index === totalLogs - 1}
            onClick={() => onMoveDown(index)}
            style={s.iconBtn}
            title="Move down"
          >
            ▼
          </button>
          <button
            type="button"
            onClick={() => onRemove(index)}
            style={{ ...s.iconBtn, color: 'var(--error)' }}
            title="Remove from today's log (task is not deleted)"
          >
            ✕
          </button>
          <button
            type="button"
            onClick={onEdit}
            disabled={!isEditable}
            style={{
              ...s.editBtn,
              opacity: isEditable ? 1 : 0.45,
              cursor: isEditable ? 'pointer' : 'not-allowed',
            }}
            title={isEditable ? 'Edit this log entry' : 'Editing is disabled (locked or checked)'}
          >
            Edit
          </button>
        </div>
      </div>

      {/* At-a-glance row: effort + primary tag */}
      <div style={s.glanceRow}>
        <span style={s.effortChip} title="Effort today">
          {log.effort} pts
        </span>
        {primaryTag ? (
          <span style={s.primaryTagBadge} title="Primary self-assessment tag">
            ★ {primaryTag.name}
          </span>
        ) : (
          <span style={s.missingTagBadge} title="No primary tag set">
            ⚠ no tag
          </span>
        )}
        {log.task.blocker_type_id && log.task.status !== 'blocked' && (
          <span style={s.blockerIndicator} title="Task has a blocker">
            🚧 blocked
          </span>
        )}
      </div>

      {updateError && <p style={s.updateError}>{updateError}</p>}
    </div>
  );
};

const cardStyles: Record<string, React.CSSProperties> = {
  card: {
    border: '1px solid var(--border)',
    borderRadius: '8px',
    padding: '0.65rem 1rem',
    marginBottom: '0.5rem',
    background: 'var(--bg-tertiary)',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '0.5rem',
  },
  taskMeta: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    flex: 1,
    minWidth: 0,
  },
  statusBadge: {
    display: 'inline-block',
    padding: '0.15rem 0.5rem',
    borderRadius: '999px',
    fontSize: '0.75rem',
    fontWeight: 700,
    color: '#fff',
    flexShrink: 0,
  },
  statusBtn: {
    padding: '0.1rem 0.45rem',
    border: '1px solid',
    borderRadius: '999px',
    fontSize: '0.72rem',
    fontWeight: 600,
    flexShrink: 0,
  },
  taskTitle: {
    fontWeight: 600,
    fontSize: '0.95rem',
    flex: 1,
    minWidth: 0,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  ghLink: {
    fontSize: '0.7rem',
    color: 'var(--primary)',
    fontWeight: 600,
    textDecoration: 'none',
    border: '1px solid var(--bg-info)',
    borderRadius: '3px',
    padding: '0 0.3rem',
    flexShrink: 0,
  },
  actions: {
    display: 'flex',
    gap: '0.25rem',
    flexShrink: 0,
    alignItems: 'center',
  },
  iconBtn: {
    background: 'none',
    border: '1px solid var(--border-strong)',
    borderRadius: '4px',
    padding: '0.1rem 0.4rem',
    cursor: 'pointer',
    fontSize: '0.75rem',
  },
  editBtn: {
    padding: '0.2rem 0.65rem',
    background: 'var(--primary)',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    fontSize: '0.78rem',
    fontWeight: 600,
  },
  glanceRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    marginTop: '0.4rem',
    flexWrap: 'wrap',
  },
  effortChip: {
    fontSize: '0.78rem',
    fontWeight: 600,
    padding: '0.1rem 0.5rem',
    background: 'var(--bg-info)',
    borderRadius: '999px',
    color: 'var(--text-body)',
    flexShrink: 0,
  },
  primaryTagBadge: {
    fontSize: '0.78rem',
    fontWeight: 600,
    padding: '0.1rem 0.5rem',
    background: 'var(--primary)',
    color: '#fff',
    borderRadius: '999px',
    flexShrink: 0,
  },
  missingTagBadge: {
    fontSize: '0.78rem',
    fontWeight: 600,
    padding: '0.1rem 0.5rem',
    background: 'var(--error-bg)',
    color: 'var(--error)',
    borderRadius: '999px',
    flexShrink: 0,
  },
  blockerIndicator: {
    fontSize: '0.75rem',
    color: 'var(--error)',
    fontWeight: 500,
    flexShrink: 0,
  },
  updateError: {
    color: 'var(--error)',
    fontSize: '0.75rem',
    margin: '0.25rem 0 0',
  },
};
