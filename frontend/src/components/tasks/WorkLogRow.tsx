import { useState, useEffect, useRef } from 'react';
import { updateTask } from '../../api/tasks';
import type {
  DailyWorkLogFormEntry,
  SelfAssessmentTag,
  BlockerType,
  Task,
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
  /** Called after task fields (status/title/description) are updated via API */
  onTaskUpdated: (index: number, updated: Task) => void;
  /** Optional left-border accent color for category color-grouping */
  accentColor?: string;
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
  onTaskUpdated,
  accentColor,
}: WorkLogRowProps) => {
  const [showBlocker, setShowBlocker] = useState(
    log.task.status === 'blocked' || !!log.blocker_type_id
  );
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);

  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState(log.task.title);
  const titleInputRef = useRef<HTMLInputElement>(null);

  const [showDesc, setShowDesc] = useState(!!log.task.description);
  const [descDraft, setDescDraft] = useState(log.task.description ?? '');

  // Keep drafts in sync when parent updates the task object
  useEffect(() => {
    if (!editingTitle) setTitleDraft(log.task.title);
  }, [log.task.title, editingTitle]);

  useEffect(() => {
    setDescDraft(log.task.description ?? '');
    if (log.task.description) setShowDesc(true);
  }, [log.task.description]);

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

  const handleStatusChange = async (newStatus: Task['status']) => {
    setStatusUpdating(true);
    setUpdateError(null);
    try {
      const updated = await updateTask(log.task.id, { status: newStatus });
      onTaskUpdated(index, updated);
    } catch {
      setUpdateError('Failed to update task status.');
    } finally {
      setStatusUpdating(false);
    }
  };

  const handleTitleSave = async () => {
    const trimmed = titleDraft.trim();
    if (!trimmed || trimmed === log.task.title) {
      setEditingTitle(false);
      setTitleDraft(log.task.title);
      return;
    }
    setUpdateError(null);
    try {
      const updated = await updateTask(log.task.id, { title: trimmed });
      onTaskUpdated(index, updated);
    } catch {
      setUpdateError('Failed to update task title.');
      setTitleDraft(log.task.title);
    }
    setEditingTitle(false);
  };

  const handleDescSave = async () => {
    const trimmed = descDraft.trim();
    const currentDesc = log.task.description ?? '';
    if (trimmed === currentDesc) return;
    setUpdateError(null);
    try {
      const updated = await updateTask(log.task.id, { description: trimmed || null });
      onTaskUpdated(index, updated);
    } catch {
      setUpdateError('Failed to update task description.');
      setDescDraft(currentDesc);
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
    <div style={{ ...s.card, ...(accentColor ? { borderLeft: `4px solid ${accentColor}` } : {}) }}>
      {/* Header: task name + status + actions */}
      <div style={s.header}>
        <div style={s.taskMeta}>
          <select
            value={log.task.status}
            onChange={(e) => handleStatusChange(e.target.value as Task['status'])}
            disabled={!isEditable || statusUpdating}
            style={{
              ...s.statusSelect,
              borderColor: statusColor[log.task.status] ?? 'var(--text-muted)',
              color: statusColor[log.task.status] ?? 'var(--text-muted)',
            }}
            title="Task status"
          >
            <option value="todo">todo</option>
            <option value="running">running</option>
            <option value="done">done</option>
            <option value="blocked">blocked</option>
          </select>
          {editingTitle ? (
            <input
              ref={titleInputRef}
              type="text"
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              onBlur={handleTitleSave}
              onKeyDown={(e) => {
                if (e.key === 'Enter') { e.preventDefault(); titleInputRef.current?.blur(); }
                if (e.key === 'Escape') { setEditingTitle(false); setTitleDraft(log.task.title); }
              }}
              style={s.titleInput}
              autoFocus
            />
          ) : (
            <>
              <span style={s.taskTitle} title={log.task.title}>
                {log.task.title}
              </span>
              {isEditable && (
                <button
                  type="button"
                  onClick={() => setEditingTitle(true)}
                  style={s.editTitleBtn}
                  title="Edit title"
                >
                  ✏
                </button>
              )}
            </>
          )}
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

            // When read-only, only render selected tags
            if (!isEditable && !selected) return null;

            if (isPrimary) {
              // Primary: solid filled highlight
              return (
                <button
                  key={tag.id}
                  type="button"
                  onClick={() => isEditable && handleTagToggle(tag.id)}
                  disabled={!isEditable}
                  style={{
                    ...s.tagChip,
                    background: 'var(--primary)',
                    color: '#fff',
                    border: '1px solid var(--primary)',
                    cursor: isEditable ? 'pointer' : 'default',
                  }}
                  title="Primary tag — click to deselect"
                >
                  ★ {tag.name}
                </button>
              );
            }

            if (selected) {
              // Selected non-primary: outline/wireframe, star inside to promote
              return (
                <button
                  key={tag.id}
                  type="button"
                  onClick={() => isEditable && handleSetPrimary(tag.id)}
                  onContextMenu={(e) => { e.preventDefault(); if (isEditable) handleTagToggle(tag.id); }}
                  disabled={!isEditable}
                  style={{
                    ...s.tagChip,
                    background: 'transparent',
                    color: 'var(--primary)',
                    border: '1px solid var(--primary)',
                    cursor: isEditable ? 'pointer' : 'default',
                  }}
                  title={isEditable ? 'Click to set as primary · right-click to deselect' : tag.name}
                >
                  ☆ {tag.name}
                </button>
              );
            }

            // Unselected: gray chip
            return (
              <button
                key={tag.id}
                type="button"
                onClick={() => handleTagToggle(tag.id)}
                disabled={!isEditable}
                style={{
                  ...s.tagChip,
                  background: 'var(--border-subtle)',
                  color: 'var(--text-secondary)',
                  border: '1px solid var(--border-subtle)',
                  cursor: 'pointer',
                }}
                title="Click to select"
              >
                {tag.name}
              </button>
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

      {/* Description (collapsible) */}
      {!showDesc && isEditable && (
        <button
          type="button"
          onClick={() => setShowDesc(true)}
          style={s.blockerToggle}
        >
          + Edit description
        </button>
      )}
      {showDesc && (
        <div style={s.descSection}>
          <div style={{ ...s.fieldRow, alignItems: 'flex-start' }}>
            <label style={s.label}>Description</label>
            <textarea
              value={descDraft}
              onChange={(e) => setDescDraft(e.target.value)}
              onBlur={handleDescSave}
              rows={2}
              style={{ ...s.input, resize: 'vertical' }}
              disabled={!isEditable}
              placeholder="Task description"
            />
            {isEditable && (
              <button
                type="button"
                onClick={() => { setShowDesc(false); setDescDraft(log.task.description ?? ''); }}
                style={{ ...s.iconBtn, alignSelf: 'flex-start' }}
              >
                ✕
              </button>
            )}
          </div>
        </div>
      )}

      {/* Inline update error */}
      {updateError && <p style={s.updateError}>{updateError}</p>}
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
  statusSelect: {
    padding: '0.15rem 0.35rem',
    border: '1px solid',
    borderRadius: '4px',
    fontSize: '0.78rem',
    fontWeight: 600,
    background: 'var(--bg)',
    cursor: 'pointer',
    flexShrink: 0,
  },
  titleInput: {
    fontWeight: 600,
    fontSize: '0.95rem',
    border: '1px solid var(--primary)',
    borderRadius: '4px',
    padding: '0.1rem 0.35rem',
    flex: 1,
    minWidth: '100px',
    outline: 'none',
  },
  editTitleBtn: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    fontSize: '0.8rem',
    color: 'var(--text-muted)',
    padding: '0 0.1rem',
    lineHeight: 1,
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
  tagChip: {
    padding: '0.2rem 0.6rem',
    borderRadius: '999px',
    fontSize: '0.8rem',
    fontWeight: 500,
    transition: 'opacity 0.1s',
  },
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
  descSection: {
    background: 'var(--bg-tertiary)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '6px',
    padding: '0.6rem',
    marginBottom: '0.5rem',
  },
  updateError: { color: 'var(--error)', fontSize: '0.78rem', margin: '0.25rem 0 0' },
};
