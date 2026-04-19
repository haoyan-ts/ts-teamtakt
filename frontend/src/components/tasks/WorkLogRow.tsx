import { useState } from 'react';
import { updateTask } from '../../api/tasks';
import type {
  DailyWorkLogFormEntry,
  SelfAssessmentTag,
  BlockerType,
} from '../../types/dailyRecord';

interface WorkLogRowProps {
  log: DailyWorkLogFormEntry;
  index: number;
  totalLogs: number;
  tags: SelfAssessmentTag[];
  blockerTypes: BlockerType[];
  isEditable: boolean;
  onChange: (index: number, updated: Partial<DailyWorkLogFormEntry>) => void;
  onRemove: (index: number) => void;
  onMoveUp: (index: number) => void;
  onMoveDown: (index: number) => void;
  /** Called after task status is updated to 'done' so parent can remove the row */
  onTaskDone: (index: number) => void;
}

export const WorkLogRow = ({
  log,
  index,
  totalLogs,
  tags,
  blockerTypes,
  isEditable,
  onChange,
  onRemove,
  onMoveUp,
  onMoveDown,
  onTaskDone,
}: WorkLogRowProps) => {
  const [showBlocker, setShowBlocker] = useState(
    log.task.status === 'blocked' || !!log.blocker_type_id
  );
  const [markingDone, setMarkingDone] = useState(false);
  const [doneError, setDoneError] = useState<string | null>(null);

  const handleTagToggle = (tagId: string) => {
    const existing = log.self_assessment_tags.find(
      (t) => t.self_assessment_tag_id === tagId
    );
    if (existing) {
      const remaining = log.self_assessment_tags.filter(
        (t) => t.self_assessment_tag_id !== tagId
      );
      const needsPromotion = existing.is_primary && remaining.length > 0;
      onChange(index, {
        self_assessment_tags: needsPromotion
          ? remaining.map((t, i) => ({ ...t, is_primary: i === 0 }))
          : remaining,
      });
    } else {
      onChange(index, {
        self_assessment_tags: [
          ...log.self_assessment_tags,
          {
            self_assessment_tag_id: tagId,
            is_primary: log.self_assessment_tags.length === 0,
          },
        ],
      });
    }
  };

  const handleSetPrimary = (tagId: string) => {
    onChange(index, {
      self_assessment_tags: log.self_assessment_tags.map((t) => ({
        ...t,
        is_primary: t.self_assessment_tag_id === tagId,
      })),
    });
  };

  const handleMarkDone = async () => {
    if (!window.confirm(`Mark "${log.task.title}" as done? This cannot be undone from this form.`)) {
      return;
    }
    setMarkingDone(true);
    setDoneError(null);
    try {
      await updateTask(log.task.id, { status: 'done' });
      onTaskDone(index);
    } catch {
      setDoneError('Failed to mark task as done.');
    } finally {
      setMarkingDone(false);
    }
  };

  const statusColor: Record<string, string> = {
    todo: 'var(--text-muted)',
    running: 'var(--primary)',
    done: 'var(--success)',
    blocked: 'var(--error)',
  };

  const s = rowStyles;

  return (
    <div style={s.card}>
      {/* Header: task name + status + actions */}
      <div style={s.header}>
        <div style={s.taskMeta}>
          <span
            style={{
              ...s.statusDot,
              background: statusColor[log.task.status] ?? 'var(--text-muted)',
            }}
            title={`Status: ${log.task.status}`}
          />
          <span style={s.taskTitle}>{log.task.title}</span>
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
        </div>
      </div>

      {/* Actual effort */}
      <div style={s.fieldRow}>
        <label style={s.label}>Effort today (1–5) *</label>
        <select
          value={log.effort}
          onChange={(e) => onChange(index, { effort: Number(e.target.value) })}
          style={{ ...s.select, width: '5rem' }}
          disabled={!isEditable}
        >
          {[1, 2, 3, 4, 5].map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
        {log.task.estimated_effort != null && (
          <span style={s.effortHint}>
            (est. {log.task.estimated_effort})
          </span>
        )}
      </div>

      {/* Work note */}
      <div style={s.fieldRow}>
        <label style={s.label}>Work note</label>
        <input
          type="text"
          value={log.work_note ?? ''}
          onChange={(e) => onChange(index, { work_note: e.target.value || null })}
          style={s.input}
          disabled={!isEditable}
          placeholder="What specifically happened today?"
        />
      </div>

      {/* Self-assessment tags */}
      <div style={s.fieldRow}>
        <label style={s.label}>Self-assessment *</label>
        <div style={s.tagGroup}>
          {tags.filter((t) => t.is_active).map((tag) => {
            const ref = log.self_assessment_tags.find(
              (t) => t.self_assessment_tag_id === tag.id
            );
            const selected = !!ref;
            const isPrimary = ref?.is_primary ?? false;
            return (
              <span key={tag.id} style={s.tagWrapper}>
                <button
                  type="button"
                  onClick={() => handleTagToggle(tag.id)}
                  disabled={!isEditable}
                  style={{
                    ...s.tagBtn,
                    background: selected ? 'var(--primary)' : 'var(--border)',
                    color: selected ? '#fff' : 'var(--text-body)',
                    opacity: !isEditable ? 0.6 : 1,
                    cursor: !isEditable ? 'default' : 'pointer',
                  }}
                >
                  {tag.name}
                </button>
                {selected && !isPrimary && (
                  <button
                    type="button"
                    onClick={() => handleSetPrimary(tag.id)}
                    disabled={!isEditable}
                    style={{
                      ...s.primaryBtn,
                      opacity: !isEditable ? 0.4 : 1,
                      cursor: !isEditable ? 'default' : 'pointer',
                    }}
                    title="Set as primary"
                  >
                    ★
                  </button>
                )}
                {selected && isPrimary && (
                  <span style={s.primaryIndicator} title="Primary tag">★</span>
                )}
              </span>
            );
          })}
        </div>
      </div>
      {log.self_assessment_tags.filter((t) => t.is_primary).length === 0 &&
        log.self_assessment_tags.length > 0 && (
          <p style={s.tagError}>Select one tag as primary (★)</p>
        )}
      {log.self_assessment_tags.length === 0 && (
        <p style={s.tagError}>At least one tag required; select primary (★)</p>
      )}

      {/* Blocker override (collapsible) */}
      {!showBlocker && isEditable && (
        <button
          type="button"
          onClick={() => setShowBlocker(true)}
          style={s.blockerToggle}
        >
          + Add blocker details
        </button>
      )}
      {showBlocker && (
        <div style={s.blockerSection}>
          <div style={s.fieldRow}>
            <label style={s.label}>Blocker type</label>
            <select
              value={log.blocker_type_id ?? ''}
              onChange={(e) =>
                onChange(index, { blocker_type_id: e.target.value || null })
              }
              style={s.select}
              disabled={!isEditable}
            >
              <option value="">— select —</option>
              {blockerTypes.filter((bt) => bt.is_active).map((bt) => (
                <option key={bt.id} value={bt.id}>{bt.name}</option>
              ))}
            </select>
            {isEditable && (
              <button
                type="button"
                onClick={() => { setShowBlocker(false); onChange(index, { blocker_type_id: null, blocker_text: null }); }}
                style={{ ...s.iconBtn, marginLeft: '0.5rem' }}
              >
                ✕
              </button>
            )}
          </div>
          <div style={s.fieldRow}>
            <label style={s.label}>Blocker details <span style={s.privateLabel}>[private]</span></label>
            <input
              type="text"
              value={log.blocker_text ?? ''}
              onChange={(e) =>
                onChange(index, { blocker_text: e.target.value || null })
              }
              style={s.input}
              disabled={!isEditable}
              placeholder="Describe the blocker (not visible to other team members)"
            />
          </div>
        </div>
      )}

      {/* Mark done */}
      {isEditable && log.task.status !== 'done' && (
        <div style={{ marginTop: '0.5rem' }}>
          <button
            type="button"
            onClick={handleMarkDone}
            disabled={markingDone}
            style={s.doneBtn}
          >
            {markingDone ? 'Marking…' : '✓ Mark task done'}
          </button>
          {doneError && <span style={s.doneError}>{doneError}</span>}
        </div>
      )}
    </div>
  );
};

const rowStyles: Record<string, React.CSSProperties> = {
  card: {
    border: '1px solid var(--border)',
    borderRadius: '8px',
    padding: '1rem',
    marginBottom: '0.75rem',
    background: 'var(--bg-tertiary)',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '0.75rem',
  },
  taskMeta: { display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1, minWidth: 0 },
  statusDot: {
    width: '10px',
    height: '10px',
    borderRadius: '50%',
    flexShrink: 0,
  },
  taskTitle: {
    fontWeight: 600,
    fontSize: '0.95rem',
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
  actions: { display: 'flex', gap: '0.25rem', flexShrink: 0 },
  iconBtn: {
    background: 'none',
    border: '1px solid var(--border-strong)',
    borderRadius: '4px',
    padding: '0.1rem 0.4rem',
    cursor: 'pointer',
    fontSize: '0.75rem',
  },
  fieldRow: {
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '0.4rem',
    marginBottom: '0.6rem',
  },
  label: { fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-body)', minWidth: '9rem' },
  input: {
    flex: 1,
    padding: '0.3rem 0.5rem',
    border: '1px solid var(--border-strong)',
    borderRadius: '5px',
    fontSize: '0.875rem',
    minWidth: '140px',
    background: 'var(--bg)',
    color: 'var(--text-h)',
  },
  select: {
    padding: '0.3rem 0.5rem',
    border: '1px solid var(--border-strong)',
    borderRadius: '5px',
    fontSize: '0.875rem',
    background: 'var(--bg)',
    color: 'var(--text-h)',
  },
  effortHint: { fontSize: '0.78rem', color: 'var(--text-secondary)' },
  tagGroup: { display: 'flex', flexWrap: 'wrap', gap: '0.35rem' },
  tagWrapper: { display: 'inline-flex', alignItems: 'center' },
  tagBtn: {
    padding: '0.2rem 0.55rem',
    border: 'none',
    borderRadius: '4px',
    fontSize: '0.8rem',
    fontWeight: 500,
  },
  primaryBtn: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    color: 'var(--warning)',
    fontSize: '0.9rem',
    padding: '0 0.15rem',
  },
  primaryIndicator: { color: 'var(--warning)', fontSize: '0.9rem', padding: '0 0.15rem' },
  tagError: { color: 'var(--error)', fontSize: '0.75rem', margin: '-0.1rem 0 0.5rem' },
  blockerSection: {
    background: 'var(--error-bg)',
    border: '1px solid var(--error-bg)',
    borderRadius: '6px',
    padding: '0.6rem',
    marginBottom: '0.5rem',
  },
  blockerToggle: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    color: 'var(--text-secondary)',
    fontSize: '0.8rem',
    padding: '0.1rem 0',
    marginBottom: '0.4rem',
  },
  privateLabel: { color: 'var(--text-muted)', fontWeight: 400, fontSize: '0.75rem' },
  doneBtn: {
    padding: '0.25rem 0.7rem',
    background: 'var(--success)',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '0.8rem',
    fontWeight: 500,
  },
  doneError: { color: 'var(--error)', fontSize: '0.8rem', marginLeft: '0.5rem' },
};
