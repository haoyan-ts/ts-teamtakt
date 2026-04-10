import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  createDailyRecord,
  updateDailyRecord,
  getDailyRecords,
  getCarryOverTasks,
  createAbsence,
  deleteAbsence,
  getAbsences,
  getUnlockGrants,
} from '../api/dailyRecords';
import { getCategories, getSelfAssessmentTags, getBlockerTypes } from '../api/categories';
import { getProjects, createProject } from '../api/projects';
import type {
  Category,
  SelfAssessmentTag,
  BlockerType,
  Project,
  DailyRecord,
  Absence,
  UnlockGrant,
  TaskFormEntry,
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
// Counter for unique task keys
// ---------------------------------------------------------------------------
let _keyCounter = 0;
const newKey = () => `task-${++_keyCounter}`;

const EMPTY_TASK = (): TaskFormEntry => ({
  _key: newKey(),
  category_id: '',
  sub_type_id: null,
  project_id: '',
  task_description: '',
  effort: 3,
  status: 'todo',
  blocker_type_id: null,
  blocker_text: null,
  carried_from_id: null,
  sort_order: 0,
  self_assessment_tags: [],
});

// ---------------------------------------------------------------------------
// Validation helper
// ---------------------------------------------------------------------------
function validatePrimaryTags(tasks: TaskFormEntry[]): string | null {
  for (const task of tasks) {
    const primaryCount = task.self_assessment_tags.filter((t) => t.is_primary).length;
    if (primaryCount === 0) return 'Each task must have exactly one primary self-assessment tag.';
    if (primaryCount > 1) return 'Each task must have exactly one primary self-assessment tag.';
  }
  return null;
}

// ---------------------------------------------------------------------------
// Sub-component: single task row
// ---------------------------------------------------------------------------
interface TaskRowProps {
  task: TaskFormEntry;
  index: number;
  totalTasks: number;
  categories: Category[];
  projects: Project[];
  tags: SelfAssessmentTag[];
  blockerTypes: BlockerType[];
  isEditable: boolean;
  onChange: (index: number, updated: Partial<TaskFormEntry>) => void;
  onRemove: (index: number) => void;
  onMoveUp: (index: number) => void;
  onMoveDown: (index: number) => void;
  onProjectCreated: (index: number, project: Project) => void;
}

const TaskRow = ({
  task,
  index,
  totalTasks,
  categories,
  projects,
  tags,
  blockerTypes,
  isEditable,
  onChange,
  onRemove,
  onMoveUp,
  onMoveDown,
  onProjectCreated,
}: TaskRowProps) => {
  const [showNewProject, setShowNewProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectScope, setNewProjectScope] = useState<'personal' | 'team' | 'cross_team'>('personal');
  const [projectSaving, setProjectSaving] = useState(false);
  const [projectError, setProjectError] = useState('');

  const submitNewProject = async () => {
    const name = newProjectName.trim();
    if (!name) { setProjectError('Name is required.'); return; }
    setProjectSaving(true);
    setProjectError('');
    try {
      const created = await createProject({ name, scope: newProjectScope });
      onProjectCreated(index, created);
      setShowNewProject(false);
      setNewProjectName('');
      setNewProjectScope('personal');
    } catch {
      setProjectError('Failed to create project. Please try again.');
    } finally {
      setProjectSaving(false);
    }
  };

  const selectedCategory = categories.find((c) => c.id === task.category_id);
  const subTypes = selectedCategory?.sub_types.filter((s) => s.is_active) ?? [];

  const handleTagToggle = (tagId: string) => {
    const existing = task.self_assessment_tags.find(
      (t) => t.self_assessment_tag_id === tagId
    );
    if (existing) {
      const remaining = task.self_assessment_tags.filter(
        (t) => t.self_assessment_tag_id !== tagId
      );
      // If the removed tag was primary, auto-promote the first remaining tag.
      const needsPromotion = existing.is_primary && remaining.length > 0;
      onChange(index, {
        self_assessment_tags: needsPromotion
          ? remaining.map((t, i) => ({ ...t, is_primary: i === 0 }))
          : remaining,
      });
    } else {
      onChange(index, {
        self_assessment_tags: [
          ...task.self_assessment_tags,
          { self_assessment_tag_id: tagId, is_primary: task.self_assessment_tags.length === 0 },
        ],
      });
    }
  };

  const handleSetPrimary = (tagId: string) => {
    onChange(index, {
      self_assessment_tags: task.self_assessment_tags.map((t) => ({
        ...t,
        is_primary: t.self_assessment_tag_id === tagId,
      })),
    });
  };

  const s = styles;

  return (
    <div style={s.taskCard}>
      {/* Header row: carry-over badge + reorder + remove */}
      <div style={s.taskHeader}>
        {task.carried_from_id && (
          <span style={s.carryBadge}>↩ Carried over</span>
        )}
        <div style={s.taskActions}>
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
            disabled={index === totalTasks - 1}
            onClick={() => onMoveDown(index)}
            style={s.iconBtn}
            title="Move down"
          >
            ▼
          </button>
          <button
            type="button"
            onClick={() => onRemove(index)}
            style={{ ...s.iconBtn, color: '#e53e3e' }}
            title="Remove task"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Category + Sub-type */}
      <div style={s.fieldRow}>
        <label style={s.label}>Category *</label>
        <select
          value={task.category_id}
          onChange={(e) =>
            onChange(index, { category_id: e.target.value, sub_type_id: null })
          }
          style={s.select}
          required
        >
          <option value="">— select —</option>
          {categories.filter((c) => c.is_active).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>

        {subTypes.length > 0 && (
          <>
            <label style={{ ...s.label, marginLeft: '0.75rem' }}>Sub-type</label>
            <select
              value={task.sub_type_id ?? ''}
              onChange={(e) =>
                onChange(index, { sub_type_id: e.target.value || null })
              }
              style={s.select}
            >
              <option value="">— none —</option>
              {subTypes.map((st) => (
                <option key={st.id} value={st.id}>
                  {st.name}
                </option>
              ))}
            </select>
          </>
        )}
      </div>

      {/* Project */}
      <div style={s.fieldRow}>
        <label style={s.label}>Project *</label>
        <select
          value={task.project_id}
          onChange={(e) => onChange(index, { project_id: e.target.value })}
          style={s.select}
          required
        >
          <option value="">— select —</option>
          {projects.filter((p) => p.is_active).map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.scope})
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => { setShowNewProject((v) => !v); setProjectError(''); }}
          style={{ ...s.iconBtn, marginLeft: '0.5rem', fontSize: '0.8rem', padding: '0.2rem 0.5rem' }}
          title="Create a new project"
        >
          + New
        </button>
      </div>
      {showNewProject && (
        <div style={{ marginBottom: '0.75rem', padding: '0.75rem', background: '#f7fafc', border: '1px solid #e2e8f0', borderRadius: '6px' }}>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <input
              style={{ ...s.input, flex: 1, minWidth: '140px' }}
              placeholder="Project name"
              value={newProjectName}
              onChange={(e) => { setNewProjectName(e.target.value); setProjectError(''); }}
              onKeyDown={(e) => e.key === 'Enter' && submitNewProject()}
              autoFocus
            />
            <select
              style={s.select}
              value={newProjectScope}
              onChange={(e) => setNewProjectScope(e.target.value as 'personal' | 'team' | 'cross_team')}
            >
              <option value="personal">Personal</option>
              <option value="team">Team</option>
              <option value="cross_team">Cross-team</option>
            </select>
            <button
              type="button"
              onClick={submitNewProject}
              disabled={projectSaving}
              style={{ padding: '0.3rem 0.75rem', background: '#3182ce', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 500, fontSize: '0.8rem' }}
            >
              {projectSaving ? 'Creating…' : 'Create'}
            </button>
            <button
              type="button"
              onClick={() => { setShowNewProject(false); setProjectError(''); }}
              style={{ padding: '0.3rem 0.5rem', background: '#edf2f7', border: '1px solid #e2e8f0', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}
            >
              Cancel
            </button>
          </div>
          {projectError && <p style={{ color: '#e53e3e', fontSize: '0.75rem', margin: '0.3rem 0 0' }}>{projectError}</p>}
        </div>
      )}

      {/* Description */}
      <div style={s.fieldRow}>
        <label style={s.label}>Description *</label>
        <input
          type="text"
          value={task.task_description}
          onChange={(e) => onChange(index, { task_description: e.target.value })}
          style={s.input}
          required
          placeholder="What did you work on?"
        />
      </div>

      {/* Effort + Status */}
      <div style={s.fieldRow}>
        <label style={s.label}>Effort (1–5) *</label>
        <select
          value={task.effort}
          onChange={(e) => onChange(index, { effort: Number(e.target.value) })}
          style={{ ...s.select, width: '5rem' }}
        >
          {[1, 2, 3, 4, 5].map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>

        <label style={{ ...s.label, marginLeft: '1rem' }}>Status *</label>
        <select
          value={task.status}
          onChange={(e) =>
            onChange(index, {
              status: e.target.value as TaskFormEntry['status'],
              blocker_type_id: e.target.value !== 'blocked' ? null : task.blocker_type_id,
              blocker_text: e.target.value !== 'blocked' ? null : task.blocker_text,
            })
          }
          style={s.select}
        >
          <option value="todo">Todo</option>
          <option value="running">Running</option>
          <option value="done">Done</option>
          <option value="blocked">Blocked</option>
        </select>
      </div>

      {/* Blocker fields (conditional) */}
      {task.status === 'blocked' && (
        <div style={s.blockerSection}>
          <div style={s.fieldRow}>
            <label style={s.label}>Blocker type</label>
            <select
              value={task.blocker_type_id ?? ''}
              onChange={(e) =>
                onChange(index, { blocker_type_id: e.target.value || null })
              }
              style={s.select}
            >
              <option value="">— select —</option>
              {blockerTypes.filter((bt) => bt.is_active).map((bt) => (
                <option key={bt.id} value={bt.id}>
                  {bt.name}
                </option>
              ))}
            </select>
          </div>
          <div style={s.fieldRow}>
            <label style={s.label}>Blocker details (private)</label>
            <input
              type="text"
              value={task.blocker_text ?? ''}
              onChange={(e) =>
                onChange(index, { blocker_text: e.target.value || null })
              }
              style={s.input}
              placeholder="Describe the blocker (not visible to other team members)"
            />
          </div>
        </div>
      )}

      {/* Self-assessment tags */}
      <div style={s.fieldRow}>
        <label style={s.label}>Self-assessment tags *</label>
        <div style={s.tagGroup}>
          {tags.filter((t) => t.is_active).map((tag) => {
            const ref = task.self_assessment_tags.find(
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
                    background: selected ? '#3182ce' : '#e2e8f0',
                    color: selected ? '#fff' : '#2d3748',
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
                  <span style={s.primaryIndicator} title="Primary tag">
                    ★
                  </span>
                )}
              </span>
            );
          })}
        </div>
      </div>
      {task.self_assessment_tags.filter((t) => t.is_primary).length === 0 &&
        task.self_assessment_tags.length > 0 && (
          <p style={s.tagError}>Select one tag as primary (★)</p>
        )}
      {task.self_assessment_tags.length === 0 && (
        <p style={s.tagError}>At least one tag required; select primary (★)</p>
      )}
    </div>
  );
};

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
  const [tasks, setTasks] = useState<TaskFormEntry[]>([]);
  const [dayLoad, setDayLoad] = useState(3);
  const [dayNote, setDayNote] = useState('');

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

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
    // Without this, navigating from a date that had isAbsenceMode=true would hide the
    // form (and its save button) on the newly-navigated-to date.
    setExistingRecord(null);
    setExistingAbsence(null);
    setUnlockGrant(null);
    setIsAbsenceMode(false);
    setAbsenceType('holiday');
    setTasks([]);
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
    ])
      .then(([cats, tagList, btList, projs, records, absences, grants]) => {
        setCategories(cats);
        setTags(tagList);
        setBlockerTypes(btList);
        setProjects(projs);

        if (records.length > 0) {
          const rec = records[0];
          setExistingRecord(rec);
          setDayLoad(rec.day_load ?? 3);
          setDayNote(rec.day_note ?? '');
          setTasks(
            rec.task_entries.map((te) => ({
              _key: newKey(),
              category_id: te.category_id,
              sub_type_id: te.sub_type_id,
              project_id: te.project_id,
              task_description: te.task_description,
              effort: te.effort,
              status: te.status as TaskFormEntry['status'],
              blocker_type_id: te.blocker_type_id,
              blocker_text: te.blocker_text,
              carried_from_id: te.carried_from_id,
              sort_order: te.sort_order,
              self_assessment_tags: te.self_assessment_tags,
            }))
          );
        } else if (dateParam === undefined || dateParam === todayISO) {
          // New record for today — pre-fill carry-over tasks
          getCarryOverTasks().then((carryOvers) => {
            setTasks(
              carryOvers.map((te) => ({
                _key: newKey(),
                category_id: te.category_id,
                sub_type_id: te.sub_type_id,
                project_id: te.project_id,
                task_description: te.task_description,
                effort: te.effort,
                status: te.status as TaskFormEntry['status'],
                blocker_type_id: te.blocker_type_id,
                blocker_text: te.blocker_text,
                carried_from_id: te.id, // reference original
                sort_order: te.sort_order,
                self_assessment_tags: te.self_assessment_tags,
              }))
            );
          });
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

  // Task manipulation
  const updateTask = useCallback(
    (index: number, updated: Partial<TaskFormEntry>) => {
      setTasks((prev) => prev.map((t, i) => (i === index ? { ...t, ...updated } : t)));
    },
    []
  );

  const removeTask = useCallback((index: number) => {
    setTasks((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const moveTask = useCallback((index: number, direction: 'up' | 'down') => {
    setTasks((prev) => {
      const next = [...prev];
      const swapIdx = direction === 'up' ? index - 1 : index + 1;
      [next[index], next[swapIdx]] = [next[swapIdx], next[index]];
      return next;
    });
  }, []);

  const addTask = () => setTasks((prev) => [...prev, EMPTY_TASK()]);

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

    const tagErr = validatePrimaryTags(tasks);
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
      task_entries: tasks.map((t, i) => ({
        category_id: t.category_id,
        sub_type_id: t.sub_type_id,
        project_id: t.project_id,
        task_description: t.task_description,
        effort: t.effort,
        status: t.status,
        blocker_type_id: t.blocker_type_id,
        blocker_text: t.blocker_text,
        carried_from_id: t.carried_from_id,
        sort_order: i,
        self_assessment_tags: t.self_assessment_tags,
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
        <div style={{ ...s.banner, background: '#f6ad55' }}>
          ⚠ Grace period — submit before the edit window closes.
        </div>
      )}
      {windowState === 'locked' && !unlockGrant && (
        <div style={{ ...s.banner, background: '#fc8181' }}>
          🔒 Edit window closed. Contact your leader to request an unlock.
        </div>
      )}
      {windowState === 'locked' && unlockGrant && (
        <div style={{ ...s.banner, background: '#68d391' }}>
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
            background: isAbsenceMode ? '#3182ce' : '#e2e8f0',
            color: isAbsenceMode ? '#fff' : '#2d3748',
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
          <span style={{ marginLeft: '0.75rem', color: '#718096' }}>
            Type: {existingAbsence.absence_type.replace('_', ' ')}
          </span>
        )}
      </div>

      {/* Daily record form (hidden when absence mode is active & confirmed) */}
      {!existingAbsence && !isAbsenceMode && (
        <form onSubmit={handleSubmit}>
          {/* Tasks */}
          <div style={s.sectionHeader}>
            <h3 style={s.sectionTitle}>Tasks</h3>
            <button
              type="button"
              onClick={addTask}
              disabled={!isEditable}
              style={s.addTaskBtn}
            >
              + Add Task
            </button>
          </div>

          {tasks.length === 0 && (
            <p style={{ color: '#718096', fontStyle: 'italic', marginBottom: '1rem' }}>
              No tasks yet. Add one above or carry over from yesterday.
            </p>
          )}

          {tasks.map((task, index) => (
            <TaskRow
              key={task._key}
              task={task}
              index={index}
              totalTasks={tasks.length}
              categories={categories}
              projects={projects}
              tags={tags}
              blockerTypes={blockerTypes}
              isEditable={isEditable}
              onChange={updateTask}
              onRemove={removeTask}
              onMoveUp={(i) => moveTask(i, 'up')}
              onMoveDown={(i) => moveTask(i, 'down')}
              onProjectCreated={(i, project) => {
                setProjects((prev) => [...prev, project]);
                updateTask(i, { project_id: project.id });
              }}
            />
          ))}

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
              style={{ ...s.navBtn, marginTop: '0.5rem', color: '#e53e3e' }}
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
    border: '1px solid #cbd5e0',
    borderRadius: '4px',
    cursor: 'pointer',
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
    background: '#ebf8ff',
    border: '1px solid #bee3f8',
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
  addTaskBtn: {
    padding: '0.3rem 0.75rem',
    background: '#48bb78',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 500,
  },
  taskCard: {
    border: '1px solid #e2e8f0',
    borderRadius: '8px',
    padding: '1rem',
    marginBottom: '0.75rem',
    background: '#f7fafc',
  },
  taskHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '0.5rem',
  },
  taskActions: { display: 'flex', gap: '0.25rem' },
  carryBadge: {
    background: '#ebf8ff',
    color: '#2b6cb0',
    fontSize: '0.75rem',
    padding: '0.1rem 0.4rem',
    borderRadius: '4px',
    fontWeight: 500,
  },
  iconBtn: {
    background: 'none',
    border: '1px solid #cbd5e0',
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
  label: { fontSize: '0.8rem', color: '#4a5568', minWidth: '7rem' },
  input: {
    border: '1px solid #cbd5e0',
    borderRadius: '4px',
    padding: '0.3rem 0.5rem',
    fontSize: '0.875rem',
    flex: 1,
    minWidth: '12rem',
  },
  select: {
    border: '1px solid #cbd5e0',
    borderRadius: '4px',
    padding: '0.3rem 0.5rem',
    fontSize: '0.875rem',
  },
  blockerSection: {
    background: '#fff5f5',
    border: '1px solid #fed7d7',
    borderRadius: '6px',
    padding: '0.5rem',
    marginBottom: '0.5rem',
  },
  tagGroup: { display: 'flex', flexWrap: 'wrap', gap: '0.35rem' },
  tagWrapper: { display: 'inline-flex', alignItems: 'center', gap: '2px' },
  tagBtn: {
    border: 'none',
    borderRadius: '4px',
    padding: '0.2rem 0.5rem',
    cursor: 'pointer',
    fontSize: '0.8rem',
  },
  primaryBtn: {
    background: 'none',
    border: 'none',
    color: '#d69e2e',
    cursor: 'pointer',
    fontSize: '0.8rem',
    padding: '0 2px',
  },
  primaryIndicator: { color: '#d69e2e', fontSize: '0.8rem' },
  tagError: { color: '#e53e3e', fontSize: '0.75rem', margin: '0.2rem 0 0' },
  metaSection: {
    background: '#f7fafc',
    border: '1px solid #e2e8f0',
    borderRadius: '8px',
    padding: '1rem',
    marginTop: '1rem',
    marginBottom: '1rem',
  },
  privateLabel: { color: '#718096', fontStyle: 'italic', fontSize: '0.75rem' },
  errorMsg: { color: '#e53e3e', marginBottom: '0.5rem' },
  successMsg: { color: '#38a169', marginBottom: '0.5rem' },
  submitRow: { display: 'flex', justifyContent: 'flex-end', marginTop: '0.5rem' },
  saveBtn: {
    padding: '0.5rem 1.5rem',
    background: '#3182ce',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 600,
    fontSize: '0.9rem',
  },
};
