import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { updateTask, getWorkTypes } from '../../api/tasks';
import type {
  DailyWorkLogFormEntry,
  SelfAssessmentTag,
  BlockerType,
  SelfAssessmentTagRef,
  EnergyType,
  WorkType,
} from '../../types/dailyRecord';
import { ENERGY_TYPE_META, ENERGY_TYPES, FIBONACCI, FIBONACCI_LABEL_KEYS } from './energyTypeMeta';

interface WorkLogEditModalProps {
  log: DailyWorkLogFormEntry;
  tags: SelfAssessmentTag[];
  blockerTypes: BlockerType[];
  /** Called after successful save with the fully updated entry. */
  onSave: (updated: DailyWorkLogFormEntry) => Promise<void>;
  onClose: () => void;
}

export const WorkLogEditModal = ({
  log,
  tags,
  blockerTypes,
  onSave,
  onClose,
}: WorkLogEditModalProps) => {
  const { t } = useTranslation();
  // ── Section A: Task fields ──────────────────────────────────────────────
  const [title, setTitle] = useState(log.task.title);
  const [description, setDescription] = useState(log.task.description ?? '');
  const [showDesc, setShowDesc] = useState(!!log.task.description);
  const [workTypeId, setWorkTypeId] = useState<string | null>(log.task.work_type_id);
  const [workTypes, setWorkTypes] = useState<WorkType[]>([]);
  const [blockerTypeId, setBlockerTypeId] = useState<string | null>(
    log.task.blocker_type_id
  );
  const [blockerText, setBlockerText] = useState(log.blocker_text ?? '');
  const [showBlocker, setShowBlocker] = useState(
    !!log.task.blocker_type_id || !!log.blocker_text
  );

  // ── Section B: Log fields ───────────────────────────────────────────────
  const [effort, setEffort] = useState(log.effort);
  const [energyType, setEnergyType] = useState<EnergyType | null>(
    log.energy_type
  );
  const [insight, setInsight] = useState(log.insight ?? '');
  const [selfAssessmentTags, setSelfAssessmentTags] = useState<
    SelfAssessmentTagRef[]
  >(log.self_assessment_tags);

  // ── Dirty / discard state ───────────────────────────────────────────────
  const [isDirty, setIsDirty] = useState(false);
  const [showDiscard, setShowDiscard] = useState(false);

  // ── Save state ──────────────────────────────────────────────────────────
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch work types once on mount
  useEffect(() => {
    getWorkTypes().then(setWorkTypes).catch(() => {});
  }, []);

  // Mark dirty whenever any field changes
  useEffect(() => {
    setIsDirty(
      title !== log.task.title ||
        description !== (log.task.description ?? '') ||
        workTypeId !== log.task.work_type_id ||
        blockerTypeId !== log.task.blocker_type_id ||
        blockerText !== (log.blocker_text ?? '') ||
        effort !== log.effort ||
        energyType !== log.energy_type ||
        insight !== (log.insight ?? '') ||
        JSON.stringify(selfAssessmentTags) !==
          JSON.stringify(log.self_assessment_tags)
    );
  }, [
    title,
    description,
    workTypeId,
    blockerTypeId,
    blockerText,
    effort,
    energyType,
    insight,
    selfAssessmentTags,
    log,
  ]);

  // ── Tag helpers ─────────────────────────────────────────────────────────
  const handleTagToggle = (tagId: string) => {
    const existing = selfAssessmentTags.find(
      (t) => t.self_assessment_tag_id === tagId
    );
    if (existing) {
      const remaining = selfAssessmentTags.filter(
        (t) => t.self_assessment_tag_id !== tagId
      );
      const needsPromotion = existing.is_primary && remaining.length > 0;
      setSelfAssessmentTags(
        needsPromotion
          ? remaining.map((t, i) => ({ ...t, is_primary: i === 0 }))
          : remaining
      );
    } else {
      setSelfAssessmentTags([
        ...selfAssessmentTags,
        {
          self_assessment_tag_id: tagId,
          is_primary: selfAssessmentTags.length === 0,
        },
      ]);
    }
  };

  const handleSetPrimary = (tagId: string) => {
    setSelfAssessmentTags(
      selfAssessmentTags.map((t) => ({
        ...t,
        is_primary: t.self_assessment_tag_id === tagId,
      }))
    );
  };

  // ── New work type inline creation ────────────────────────────────────────
  // (removed — work_type is admin/leader-only editable)

  // ── Close / Cancel ──────────────────────────────────────────────────────
  const handleCloseAttempt = () => {    if (isDirty) {
      setShowDiscard(true);
    } else {
      onClose();
    }
  };

  // ── Save ────────────────────────────────────────────────────────────────
  const handleSave = async () => {
    // Validate primary tag
    const primaryCount = selfAssessmentTags.filter((t) => t.is_primary).length;
    if (selfAssessmentTags.length === 0) {
      setError('At least one self-assessment tag required.');
      return;
    }
    if (primaryCount !== 1) {
      setError('Exactly one tag must be set as primary (★).');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      let updatedTask = log.task;

      // Batch all task-field changes into one API call
      const taskPatch: Record<string, unknown> = {};
      const trimmedTitle = title.trim();
      if (trimmedTitle && trimmedTitle !== log.task.title)
        taskPatch.title = trimmedTitle;
      const trimmedDesc = description.trim();
      if (trimmedDesc !== (log.task.description ?? ''))
        taskPatch.description = trimmedDesc || null;
      if (workTypeId !== log.task.work_type_id)
        taskPatch.work_type_id = workTypeId;
      if (blockerTypeId !== log.task.blocker_type_id)
        taskPatch.blocker_type_id = blockerTypeId;

      if (Object.keys(taskPatch).length > 0) {
        updatedTask = await updateTask(log.task.id, taskPatch);
      }

      await onSave({
        ...log,
        task: updatedTask,
        effort,
        energy_type: energyType,
        insight: insight.trim() || null,
        blocker_text: blockerText.trim() || null,
        self_assessment_tags: selfAssessmentTags,
      });
    } catch {
      setError('Failed to save. Please try again.');
      setSaving(false);
    }
  };

  // ── Keyboard: Escape to close ───────────────────────────────────────────
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleCloseAttempt();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDirty]);

  const s = modalStyles;

  return (
    <div style={s.overlay} role="dialog" aria-modal="true" aria-label="Edit work log">
      <div style={s.box}>
        <h3 style={s.heading}>
          Edit Log — <span style={s.taskTitlePreview}>{log.task.title}</span>
        </h3>

        {/* ── Section A: Task ─────────────────────────────────────── */}
        <p style={s.sectionLabel}>Task</p>

        {/* Title */}
        <div style={s.fieldRow}>
          <label style={s.label}>Title *</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            style={s.input}
            placeholder="Task title"
          />
        </div>

        {/* Work Type */}
        <div style={s.fieldRow}>
          <label style={s.label}>Work Type</label>
          <select
            value={workTypeId ?? ''}
            onChange={(e) => setWorkTypeId(e.target.value || null)}
            style={s.select}
          >
            <option value="">— none —</option>
            {workTypes.filter((wt) => wt.is_active || wt.id === workTypeId).map((wt) => (
              <option key={wt.id} value={wt.id}>{wt.name}</option>
            ))}
          </select>
        </div>

        {/* Description (collapsible) */}
        {!showDesc ? (          <button
            type="button"
            onClick={() => setShowDesc(true)}
            style={s.toggleBtn}
          >
            + Add description
          </button>
        ) : (
          <div style={s.collapsible}>
            <div style={{ ...s.fieldRow, alignItems: 'flex-start' }}>
              <label style={s.label}>Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                style={{ ...s.input, resize: 'vertical' }}
                placeholder="Task description"
              />
              <button
                type="button"
                onClick={() => {
                  setShowDesc(false);
                  setDescription(log.task.description ?? '');
                }}
                style={s.iconBtn}
              >
                ✕
              </button>
            </div>
          </div>
        )}

        {/* Blocker (collapsible) */}
        {!showBlocker ? (
          <button
            type="button"
            onClick={() => setShowBlocker(true)}
            style={s.toggleBtn}
          >
            + Add blocker details
          </button>
        ) : (
          <div style={{ ...s.collapsible, background: 'var(--error-bg)' }}>
            <div style={s.fieldRow}>
              <label style={s.label}>Blocker type</label>
              <select
                value={blockerTypeId ?? ''}
                onChange={(e) => setBlockerTypeId(e.target.value || null)}
                style={s.select}
              >
                <option value="">— select —</option>
                {blockerTypes
                  .filter((bt) => bt.is_active)
                  .map((bt) => (
                    <option key={bt.id} value={bt.id}>
                      {bt.name}
                    </option>
                  ))}
              </select>
              <button
                type="button"
                onClick={() => {
                  setShowBlocker(false);
                  setBlockerTypeId(null);
                  setBlockerText('');
                }}
                style={s.iconBtn}
              >
                ✕
              </button>
            </div>
            <div style={s.fieldRow}>
              <label style={s.label}>
                Blocker details{' '}
                <span style={s.privateLabel}>[private]</span>
              </label>
              <input
                type="text"
                value={blockerText}
                onChange={(e) => setBlockerText(e.target.value)}
                style={s.input}
                placeholder="Not visible to other team members"
              />
            </div>
          </div>
        )}

        <hr style={s.divider} />

        {/* ── Section B: Log ──────────────────────────────────────── */}
        <p style={s.sectionLabel}>Today's log</p>

        {/* Effort */}
        <div style={s.fieldRow}>
          <label style={s.label}>Story Points *</label>
          <select
            value={effort}
            onChange={(e) => setEffort(Number(e.target.value))}
            style={{ ...s.select, width: '5rem' }}
          >
            {FIBONACCI.map((n) => (
              <option key={n} value={n}>
                {n} – {t(FIBONACCI_LABEL_KEYS[n])}
              </option>
            ))}
          </select>
          {log.task.estimated_effort != null && (
            <span style={s.hint}>(est. {log.task.estimated_effort})</span>
          )}
        </div>

        {/* Energy type */}
        <div style={s.fieldRow}>
          <label style={s.label}>Energy type</label>
          <div style={s.chipGroup}>
            {ENERGY_TYPES.map((type) => {
              const meta = ENERGY_TYPE_META[type];
              const selected = energyType === type;
              return (
                <button
                  key={type}
                  type="button"
                  onClick={() => setEnergyType(selected ? null : type)}
                  title={meta.label}
                  style={{
                    ...s.energyChip,
                    ...(selected
                      ? {
                          background: meta.color,
                          color: '#fff',
                          borderColor: meta.color,
                        }
                      : {
                          background: 'transparent',
                          color: 'var(--text-secondary)',
                          borderColor: 'var(--border-strong)',
                        }),
                  }}
                >
                  <span>{meta.icon}</span>
                  <span style={s.chipLabel}>{meta.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Insight */}
        <div style={s.fieldRow}>
          <label style={s.label}>Insight</label>
          <input
            type="text"
            value={insight}
            onChange={(e) => setInsight(e.target.value)}
            style={s.input}
            placeholder="What specifically happened today?"
          />
        </div>

        {/* Self-assessment tags */}
        <div style={s.fieldRow}>
          <label style={s.label}>Self-assessment *</label>
          <div style={s.chipGroup}>
            {tags
              .filter((t) => t.is_active)
              .map((tag) => {
                const ref = selfAssessmentTags.find(
                  (t) => t.self_assessment_tag_id === tag.id
                );
                const selected = !!ref;
                const isPrimary = ref?.is_primary ?? false;

                if (isPrimary) {
                  return (
                    <button
                      key={tag.id}
                      type="button"
                      onClick={() => handleTagToggle(tag.id)}
                      style={{
                        ...s.tagChip,
                        background: 'var(--primary)',
                        color: '#fff',
                        border: '1px solid var(--primary)',
                      }}
                      title="Primary tag — click to deselect"
                    >
                      ★ {tag.name}
                    </button>
                  );
                }

                if (selected) {
                  return (
                    <button
                      key={tag.id}
                      type="button"
                      onClick={() => handleSetPrimary(tag.id)}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        handleTagToggle(tag.id);
                      }}
                      style={{
                        ...s.tagChip,
                        background: 'transparent',
                        color: 'var(--primary)',
                        border: '1px solid var(--primary)',
                      }}
                      title="Click to set as primary · right-click to deselect"
                    >
                      ☆ {tag.name}
                    </button>
                  );
                }

                return (
                  <button
                    key={tag.id}
                    type="button"
                    onClick={() => handleTagToggle(tag.id)}
                    style={{
                      ...s.tagChip,
                      background: 'var(--border-subtle)',
                      color: 'var(--text-secondary)',
                      border: '1px solid var(--border-subtle)',
                    }}
                    title="Click to select"
                  >
                    {tag.name}
                  </button>
                );
              })}
          </div>
        </div>
        {selfAssessmentTags.length === 0 && (
          <p style={s.tagError}>At least one tag required; select primary (★)</p>
        )}
        {selfAssessmentTags.length > 0 &&
          selfAssessmentTags.filter((t) => t.is_primary).length === 0 && (
            <p style={s.tagError}>Select one tag as primary (★)</p>
          )}

        {/* Inline discard confirmation */}
        {showDiscard && (
          <div style={s.discardBox}>
            <span style={s.discardText}>Discard unsaved changes?</span>
            <button
              type="button"
              onClick={onClose}
              style={{ ...s.discardBtn, background: 'var(--error)', color: '#fff' }}
            >
              Discard
            </button>
            <button
              type="button"
              onClick={() => setShowDiscard(false)}
              style={s.discardBtn}
            >
              Keep editing
            </button>
          </div>
        )}

        {/* Error */}
        {error && <p style={s.errorMsg}>{error}</p>}

        {/* Footer */}
        <div style={s.footer}>
          <button
            type="button"
            onClick={handleCloseAttempt}
            style={s.cancelBtn}
            disabled={saving}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            style={s.saveBtn}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
};

const modalStyles: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'fixed' as const,
    inset: 0,
    background: 'rgba(0,0,0,0.4)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  box: {
    background: 'var(--bg)',
    borderRadius: '10px',
    padding: '1.5rem',
    width: '520px',
    maxWidth: '92vw',
    maxHeight: '90vh',
    overflowY: 'auto',
    boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
  },
  heading: {
    margin: '0 0 1rem',
    fontSize: '1rem',
    fontWeight: 700,
    display: 'flex',
    alignItems: 'baseline',
    gap: '0.4rem',
    flexWrap: 'wrap',
  },
  taskTitlePreview: {
    fontWeight: 400,
    fontSize: '0.9rem',
    color: 'var(--text-secondary)',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    maxWidth: '280px',
    display: 'inline-block',
  },
  sectionLabel: {
    margin: '0 0 0.6rem',
    fontSize: '0.78rem',
    fontWeight: 700,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.04em',
    color: 'var(--text-muted)',
  },
  divider: {
    border: 'none',
    borderTop: '1px solid var(--border)',
    margin: '1rem 0',
  },
  fieldRow: {
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'wrap' as const,
    gap: '0.4rem',
    marginBottom: '0.6rem',
  },
  label: {
    fontSize: '0.85rem',
    fontWeight: 600,
    color: 'var(--text-body)',
    minWidth: '8rem',
  },
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
  hint: {
    fontSize: '0.78rem',
    color: 'var(--text-secondary)',
  },
  iconBtn: {
    background: 'none',
    border: '1px solid var(--border-strong)',
    borderRadius: '4px',
    padding: '0.1rem 0.4rem',
    cursor: 'pointer',
    fontSize: '0.75rem',
    alignSelf: 'flex-start',
  },
  toggleBtn: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    color: 'var(--text-secondary)',
    fontSize: '0.8rem',
    padding: '0.1rem 0',
    marginBottom: '0.4rem',
  },
  collapsible: {
    background: 'var(--bg-tertiary)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '6px',
    padding: '0.6rem',
    marginBottom: '0.5rem',
  },
  chipGroup: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    gap: '0.35rem',
  },
  energyChip: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.25rem',
    padding: '0.2rem 0.55rem',
    borderRadius: '999px',
    border: '1px solid',
    fontSize: '0.8rem',
    fontWeight: 500,
    cursor: 'pointer',
    lineHeight: 1.3,
    transition: 'background 0.15s, color 0.15s',
  },
  chipLabel: { whiteSpace: 'nowrap' as const },
  tagChip: {
    padding: '0.2rem 0.6rem',
    borderRadius: '999px',
    fontSize: '0.8rem',
    fontWeight: 500,
    cursor: 'pointer',
  },
  tagError: {
    color: 'var(--error)',
    fontSize: '0.75rem',
    margin: '-0.1rem 0 0.5rem',
  },
  discardBox: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    padding: '0.6rem 0.75rem',
    background: 'var(--error-bg)',
    border: '1px solid var(--error)',
    borderRadius: '6px',
    marginBottom: '0.75rem',
    flexWrap: 'wrap' as const,
  },
  discardText: {
    flex: 1,
    fontSize: '0.85rem',
    fontWeight: 600,
    color: 'var(--error)',
    minWidth: '160px',
  },
  discardBtn: {
    padding: '0.25rem 0.65rem',
    background: 'none',
    border: '1px solid var(--border-strong)',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '0.8rem',
    fontWeight: 500,
  },
  errorMsg: {
    color: 'var(--error)',
    fontSize: '0.85rem',
    margin: '0 0 0.5rem',
  },
  footer: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '0.5rem',
    marginTop: '1rem',
  },
  cancelBtn: {
    padding: '0.4rem 0.9rem',
    background: 'none',
    border: '1px solid var(--border-strong)',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 500,
    fontSize: '0.875rem',
  },
  saveBtn: {
    padding: '0.4rem 1.25rem',
    background: 'var(--primary)',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 600,
    fontSize: '0.875rem',
  },
  privateLabel: {
    color: 'var(--text-muted)',
    fontWeight: 400,
    fontSize: '0.75rem',
  },
};
