import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  createDailyRecord,
  updateDailyRecord,
  getDailyRecords,
  createAbsence,
  deleteAbsence,
  getAbsences,
  getUnlockGrants,
} from '../api/dailyRecords';
import { getActiveTasks, getTask } from '../api/tasks';
import { getCategories, getSelfAssessmentTags, getBlockerTypes } from '../api/categories';
import { getAbsenceTypes } from '../api/absenceTypes';
import { getProjects } from '../api/projects';
import { WorkLogRow } from '../components/tasks/WorkLogRow';
import { TaskCreateModal } from '../components/tasks/TaskCreateModal';
import type {
  AbsenceType,
  Category,
  SelfAssessmentTag,
  BlockerType,
  Project,
  Task,
  DailyRecord,
  DailyWorkLogFormEntry,
  Absence,
  UnlockGrant,
} from '../types/dailyRecord';

// ---------------------------------------------------------------------------
// Edit window helpers (mirrors backend logic — server always re-validates)
// ---------------------------------------------------------------------------

function mondayOf(d: Date): Date {
  const day = d.getDay(); // 0=Sun
  const diff = day === 0 ? -6 : 1 - day;
  const m = new Date(d);
  m.setDate(d.getDate() + diff);
  m.setHours(0, 0, 0, 0);
  return m;
}

function computeEditDeadlineJST(recordDate: string): Date {
  const [y, mo, da] = recordDate.split('-').map(Number);
  const d = new Date(y, mo - 1, da);
  const mon = mondayOf(d);
  // Monday + 12 days = Saturday 00:00 JST
  // Approximate JST offset as UTC+9
  const saturdayLocal = new Date(mon);
  saturdayLocal.setDate(mon.getDate() + 12);
  // Treat as JST midnight (UTC+9 = UTC-9 hours, i.e. previous day 15:00 UTC)
  return new Date(
    Date.UTC(
      saturdayLocal.getFullYear(),
      saturdayLocal.getMonth(),
      saturdayLocal.getDate(),
    ) - 9 * 60 * 60 * 1000
  );
}

// ---------------------------------------------------------------------------
// Category color palette (cycles for large category lists)
// ---------------------------------------------------------------------------
const CATEGORY_PALETTE = [
  '#4299e1', // blue
  '#48bb78', // green
  '#ed8936', // orange
  '#9f7aea', // purple
  '#e53e3e', // red
  '#38b2ac', // teal
  '#f6ad55', // amber
  '#667eea', // indigo
];
const CATEGORY_FALLBACK_COLOR = 'var(--text-muted)'; // gray — for unknown category

function getColorMap(categories: Category[]): Map<string, string> {
  const map = new Map<string, string>();
  categories.forEach((cat, i) => {
    map.set(cat.id, CATEGORY_PALETTE[i % CATEGORY_PALETTE.length]);
  });
  return map;
}

function getEditWindowState(
  recordDate: string,
  formOpenedAt: Date,
): 'open' | 'grace' | 'locked' {
  const deadline = computeEditDeadlineJST(recordDate);
  const now = new Date();
  if (now < deadline) return 'open';
  if (formOpenedAt < deadline && now < new Date(deadline.getTime() + 15 * 60 * 1000)) {
    return 'grace';
  }
  return 'locked';
}

// ---------------------------------------------------------------------------
// Counter for unique log row keys
// ---------------------------------------------------------------------------
let _keyCounter = 0;
const newKey = () => `log-${++_keyCounter}`;

function taskToBlankLog(task: Task): DailyWorkLogFormEntry {
  return {
    _key: newKey(),
    task,
    task_id: task.id,
    effort: 3,
    energy_type: null,
    insight: null,
    blocker_type_id: null,
    blocker_text: null,
    sort_order: 0,
    self_assessment_tags: [],
  };
}

// ---------------------------------------------------------------------------
// Validation helper
// ---------------------------------------------------------------------------
function validatePrimaryTags(logs: DailyWorkLogFormEntry[]): string | null {
  for (const log of logs) {
    const primaryCount = log.self_assessment_tags.filter((t) => t.is_primary).length;
    if (primaryCount === 0) return 'Each work log must have exactly one primary self-assessment tag.';
    if (primaryCount > 1) return 'Each work log must have exactly one primary self-assessment tag.';
  }
  return null;
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export const DailyFormPage = () => {
  const { date: dateParam } = useParams<{ date?: string }>();
  const navigate = useNavigate();

  const todayISO = new Date().toISOString().slice(0, 10);
  const recordDate = dateParam ?? todayISO;

  // Captured on component mount — used for edit-window grace period check
  const formOpenedAt = useRef(new Date());

  // Reference data
  const [categories, setCategories] = useState<Category[]>([]);
  const [tags, setTags] = useState<SelfAssessmentTag[]>([]);
  const [blockerTypes, setBlockerTypes] = useState<BlockerType[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [absenceTypes, setAbsenceTypes] = useState<AbsenceType[]>([]);

  // Record state
  const [existingRecord, setExistingRecord] = useState<DailyRecord | null>(null);
  const [existingAbsence, setExistingAbsence] = useState<Absence | null>(null);
  const [unlockGrant, setUnlockGrant] = useState<UnlockGrant | null>(null);

  // Form fields
  const [isAbsenceMode, setIsAbsenceMode] = useState(false);
  const [absenceType, setAbsenceType] = useState<string>('holiday');
  const [workLogs, setWorkLogs] = useState<DailyWorkLogFormEntry[]>([]);
  const [dayLoad, setDayLoad] = useState(50);
  const [dayNote, setDayNote] = useState('');

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [showConfirmCheck, setShowConfirmCheck] = useState(false);

  // Task create modal
  const [showTaskModal, setShowTaskModal] = useState(false);

  // Dirty tracking — set on first user interaction, reset after successful save
  const isDirty = useRef(false);

  // Edit window
  const windowState = useMemo(
    () => getEditWindowState(recordDate, formOpenedAt.current),
    [recordDate]
  );
  const isEditable = (windowState !== 'locked' || !!unlockGrant) && !checked;

  // Category → accent color map (stable across renders, cycles through palette)
  const categoryColorMap = useMemo(() => getColorMap(categories), [categories]);

  // Load reference data + existing record
  useEffect(() => {
    setLoading(true);
    setError(null);
    // Reset all date-specific state so stale data from a previous date never lingers.
    setExistingRecord(null);
    setExistingAbsence(null);
    setUnlockGrant(null);
    setIsAbsenceMode(false);
    setAbsenceTypes([]);
    setAbsenceType('');
    setWorkLogs([]);
    setDayLoad(50);
    setDayNote('');
    setSuccessMsg(null);
    setChecked(false);
    setShowConfirmCheck(false);
    isDirty.current = false;
    (async () => {
      try {
        const [cats, tagList, btList, projs, absenceTypeList, records, absences, grants, activeTasks] =
          await Promise.all([
            getCategories(),
            getSelfAssessmentTags(),
            getBlockerTypes(),
            getProjects(),
            getAbsenceTypes(),
            getDailyRecords({ date: recordDate }),
            getAbsences({ start_date: recordDate, end_date: recordDate }),
            getUnlockGrants({ record_date: recordDate }),
            getActiveTasks(),
          ]);
        setCategories(cats);
        setTags(tagList);
        setBlockerTypes(btList);
        setProjects(projs);
        setAbsenceTypes(absenceTypeList);
        setAbsenceType(absenceTypeList[0]?.id ?? '');

        if (records.length > 0) {
          const rec = records[0];
          setExistingRecord(rec);
          setChecked(true); // already submitted — start in locked state
          setDayLoad(rec.day_load ?? 50);
          setDayNote(rec.day_note ?? '');

          const activeTasksById = new Map(activeTasks.map((t) => [t.id, t]));

          // Fetch tasks that are in the saved record but no longer in activeTasks
          // (e.g. soft-deleted tasks with is_active=false).
          const orphanedIds = rec.daily_work_logs
            .map((l) => l.task_id)
            .filter((id) => !activeTasksById.has(id));
          const orphanedTasks = (
            await Promise.all(
              orphanedIds.map((id) => getTask(id).catch(() => null))
            )
          ).filter((t): t is Task => t !== null);
          const orphanedTasksById = new Map(orphanedTasks.map((t) => [t.id, t]));

          const allTasksById = new Map([...activeTasksById, ...orphanedTasksById]);

          // Part A: rows from saved logs (in sort_order), including orphaned tasks.
          const savedLogRows: DailyWorkLogFormEntry[] = rec.daily_work_logs
            .slice()
            .sort((a, b) => a.sort_order - b.sort_order)
            .flatMap((log) => {
              const task = allTasksById.get(log.task_id);
              if (!task) return []; // task no longer fetchable — skip gracefully
              return [{
                _key: newKey(),
                task,
                task_id: log.task_id,
                effort: log.effort,
                energy_type: log.energy_type,
                insight: log.insight,
                blocker_type_id: log.blocker_type_id,
                blocker_text: log.blocker_text,
                sort_order: log.sort_order,
                self_assessment_tags: log.self_assessment_tags,
              }];
            });

          // Part B: active tasks not already in the saved record — append as blank rows.
          const loggedTaskIds = new Set(rec.daily_work_logs.map((l) => l.task_id));
          const newBlankRows = activeTasks
            .filter((t) => !loggedTaskIds.has(t.id))
            .map(taskToBlankLog);

          setWorkLogs([...savedLogRows, ...newBlankRows]);
        } else {
          setWorkLogs(activeTasks.map(taskToBlankLog));
        }

        if (absences.length > 0) {
          setExistingAbsence(absences[0]);
          setIsAbsenceMode(true);
          setAbsenceType(absences[0].absence_type.id);
        }

        const activeGrant = grants.find((g) => g.revoked_at === null);
        setUnlockGrant(activeGrant ?? null);
      } catch {
        setError('Failed to load form data.');
      } finally {
        setLoading(false);
      }
    })();
  }, [recordDate]);

  const removeLog = useCallback((index: number) => {
    isDirty.current = true;
    setWorkLogs((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const moveLog = useCallback((index: number, direction: 'up' | 'down') => {
    setWorkLogs((prev) => {
      const next = [...prev];
      const swapIdx = direction === 'up' ? index - 1 : index + 1;
      [next[index], next[swapIdx]] = [next[swapIdx], next[index]];
      return next;
    });
  }, []);

  // Silently persist the DailyRecord after a task mutation.
  // Accepts an explicit snapshot so callers pass the already-updated logs
  // rather than racing against the async state update.
  // Gated on validatePrimaryTags — silently skips if tags are incomplete.
  const autoSaveRecord = useCallback(async (logsSnapshot: DailyWorkLogFormEntry[]) => {
    if (!isEditable || saving) return;
    if (validatePrimaryTags(logsSnapshot) !== null) return;
    const payload = {
      day_load: dayLoad,
      day_note: dayNote || null,
      form_opened_at: formOpenedAt.current.toISOString(),
      daily_work_logs: logsSnapshot.map((l, i) => ({
        task_id: l.task_id,
        effort: l.effort,
        energy_type: l.energy_type,
        insight: l.insight,
        blocker_type_id: l.blocker_type_id,
        blocker_text: l.blocker_text,
        sort_order: i,
        self_assessment_tags: l.self_assessment_tags,
      })),
    };
    try {
      if (existingRecord) {
        await updateDailyRecord(existingRecord.id, payload);
      } else {
        const created = await createDailyRecord({
          record_date: recordDate,
          ...payload,
        });
        setExistingRecord(created);
      }
    } catch (e) {
      console.warn('[autoSave] DailyRecord auto-save failed:', e);
    }
  }, [isEditable, saving, dayLoad, dayNote, existingRecord, recordDate]);

  // Work log manipulation
  const updateLog = useCallback(
    (index: number, updated: Partial<DailyWorkLogFormEntry>) => {
      isDirty.current = true;
      const next = workLogs.map((l, i) => (i === index ? { ...l, ...updated } : l));
      setWorkLogs(next);
      void autoSaveRecord(next);
    },
    [workLogs, autoSaveRecord]
  );

  const handleTaskCreated = useCallback((task: Task) => {
    const next = [...workLogs, taskToBlankLog(task)];
    setWorkLogs(next);
    // Silently skipped: new row has no tags yet, validatePrimaryTags will fail
    void autoSaveRecord(next);
  }, [workLogs, autoSaveRecord]);

  const handleTaskUpdated = useCallback(
    (index: number, updated: Task) => {
      const next = workLogs.map((l, i) =>
        i === index ? { ...l, task: updated, task_id: updated.id } : l
      );
      setWorkLogs(next);
      void autoSaveRecord(next);
    },
    [workLogs, autoSaveRecord]
  );

  // Toggle absence mode
  const toggleAbsence = async () => {
    if (isAbsenceMode) {
      // Remove absence
      if (existingAbsence) {
        try {
          await deleteAbsence(
            existingAbsence.id,
            formOpenedAt.current.toISOString()
          );
          setExistingAbsence(null);
        } catch {
          setError('Failed to remove absence.');
          return;
        }
      }
      setIsAbsenceMode(false);
    } else {
      // Switch to absence mode — show controls
      setIsAbsenceMode(true);
    }
  };

  // Save absence directly
  const saveAbsence = async () => {
    if (existingAbsence) return; // already saved
    setSaving(true);
    setError(null);
    try {
      const abs = await createAbsence({
        record_date: recordDate,
        absence_type_id: absenceType,
        form_opened_at: formOpenedAt.current.toISOString(),
      });
      setExistingAbsence(abs);
      setSuccessMsg('Absence recorded.');
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to record absence.';
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  // Save daily record
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isEditable) return;

    const tagErr = validatePrimaryTags(workLogs);
    if (tagErr) {
      setError(tagErr);
      return;
    }

    // Show confirmation modal before saving
    setShowConfirmCheck(true);
  };

  const confirmCheck = async () => {
    setShowConfirmCheck(false);
    if (!isEditable) return;

    setSaving(true);
    setError(null);
    setSuccessMsg(null);

    const payload = {
      day_load: dayLoad,
      day_note: dayNote || null,
      form_opened_at: formOpenedAt.current.toISOString(),
      daily_work_logs: workLogs.map((l, i) => ({
        task_id: l.task_id,
        effort: l.effort,
        energy_type: l.energy_type,
        insight: l.insight,
        blocker_type_id: l.blocker_type_id,
        blocker_text: l.blocker_text,
        sort_order: i,
        self_assessment_tags: l.self_assessment_tags,
      })),
    };

    try {
      if (existingRecord) {
        await updateDailyRecord(existingRecord.id, payload);
      } else {
        const created = await createDailyRecord({
          record_date: recordDate,
          ...payload,
        });
        setExistingRecord(created);
      }
      setSuccessMsg('Record checked.');
      setChecked(true);
      isDirty.current = false;
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to save record.';
      if (msg.toLowerCase().includes('edit window')) {
        setError('The edit window is closed. Ask your leader for an unlock if needed.');
      } else {
        setError(msg);
      }
    } finally {
      setSaving(false);
    }
  };

  // Navigate dates
  const goToDate = (offset: number) => {
    if (isDirty.current && !window.confirm('You have unsaved changes. Leave anyway?')) return;
    const d = new Date(recordDate);
    d.setDate(d.getDate() + offset);
    navigate(`/daily/${d.toISOString().slice(0, 10)}`);
  };

  const handleCancel = () => {
    if (isDirty.current && !window.confirm('You have unsaved changes. Leave anyway?')) return;
    navigate('/');
  };

  const s = styles;

  if (loading) return <div style={s.page}>Loading…</div>;

  return (
    <div style={s.page}>
      {/* Date header */}
      <div style={s.dateHeader}>
        <button type="button" onClick={() => goToDate(-1)} style={s.navBtn}>
          ◀
        </button>
        <input
          type="date"
          value={recordDate}
          onChange={(e) => { if (e.target.value) navigate(`/daily/${e.target.value}`); }}
          style={s.datePicker}
        />
        <button
          type="button"
          onClick={() => goToDate(1)}
          style={s.navBtn}
        >
          ▶
        </button>
        <button
          type="button"
          onClick={() => navigate('/daily')}
          style={{ ...s.navBtn, marginLeft: '1rem' }}
        >
          Today
        </button>
        <button
          type="button"
          onClick={handleCancel}
          style={{ ...s.navBtn, marginLeft: 'auto', color: 'var(--text-secondary)' }}
        >
          ✕ Cancel
        </button>
      </div>

      {/* Edit window banner */}
      {windowState === 'grace' && (
        <div style={{ ...s.banner, background: 'var(--warning-bg)', border: '1px solid var(--warning)', color: 'var(--text-h)' }}>
          ⚠ Grace period — submit before the edit window closes.
        </div>
      )}
      {windowState === 'locked' && !unlockGrant && (
        <div style={{ ...s.banner, background: 'var(--error-bg)', border: '1px solid var(--error)', color: 'var(--error)' }}>
          🔒 Edit window closed. Contact your leader to request an unlock.
        </div>
      )}
      {windowState === 'locked' && unlockGrant && (
        <div style={{ ...s.banner, background: 'var(--success-bg)', border: '1px solid var(--success)', color: 'var(--success)' }}>
          🔓 Unlock granted by your leader.
        </div>
      )}

      {/* Absence toggle */}
      <div style={s.absenceRow}>
        <button
          type="button"
          onClick={toggleAbsence}
          disabled={!!existingRecord}
          style={{
            ...s.absenceToggle,
            background: isAbsenceMode ? 'var(--primary)' : 'var(--border)',
            color: isAbsenceMode ? '#fff' : 'var(--text-h)',
          }}
        >
          {isAbsenceMode ? '✓ Marked as Absence' : 'Mark as Absence'}
        </button>
        {isAbsenceMode && !existingAbsence && (
          <>
            <select
              value={absenceType}
              onChange={(e) => setAbsenceType(e.target.value)}
              style={{ ...s.select, marginLeft: '0.75rem', width: 'auto' }}
            >
              {absenceTypes.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
            <button
              type="button"
              onClick={saveAbsence}
              disabled={saving || !isEditable}
              style={{ ...s.saveBtn, marginLeft: '0.75rem' }}
            >
              {saving ? 'Saving…' : 'Save Absence'}
            </button>
          </>
        )}
        {existingAbsence && (
          <span style={{ marginLeft: '0.75rem', color: 'var(--text-secondary)' }}>
            Type: {existingAbsence.absence_type.name}
          </span>
        )}
      </div>

      {/* Daily record form (hidden when absence mode is active & confirmed) */}
      {!existingAbsence && !isAbsenceMode && (
        <form onSubmit={handleSubmit}>
          {/* Work Logs (one per active task) */}
          <div style={s.sectionHeader}>
            <h3 style={s.sectionTitle}>Today's Tasks</h3>
            <button
              type="button"
              onClick={() => setShowTaskModal(true)}
              disabled={!isEditable}
              style={s.addTaskBtn}
            >
              + New Task
            </button>
          </div>
          <p style={s.sectionHint}>
            Log effort for each active task. Mark done when finished.
          </p>

          {workLogs.length === 0 && (
            <p style={{ color: 'var(--text-secondary)', fontStyle: 'italic', marginBottom: '1rem' }}>
              No active tasks. Create a task or skip rows for tasks not touched today.
            </p>
          )}

          {(() => {
            // Build ordered list of distinct category IDs (first-seen order)
            const seenCatIds: string[] = [];
            for (const log of workLogs) {
              const catId = log.task.category_id ?? '__unknown__';
              if (!seenCatIds.includes(catId)) seenCatIds.push(catId);
            }
            return seenCatIds.map((catId) => {
              const group = workLogs.filter(
                (l) => (l.task.category_id ?? '__unknown__') === catId
              );
              const catName =
                catId === '__unknown__'
                  ? 'Other'
                  : (categories.find((c) => c.id === catId)?.name ?? 'Other');
              const color =
                catId === '__unknown__'
                  ? CATEGORY_FALLBACK_COLOR
                  : (categoryColorMap.get(catId) ?? CATEGORY_FALLBACK_COLOR);
              return (
                <div key={catId}>
                  {/* Category group header */}
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    margin: '1rem 0 0.4rem',
                  }}>
                    <span style={{
                      width: '12px',
                      height: '12px',
                      borderRadius: '3px',
                      background: color,
                      flexShrink: 0,
                    }} />
                    <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-body)' }}>
                      {catName}
                    </span>
                  </div>
                  {group.map((log) => {
                    const index = workLogs.indexOf(log);
                    return (
                      <WorkLogRow
                        key={log._key}
                        log={log}
                        index={index}
                        totalLogs={workLogs.length}
                        tags={tags}
                        blockerTypes={blockerTypes}
                        isEditable={isEditable && log.task.is_active}
                        onChange={updateLog}
                        onRemove={removeLog}
                        onMoveUp={(i) => moveLog(i, 'up')}
                        onMoveDown={(i) => moveLog(i, 'down')}
                        onTaskUpdated={handleTaskUpdated}
                        accentColor={color}
                      />
                    );
                  })}
                </div>
              );
            });
          })()}

          {/* Battery % (private) */}
          <div style={s.metaSection}>
            <div style={s.fieldRow}>
              <label style={s.label}>
                Battery % <span style={s.privateLabel}>[private]</span>
              </label>
              <div style={{ display: 'flex', gap: '0.4rem', margin: '0 0.75rem' }}>
                {[0, 25, 50, 75, 100].map((pct) => (
                  <button
                    key={pct}
                    type="button"
                    disabled={!isEditable}
                    onClick={() => { isDirty.current = true; setDayLoad(pct); }}
                    style={{
                      padding: '0.25rem 0.6rem',
                      borderRadius: '4px',
                      border: '1px solid var(--border)',
                      cursor: isEditable ? 'pointer' : 'not-allowed',
                      background: dayLoad === pct ? 'var(--accent)' : 'var(--bg-secondary)',
                      color: dayLoad === pct ? '#fff' : 'var(--text-body)',
                      fontWeight: dayLoad === pct ? 700 : 400,
                    }}
                  >
                    {pct}%
                  </button>
                ))}
              </div>
            </div>

            {/* Day note */}
            <div style={{ ...s.fieldRow, alignItems: 'flex-start', marginTop: '0.5rem' }}>
              <label style={s.label}>Day note</label>
              <textarea
                value={dayNote}
                onChange={(e) => { isDirty.current = true; setDayNote(e.target.value); }}
                disabled={!isEditable}
                rows={3}
                style={{ ...s.input, resize: 'vertical' }}
                placeholder="Optional notes for the day (visible to your leader)"
              />
            </div>
          </div>

          {/* Feedback */}
          {error && <p style={s.errorMsg}>{error}</p>}
          {successMsg && <p style={s.successMsg}>{successMsg}</p>}

          {/* Submit */}
          <div style={s.submitRow}>
            {checked ? (
              <>
                <span style={s.checkedBadge}>✓ Checked</span>
                {windowState !== 'locked' && (
                  <button
                    type="button"
                    onClick={() => setChecked(false)}
                    style={{ ...s.navBtn, marginLeft: '0.75rem' }}
                  >
                    Re-edit
                  </button>
                )}
              </>
            ) : (
              <button
                type="submit"
                disabled={saving || !isEditable}
                style={s.saveBtn}
              >
                {saving ? 'Checking…' : 'Check'}
              </button>
            )}
          </div>
        </form>
      )}

      {/* Task create modal — rendered outside <form> to avoid nested form HTML */}
      <TaskCreateModal
        open={showTaskModal}
        onClose={() => setShowTaskModal(false)}
        onCreated={handleTaskCreated}
        categories={categories}
        projects={projects}
        blockerTypes={blockerTypes}
        onProjectCreated={(project) => setProjects((prev) => [...prev, project])}
      />

      {/* Check confirmation modal */}
      {showConfirmCheck && (
        <div style={s.modalOverlay}>
          <div style={s.modalBox}>
            <h3 style={{ margin: '0 0 0.75rem', fontSize: '1rem' }}>Confirm Check</h3>
            <p style={{ margin: '0 0 1.25rem', color: 'var(--text-body)', fontSize: '0.9rem' }}>
              Submit today’s record? The form will be locked until you click Re-edit.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button
                type="button"
                onClick={() => setShowConfirmCheck(false)}
                style={s.navBtn}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmCheck}
                style={s.saveBtn}
              >
                Confirm Check
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Absence confirmed — show summary */}
      {existingAbsence && (
        <div style={s.absenceSummary}>
          <p>
            This day is recorded as an absence (
            <strong>{existingAbsence.absence_type.name}</strong>).
          </p>
          {isEditable && (
            <button
              type="button"
              onClick={toggleAbsence}
              style={{ ...s.navBtn, marginTop: '0.5rem', color: 'var(--error)' }}
            >
              Remove absence
            </button>
          )}
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Minimal inline styles
// ---------------------------------------------------------------------------
const styles: Record<string, React.CSSProperties> = {
  page: { maxWidth: '800px', margin: '0 auto' },
  dateHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    marginBottom: '1rem',
  },
  dateTitle: { margin: 0, fontSize: '1.25rem', fontWeight: 700 },
  datePicker: {
    fontSize: '1rem',
    fontWeight: 700,
    border: '1px solid #cbd5e0',
    borderRadius: '4px',
    padding: '0.15rem 0.4rem',
    cursor: 'pointer',
    background: 'none',
  },
  navBtn: {
    padding: '0.25rem 0.5rem',
    background: 'none',
    border: '1px solid var(--border-strong)',
    borderRadius: '4px',
    cursor: 'pointer',
    color: 'var(--text-h)',
  },
  banner: {
    padding: '0.5rem 1rem',
    borderRadius: '6px',
    marginBottom: '1rem',
    fontWeight: 500,
  },
  absenceRow: {
    display: 'flex',
    alignItems: 'center',
    marginBottom: '1.25rem',
    flexWrap: 'wrap',
    gap: '0.5rem',
  },
  absenceToggle: {
    padding: '0.4rem 0.8rem',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 500,
  },
  absenceSummary: {
    background: 'var(--bg-info)',
    border: '1px solid var(--border)',
    borderRadius: '6px',
    padding: '1rem',
  },
  sectionHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '0.5rem',
  },
  sectionTitle: { margin: 0, fontSize: '1rem', fontWeight: 600 },
  sectionHint: { color: 'var(--text-secondary)', fontSize: '0.8rem', margin: '0 0 0.75rem' },
  addTaskBtn: {
    padding: '0.3rem 0.75rem',
    background: 'var(--success)',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 500,
  },
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
    marginBottom: '0.5rem',
  },
  label: { fontSize: '0.8rem', color: 'var(--text-body)', minWidth: '7rem' },
  input: {
    border: '1px solid var(--border-strong)',
    borderRadius: '4px',
    padding: '0.3rem 0.5rem',
    fontSize: '0.875rem',
    flex: 1,
    minWidth: '12rem',
    background: 'var(--bg)',
    color: 'var(--text-h)',
  },
  select: {
    border: '1px solid var(--border-strong)',
    borderRadius: '4px',
    padding: '0.3rem 0.5rem',
    fontSize: '0.875rem',
    background: 'var(--bg)',
    color: 'var(--text-h)',
  },
  metaSection: {
    background: 'var(--bg-tertiary)',
    border: '1px solid var(--border)',
    borderRadius: '8px',
    padding: '1rem',
    marginTop: '1rem',
    marginBottom: '1rem',
  },
  privateLabel: { color: 'var(--text-secondary)', fontStyle: 'italic', fontSize: '0.75rem' },
  errorMsg: { color: 'var(--error)', marginBottom: '0.5rem' },
  successMsg: { color: 'var(--success)', marginBottom: '0.5rem' },
  submitRow: { display: 'flex', justifyContent: 'flex-end', marginTop: '0.5rem' },
  saveBtn: {
    padding: '0.5rem 1.5rem',
    background: 'var(--primary)',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 600,
    fontSize: '0.9rem',
  },
  checkedBadge: {
    padding: '0.4rem 1rem',
    background: '#c6f6d5',
    color: '#276749',
    borderRadius: '6px',
    fontWeight: 600,
    fontSize: '0.9rem',
    border: '1px solid #9ae6b4',
  },
  modalOverlay: {
    position: 'fixed' as const,
    inset: 0,
    background: 'rgba(0,0,0,0.4)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  modalBox: {
    background: 'var(--bg)',
    borderRadius: '10px',
    padding: '1.5rem',
    width: '360px',
    maxWidth: '90vw',
    boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
  },
};
