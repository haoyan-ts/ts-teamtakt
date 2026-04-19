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
import { getActiveTasks } from '../api/tasks';
import { getCategories, getSelfAssessmentTags, getBlockerTypes } from '../api/categories';
import { getProjects } from '../api/projects';
import { WorkLogRow } from '../components/tasks/WorkLogRow';
import { TaskCreateModal } from '../components/tasks/TaskCreateModal';
import type {
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
    work_note: null,
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

  // Record state
  const [existingRecord, setExistingRecord] = useState<DailyRecord | null>(null);
  const [existingAbsence, setExistingAbsence] = useState<Absence | null>(null);
  const [unlockGrant, setUnlockGrant] = useState<UnlockGrant | null>(null);

  // Form fields
  const [isAbsenceMode, setIsAbsenceMode] = useState(false);
  const [absenceType, setAbsenceType] = useState<string>('holiday');
  const [workLogs, setWorkLogs] = useState<DailyWorkLogFormEntry[]>([]);
  const [dayLoad, setDayLoad] = useState(3);
  const [dayNote, setDayNote] = useState('');

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Task create modal
  const [showTaskModal, setShowTaskModal] = useState(false);

  // Edit window
  const windowState = useMemo(
    () => getEditWindowState(recordDate, formOpenedAt.current),
    [recordDate]
  );
  const isEditable = windowState !== 'locked' || !!unlockGrant;

  // Load reference data + existing record
  useEffect(() => {
    setLoading(true);
    setError(null);
    // Reset all date-specific state so stale data from a previous date never lingers.
    setExistingRecord(null);
    setExistingAbsence(null);
    setUnlockGrant(null);
    setIsAbsenceMode(false);
    setAbsenceType('holiday');
    setWorkLogs([]);
    setDayLoad(3);
    setDayNote('');
    setSuccessMsg(null);
    Promise.all([
      getCategories(),
      getSelfAssessmentTags(),
      getBlockerTypes(),
      getProjects(),
      getDailyRecords({ date: recordDate }),
      getAbsences({ start_date: recordDate, end_date: recordDate }),
      getUnlockGrants({ record_date: recordDate }),
      getActiveTasks(),
    ])
      .then(([cats, tagList, btList, projs, records, absences, grants, activeTasks]) => {
        setCategories(cats);
        setTags(tagList);
        setBlockerTypes(btList);
        setProjects(projs);

        if (records.length > 0) {
          const rec = records[0];
          setExistingRecord(rec);
          setDayLoad(rec.day_load ?? 3);
          setDayNote(rec.day_note ?? '');

          const logsByTaskId = new Map(
            rec.daily_work_logs.map((l) => [l.task_id, l])
          );
          const rows: DailyWorkLogFormEntry[] = activeTasks.map((task) => {
            const existing = logsByTaskId.get(task.id);
            if (existing) {
              return {
                _key: newKey(),
                task,
                task_id: existing.task_id,
                effort: existing.effort,
                work_note: existing.work_note,
                blocker_type_id: existing.blocker_type_id,
                blocker_text: existing.blocker_text,
                sort_order: existing.sort_order,
                self_assessment_tags: existing.self_assessment_tags,
              };
            }
            return taskToBlankLog(task);
          });
          setWorkLogs(rows);
        } else {
          setWorkLogs(activeTasks.map(taskToBlankLog));
        }

        if (absences.length > 0) {
          setExistingAbsence(absences[0]);
          setIsAbsenceMode(true);
          setAbsenceType(absences[0].absence_type);
        }

        const activeGrant = grants.find((g) => g.revoked_at === null);
        setUnlockGrant(activeGrant ?? null);
      })
      .catch(() => setError('Failed to load form data.'))
      .finally(() => setLoading(false));
  }, [recordDate]);

  // Work log manipulation
  const updateLog = useCallback(
    (index: number, updated: Partial<DailyWorkLogFormEntry>) => {
      setWorkLogs((prev) => prev.map((l, i) => (i === index ? { ...l, ...updated } : l)));
    },
    []
  );

  const removeLog = useCallback((index: number) => {
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

  const handleTaskDone = useCallback((index: number) => {
    setWorkLogs((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleTaskCreated = useCallback((task: Task) => {
    setWorkLogs((prev) => [...prev, taskToBlankLog(task)]);
  }, []);

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
        absence_type: absenceType,
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
        work_note: l.work_note,
        blocker_type_id: l.blocker_type_id,
        blocker_text: l.blocker_text,
        sort_order: i,
        self_assessment_tags: l.self_assessment_tags,
      })),
    };

    try {
      if (existingRecord) {
        await updateDailyRecord(existingRecord.id, payload);
        setSuccessMsg('Record updated.');
      } else {
        const created = await createDailyRecord({
          record_date: recordDate,
          ...payload,
        });
        setExistingRecord(created);
        setSuccessMsg('Record saved.');
      }
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
    const d = new Date(recordDate);
    d.setDate(d.getDate() + offset);
    navigate(`/daily/${d.toISOString().slice(0, 10)}`);
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
        <h2 style={s.dateTitle}>{recordDate}</h2>
        <button
          type="button"
          onClick={() => goToDate(1)}
          disabled={recordDate >= todayISO}
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
              <option value="holiday">Public Holiday</option>
              <option value="exchanged_holiday">Exchanged Holiday</option>
              <option value="illness">Illness</option>
              <option value="other">Other</option>
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
            Type: {existingAbsence.absence_type.replace('_', ' ')}
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

          {workLogs.map((log, index) => (
            <WorkLogRow
              key={log._key}
              log={log}
              index={index}
              totalLogs={workLogs.length}
              tags={tags}
              blockerTypes={blockerTypes}
              isEditable={isEditable}
              onChange={updateLog}
              onRemove={removeLog}
              onMoveUp={(i) => moveLog(i, 'up')}
              onMoveDown={(i) => moveLog(i, 'down')}
              onTaskDone={handleTaskDone}
            />
          ))}

          <TaskCreateModal
            open={showTaskModal}
            onClose={() => setShowTaskModal(false)}
            onCreated={handleTaskCreated}
            categories={categories}
            projects={projects}
            blockerTypes={blockerTypes}
            onProjectCreated={(project) => setProjects((prev) => [...prev, project])}
          />

          {/* Day load (private) */}
          <div style={s.metaSection}>
            <div style={s.fieldRow}>
              <label style={s.label}>
                Day load (1–5) <span style={s.privateLabel}>[private]</span>
              </label>
              <input
                type="range"
                min={1}
                max={5}
                step={1}
                value={dayLoad}
                onChange={(e) => setDayLoad(Number(e.target.value))}
                disabled={!isEditable}
                style={{ width: '10rem', margin: '0 0.75rem' }}
              />
              <span style={{ fontWeight: 600, minWidth: '1.5rem' }}>{dayLoad}</span>
            </div>

            {/* Day note */}
            <div style={{ ...s.fieldRow, alignItems: 'flex-start', marginTop: '0.5rem' }}>
              <label style={s.label}>Day note</label>
              <textarea
                value={dayNote}
                onChange={(e) => setDayNote(e.target.value)}
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
            <button
              type="submit"
              disabled={saving || !isEditable}
              style={s.saveBtn}
            >
              {saving ? 'Saving…' : existingRecord ? 'Update Record' : 'Save Record'}
            </button>
          </div>
        </form>
      )}

      {/* Absence confirmed — show summary */}
      {existingAbsence && (
        <div style={s.absenceSummary}>
          <p>
            This day is recorded as an absence (
            <strong>{existingAbsence.absence_type.replace('_', ' ')}</strong>).
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
};
