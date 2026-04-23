import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  createDailyRecord,
  updateDailyRecord,
  getDailyRecords,
  getUnlockGrants,
  checkDailyRecord,
  uncheckDailyRecord,
  getTeamsDraft,
  getEmailDraft,
  sendTeamsMessage,
  sendEmail,
} from '../api/dailyRecords';
import { getActiveTasks, getTask } from '../api/tasks';
import { getCategories, getSelfAssessmentTags, getBlockerTypes } from '../api/categories';
import { getProjects } from '../api/projects';
import { WorkLogCard } from '../components/tasks/WorkLogCard';
import { WorkLogEditModal } from '../components/tasks/WorkLogEditModal';
import { TaskCreateModal } from '../components/tasks/TaskCreateModal';
import type {
  Category,
  SelfAssessmentTag,
  BlockerType,
  Project,
  Task,
  DailyRecord,
  DailyWorkLogFormEntry,
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
  const [unlockGrant, setUnlockGrant] = useState<UnlockGrant | null>(null);

  // Form fields
  const [workLogs, setWorkLogs] = useState<DailyWorkLogFormEntry[]>([]);
  const [dayLoad, setDayLoad] = useState(50);
  const [dayInsight, setDayInsight] = useState('');

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [showConfirmCheck, setShowConfirmCheck] = useState(false);

  // Send panel state
  const [teamsSentAt, setTeamsSentAt] = useState<string | null>(null);
  const [emailSentAt, setEmailSentAt] = useState<string | null>(null);
  const [showTeamsModal, setShowTeamsModal] = useState(false);
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [draftSubject, setDraftSubject] = useState('');
  const [draftBody, setDraftBody] = useState('');
  const [sendError, setSendError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  // Task create modal
  const [showTaskModal, setShowTaskModal] = useState(false);

  // Work log edit modal
  const [editingKey, setEditingKey] = useState<string | null>(null);

  // Dirty tracking — set on first user interaction, reset after successful save
  const isDirty = useRef(false);

  // Edit window
  const windowState = useMemo(
    () => getEditWindowState(recordDate, formOpenedAt.current),
    [recordDate]
  );
  // Use server-authoritative is_locked when a record exists; fall back to
  // client-side deadline computation only before the first save.
  const isLocked = existingRecord
    ? existingRecord.is_locked
    : windowState === 'locked' && !unlockGrant;
  const isEditable = !isLocked && !checked;

  // Category → accent color map (stable across renders, cycles through palette)
  const categoryColorMap = useMemo(() => getColorMap(categories), [categories]);

  // Load reference data + existing record
  useEffect(() => {
    setLoading(true);
    setError(null);
    // Reset all date-specific state so stale data from a previous date never lingers.
    setExistingRecord(null);
    setUnlockGrant(null);
    setWorkLogs([]);
    setDayLoad(50);
    setDayInsight('');
    setSuccessMsg(null);
    setChecked(false);
    setShowConfirmCheck(false);
    setTeamsSentAt(null);
    setEmailSentAt(null);
    setSendError(null);
    isDirty.current = false;
    (async () => {
      try {
        const [cats, tagList, btList, projs, records, grants, activeTasks] =
          await Promise.all([
            getCategories(),
            getSelfAssessmentTags(),
            getBlockerTypes(),
            getProjects(),
            getDailyRecords({ date: recordDate }),
            getUnlockGrants({ record_date: recordDate }),
            getActiveTasks(),
          ]);
        setCategories(cats);
        setTags(tagList);
        setBlockerTypes(btList);
        setProjects(projs);

        if (records.length > 0) {
          const rec = records[0];
          setExistingRecord(rec);
          setChecked(rec.is_checked);
          setTeamsSentAt(rec.teams_message_sent_at);
          setEmailSentAt(rec.email_sent_at);
          setDayLoad(rec.day_load ?? 50);
          setDayInsight(rec.day_insight ?? '');

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
      day_insight: dayInsight || null,
      form_opened_at: formOpenedAt.current.toISOString(),
      daily_work_logs: logsSnapshot.map((l, i) => ({
        task_id: l.task_id,
        effort: l.effort,
        energy_type: l.energy_type,
        insight: l.insight,
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
  }, [isEditable, saving, dayLoad, dayInsight, existingRecord, recordDate]);

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

  const handleModalSave = useCallback(
    async (updated: DailyWorkLogFormEntry) => {
      const next = workLogs.map((l) => (l._key === updated._key ? updated : l));
      setWorkLogs(next);
      await autoSaveRecord(next);
      setEditingKey(null);
    },
    [workLogs, autoSaveRecord]
  );

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
      day_insight: dayInsight || null,
      form_opened_at: formOpenedAt.current.toISOString(),
      daily_work_logs: workLogs.map((l, i) => ({
        task_id: l.task_id,
        effort: l.effort,
        energy_type: l.energy_type,
        insight: l.insight,
        blocker_text: l.blocker_text,
        sort_order: i,
        self_assessment_tags: l.self_assessment_tags,
      })),
    };

    try {
      let savedRecord: DailyRecord;
      if (existingRecord) {
        savedRecord = await updateDailyRecord(existingRecord.id, payload);
      } else {
        savedRecord = await createDailyRecord({
          record_date: recordDate,
          ...payload,
        });
      }
      // Call the real check API
      const checkedRecord = await checkDailyRecord(
        savedRecord.id,
        formOpenedAt.current.toISOString(),
      );
      setExistingRecord(checkedRecord);
      setChecked(checkedRecord.is_checked);
      setTeamsSentAt(checkedRecord.teams_message_sent_at);
      setEmailSentAt(checkedRecord.email_sent_at);
      setSuccessMsg('Record checked.');
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

  const handleUncheck = async () => {
    if (!existingRecord) return;
    setError(null);
    try {
      const updated = await uncheckDailyRecord(
        existingRecord.id,
        formOpenedAt.current.toISOString(),
      );
      setExistingRecord(updated);
      setChecked(updated.is_checked);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 423) {
        setError('The edit window is closed — cannot uncheck. Ask your leader for an unlock.');
      } else {
        setError('Failed to uncheck record.');
      }
    }
  };

  const openTeamsModal = async () => {
    if (!existingRecord) return;
    setSendError(null);
    try {
      const draft = await getTeamsDraft(existingRecord.id);
      setDraftSubject(draft.subject);
      setDraftBody(draft.body);
      setShowTeamsModal(true);
    } catch {
      setSendError('Failed to load Teams draft.');
    }
  };

  const openEmailModal = async () => {
    if (!existingRecord) return;
    setSendError(null);
    try {
      const draft = await getEmailDraft(existingRecord.id);
      setDraftSubject(draft.subject);
      setDraftBody(draft.body);
      setShowEmailModal(true);
    } catch {
      setSendError('Failed to load email draft.');
    }
  };

  const handleSendTeams = async () => {
    if (!existingRecord) return;
    setSending(true);
    setSendError(null);
    try {
      const result = await sendTeamsMessage(existingRecord.id, {
        subject: draftSubject,
        body: draftBody,
      });
      setTeamsSentAt(result.sent_at);
      setShowTeamsModal(false);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number; data?: { detail?: string } } })?.response?.status;
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      if (status === 503) {
        setSendError('Teams channel not configured — contact your admin.');
      } else if (status === 422) {
        setSendError('MS365 account not connected — set up in Profile Settings.');
      } else if (status === 409) {
        setSendError('Already sent.');
        setShowTeamsModal(false);
      } else {
        setSendError(detail ?? 'Failed to send Teams message.');
      }
    } finally {
      setSending(false);
    }
  };

  const handleSendEmail = async () => {
    if (!existingRecord) return;
    setSending(true);
    setSendError(null);
    try {
      const result = await sendEmail(existingRecord.id, {
        subject: draftSubject,
        body: draftBody,
      });
      setEmailSentAt(result.sent_at);
      setShowEmailModal(false);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number; data?: { detail?: string } } })?.response?.status;
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      if (status === 422) {
        setSendError('MS365 account not connected — set up in Profile Settings.');
      } else if (status === 409) {
        setSendError('Already sent.');
        setShowEmailModal(false);
      } else {
        setSendError(detail ?? 'Failed to send email.');
      }
    } finally {
      setSending(false);
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

      {/* Edit window banner — use server is_locked when record exists */}
      {!isLocked && windowState === 'grace' && (
        <div style={{ ...s.banner, background: 'var(--warning-bg)', border: '1px solid var(--warning)', color: 'var(--text-h)' }}>
          ⚠ Grace period — submit before the edit window closes.
        </div>
      )}
      {isLocked && checked && (
        <div style={{ ...s.banner, background: 'var(--success-bg)', border: '1px solid var(--success)', color: 'var(--success)' }}>
          ✓ Checked and locked.
        </div>
      )}
      {isLocked && !checked && unlockGrant && (
        <div style={{ ...s.banner, background: 'var(--success-bg)', border: '1px solid var(--success)', color: 'var(--success)' }}>
          🔓 Unlock granted by your leader.
        </div>
      )}
      {isLocked && !checked && !unlockGrant && (
        <div style={{ ...s.banner, background: 'var(--error-bg)', border: '1px solid var(--error)', color: 'var(--error)' }}>
          🔒 Edit window closed. Contact your leader to request an unlock.
        </div>
      )}

      {/* Daily record form */}
      <form onSubmit={handleSubmit}>
          {/* Work Logs (one per active task) */}
          <div style={s.sectionHeader}>
            <h3 style={s.sectionTitle}>Today's Tasks</h3>
          </div>
          <p style={s.sectionHint}>
            Log effort for each active task. Click Edit to fill in details.
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
                      <WorkLogCard
                        key={log._key}
                        log={log}
                        index={index}
                        totalLogs={workLogs.length}
                        tags={tags}
                        isEditable={isEditable && log.task.is_active}
                        accentColor={color}
                        onEdit={() => setEditingKey(log._key)}
                        onRemove={removeLog}
                        onMoveUp={(i) => moveLog(i, 'up')}
                        onMoveDown={(i) => moveLog(i, 'down')}
                        onTaskUpdated={handleTaskUpdated}
                      />
                    );
                  })}
                </div>
              );
            });
          })()}

          {/* Ghost card — add a new task */}
          {isEditable && (
            <button
              type="button"
              onClick={() => setShowTaskModal(true)}
              style={s.ghostCard}
            >
              + New Task
            </button>
          )}

          {/* Battery % (private) */}
          <div style={s.metaSection}>
            <div style={s.fieldRow}>
              <label style={s.label}>
                Battery % <span style={s.privateLabel}>[private]</span>
              </label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', margin: '0 0.75rem', flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <datalist id="battery-ticks">
                    <option value="0" />
                    <option value="25" />
                    <option value="50" />
                    <option value="75" />
                    <option value="100" />
                  </datalist>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={25}
                    list="battery-ticks"
                    value={dayLoad}
                    disabled={!isEditable}
                    onChange={(e) => { isDirty.current = true; setDayLoad(Number(e.target.value)); }}
                    style={{ flex: 1, cursor: isEditable ? 'pointer' : 'not-allowed', accentColor: 'var(--accent)' }}
                  />
                  <span style={{ minWidth: '3rem', textAlign: 'right', fontWeight: 700, color: 'var(--accent)' }}>
                    {dayLoad}%
                  </span>
                </div>
              </div>
            </div>

            {/* Day Insight */}
            <div style={{ ...s.fieldRow, alignItems: 'flex-start', marginTop: '0.5rem' }}>
              <label style={s.label}>Day Insight</label>
              <textarea
                value={dayInsight}
                onChange={(e) => { isDirty.current = true; setDayInsight(e.target.value); }}
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
                {!isLocked && (
                  <button
                    type="button"
                    onClick={handleUncheck}
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

          {/* Post-check send panel */}
          {checked && existingRecord && (
            <div style={s.sendPanel}>
              <p style={{ margin: '0 0 0.5rem', fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-body)' }}>
                Share status
              </p>
              {sendError && <p style={s.errorMsg}>{sendError}</p>}
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {teamsSentAt ? (
                  <span style={s.sentBadge}>✓ Sent to Teams</span>
                ) : (
                  <button type="button" onClick={openTeamsModal} style={s.sendBtn}>
                    Send to Teams
                  </button>
                )}
                {emailSentAt ? (
                  <span style={s.sentBadge}>✓ Email sent</span>
                ) : (
                  <button type="button" onClick={openEmailModal} style={s.sendBtn}>
                    Send Email
                  </button>
                )}
              </div>
            </div>
          )}
        </form>

      {/* Work log edit modal */}
      {editingKey !== null && (() => {
        const editingLog = workLogs.find((l) => l._key === editingKey);
        if (!editingLog) return null;
        return (
          <WorkLogEditModal
            log={editingLog}
            tags={tags}
            blockerTypes={blockerTypes}
            onSave={handleModalSave}
            onClose={() => setEditingKey(null)}
          />
        );
      })()}

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

      {/* Teams message draft modal */}
      {showTeamsModal && (
        <div style={s.modalOverlay}>
          <div style={{ ...s.modalBox, width: '480px' }}>
            <h3 style={{ margin: '0 0 0.75rem', fontSize: '1rem' }}>Send to Teams</h3>
            {sendError && <p style={s.errorMsg}>{sendError}</p>}
            <div style={{ marginBottom: '0.5rem' }}>
              <label style={s.label}>Subject</label>
              <input
                type="text"
                value={draftSubject}
                onChange={(e) => setDraftSubject(e.target.value)}
                style={{ ...s.input, marginTop: '0.25rem' }}
              />
            </div>
            <div style={{ marginBottom: '1rem' }}>
              <label style={s.label}>Body</label>
              <textarea
                value={draftBody}
                onChange={(e) => setDraftBody(e.target.value)}
                rows={8}
                style={{ ...s.input, resize: 'vertical', marginTop: '0.25rem' }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button type="button" onClick={() => { setShowTeamsModal(false); setSendError(null); }} style={s.navBtn}>
                Cancel
              </button>
              <button type="button" onClick={handleSendTeams} disabled={sending} style={s.saveBtn}>
                {sending ? 'Sending\u2026' : 'Send'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Email draft modal */}
      {showEmailModal && (
        <div style={s.modalOverlay}>
          <div style={{ ...s.modalBox, width: '480px' }}>
            <h3 style={{ margin: '0 0 0.75rem', fontSize: '1rem' }}>Send Email</h3>
            {sendError && <p style={s.errorMsg}>{sendError}</p>}
            <div style={{ marginBottom: '0.5rem' }}>
              <label style={s.label}>Subject</label>
              <input
                type="text"
                value={draftSubject}
                onChange={(e) => setDraftSubject(e.target.value)}
                style={{ ...s.input, marginTop: '0.25rem' }}
              />
            </div>
            <div style={{ marginBottom: '1rem' }}>
              <label style={s.label}>Body</label>
              <textarea
                value={draftBody}
                onChange={(e) => setDraftBody(e.target.value)}
                rows={8}
                style={{ ...s.input, resize: 'vertical', marginTop: '0.25rem' }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button type="button" onClick={() => { setShowEmailModal(false); setSendError(null); }} style={s.navBtn}>
                Cancel
              </button>
              <button type="button" onClick={handleSendEmail} disabled={sending} style={s.saveBtn}>
                {sending ? 'Sending\u2026' : 'Send'}
              </button>
            </div>
          </div>
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
  ghostCard: {
    display: 'block',
    width: '100%',
    padding: '0.6rem 1rem',
    marginBottom: '0.5rem',
    background: 'transparent',
    border: '2px dashed var(--border-strong)',
    borderRadius: '8px',
    cursor: 'pointer',
    color: 'var(--text-secondary)',
    fontSize: '0.875rem',
    fontWeight: 500,
    textAlign: 'left' as const,
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
  sendPanel: {
    marginTop: '1rem',
    padding: '0.75rem 1rem',
    background: 'var(--bg-tertiary)',
    border: '1px solid var(--border)',
    borderRadius: '8px',
  },
  sendBtn: {
    padding: '0.35rem 0.9rem',
    background: 'var(--accent)',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 500,
    fontSize: '0.85rem',
  },
  sentBadge: {
    padding: '0.35rem 0.9rem',
    background: '#c6f6d5',
    color: '#276749',
    borderRadius: '6px',
    fontWeight: 600,
    fontSize: '0.85rem',
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
