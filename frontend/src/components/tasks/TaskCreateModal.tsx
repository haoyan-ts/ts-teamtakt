import { useState, useEffect, useRef } from 'react';
import { createProject } from '../../api/projects';
import { createTask, prefillFromGithubIssue } from '../../api/tasks';
import type {
  Category,
  Project,
  BlockerType,
  Task,
} from '../../types/dailyRecord';

interface TaskCreateModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: (task: Task) => void;
  categories: Category[];
  projects: Project[];
  blockerTypes: BlockerType[];
  /** Called when user creates a new project inline so parent can update its list */
  onProjectCreated: (project: Project) => void;
}

const GITHUB_URL_PATTERN = /^https?:\/\/github\.com\/[^/]+\/[^/]+\/issues\/\d+$/;

export const TaskCreateModal = ({
  open,
  onClose,
  onCreated,
  categories,
  projects,
  blockerTypes,
  onProjectCreated,
}: TaskCreateModalProps) => {
  const [title, setTitle] = useState('');
  const [githubUrl, setGithubUrl] = useState('');
  const [urlLocked, setUrlLocked] = useState(false); // true if editing an existing task with URL
  const [categoryId, setCategoryId] = useState('');
  const [subTypeId, setSubTypeId] = useState<string | null>(null);
  const [projectId, setProjectId] = useState('');
  const [status, setStatus] = useState<Task['status']>('todo');
  const [estimatedEffort, setEstimatedEffort] = useState<number | null>(null);
  const [blockerTypeId, setBlockerTypeId] = useState<string | null>(null);
  const [description, setDescription] = useState('');

  const [autofilling, setAutofilling] = useState(false);
  const [autofillMsg, setAutofillMsg] = useState<string | null>(null);
  const [autofillError, setAutofillError] = useState<string | null>(null);

  const [showNewProject, setShowNewProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectScope, setNewProjectScope] = useState<Project['scope']>('personal');
  const [projectSaving, setProjectSaving] = useState(false);
  const [projectError, setProjectError] = useState('');

  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const urlInputRef = useRef<HTMLInputElement>(null);

  // Reset form when modal opens
  useEffect(() => {
    if (open) {
      setTitle('');
      setGithubUrl('');
      setUrlLocked(false);
      setCategoryId('');
      setSubTypeId(null);
      setProjectId('');
      setStatus('todo');
      setEstimatedEffort(null);
      setBlockerTypeId(null);
      setDescription('');
      setAutofilling(false);
      setAutofillMsg(null);
      setAutofillError(null);
      setShowNewProject(false);
      setFormError(null);
    }
  }, [open]);

  const triggerAutofill = async (url: string) => {
    if (!GITHUB_URL_PATTERN.test(url)) return;
    setAutofilling(true);
    setAutofillMsg(null);
    setAutofillError(null);
    try {
      const result = await prefillFromGithubIssue(url);
      if (result.title) setTitle(result.title);
      if (result.category_id) { setCategoryId(result.category_id); setSubTypeId(null); }
      if (result.sub_type_id) setSubTypeId(result.sub_type_id);
      if (result.project_id) setProjectId(result.project_id);
      if (result.estimated_effort != null) setEstimatedEffort(result.estimated_effort);
      if (result.status) setStatus(result.status === 'done' ? 'done' : 'todo');
      if (result.blocker_type_id) setBlockerTypeId(result.blocker_type_id);
      setAutofillMsg('Auto-filled from GitHub Issue — please review.');
    } catch {
      setAutofillError('Could not fetch GitHub Issue. Check the URL and try again.');
    } finally {
      setAutofilling(false);
    }
  };

  const handleUrlBlur = () => {
    if (githubUrl.trim()) {
      triggerAutofill(githubUrl.trim());
    }
  };

  const submitNewProject = async () => {
    const name = newProjectName.trim();
    if (!name) { setProjectError('Name is required.'); return; }
    setProjectSaving(true);
    setProjectError('');
    try {
      const created = await createProject({ name, scope: newProjectScope });
      onProjectCreated(created);
      setProjectId(created.id);
      setShowNewProject(false);
      setNewProjectName('');
      setNewProjectScope('personal');
    } catch {
      setProjectError('Failed to create project. Please try again.');
    } finally {
      setProjectSaving(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanTitle = title.trim();
    if (!cleanTitle) { setFormError('Title is required.'); return; }
    if (!categoryId) { setFormError('Category is required.'); return; }
    if (!projectId) { setFormError('Project is required.'); return; }

    setSaving(true);
    setFormError(null);
    try {
      const task = await createTask({
        title: cleanTitle,
        description: description.trim() || null,
        project_id: projectId,
        category_id: categoryId,
        sub_type_id: subTypeId,
        status,
        estimated_effort: estimatedEffort,
        blocker_type_id: blockerTypeId,
        github_issue_url: githubUrl.trim() || null,
      });
      onCreated(task);
      onClose();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      if (detail?.includes('already linked') || detail?.includes('unique')) {
        setFormError('This GitHub Issue URL is already linked to another task.');
      } else {
        setFormError(detail ?? 'Failed to create task. Please try again.');
      }
    } finally {
      setSaving(false);
    }
  };

  const hasContent = !!(title || githubUrl || description || categoryId || projectId);

  const handleClose = () => {
    if (hasContent && !saving && !window.confirm('Discard unsaved task?')) return;
    onClose();
  };

  if (!open) return null;

  const selectedCategory = categories.find((c) => c.id === categoryId);
  const subTypes = selectedCategory?.sub_types.filter((s) => s.is_active) ?? [];
  const s = modalStyles;

  return (
    <div style={s.overlay} role="dialog" aria-modal="true" aria-label="Create new task">
      <div style={s.panel}>
        <div style={s.header}>
          <h3 style={s.title}>New Task</h3>
          <button type="button" onClick={handleClose} style={s.closeBtn} aria-label="Close">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {/* GitHub Issue URL */}
          <div style={s.fieldRow}>
            <label style={s.label}>GitHub Issue URL</label>
            {urlLocked ? (
              <div style={s.lockedUrl}>
                <span style={s.lockIcon}>🔒</span>
                <span>{githubUrl}</span>
              </div>
            ) : (
              <input
                ref={urlInputRef}
                type="url"
                value={githubUrl}
                onChange={(e) => { setGithubUrl(e.target.value); setAutofillError(null); }}
                onBlur={handleUrlBlur}
                style={s.input}
                placeholder="https://github.com/org/repo/issues/123"
                disabled={autofilling}
              />
            )}
          </div>
          {autofilling && <p style={s.autofillNote}>Fetching GitHub Issue…</p>}
          {autofillMsg && <p style={{ ...s.autofillNote, color: 'var(--primary)' }}>{autofillMsg}</p>}
          {autofillError && <p style={{ ...s.autofillNote, color: 'var(--error)' }}>{autofillError}</p>}

          {/* Title */}
          <div style={s.fieldRow}>
            <label style={s.label}>Title *</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              style={s.input}
              required
              placeholder="What needs to happen?"
            />
          </div>

          {/* Description */}
          <div style={s.fieldRow}>
            <label style={s.label}>Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              style={{ ...s.input, resize: 'vertical' }}
              rows={2}
              placeholder="Optional context (not sent to AI)"
            />
          </div>

          {/* Category + Sub-type */}
          <div style={s.fieldRow}>
            <label style={s.label}>Category *</label>
            <select
              value={categoryId}
              onChange={(e) => { setCategoryId(e.target.value); setSubTypeId(null); }}
              style={s.select}
              required
            >
              <option value="">— select —</option>
              {categories.filter((c) => c.is_active).map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            {subTypes.length > 0 && (
              <>
                <label style={{ ...s.label, marginLeft: '0.75rem' }}>Sub-type</label>
                <select
                  value={subTypeId ?? ''}
                  onChange={(e) => setSubTypeId(e.target.value || null)}
                  style={s.select}
                >
                  <option value="">— none —</option>
                  {subTypes.map((st) => (
                    <option key={st.id} value={st.id}>{st.name}</option>
                  ))}
                </select>
              </>
            )}
          </div>

          {/* Project */}
          <div style={s.fieldRow}>
            <label style={s.label}>Project *</label>
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              style={s.select}
              required
            >
              <option value="">— select —</option>
              {projects.filter((p) => p.is_active).map((p) => (
                <option key={p.id} value={p.id}>{p.name} ({p.scope})</option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => { setShowNewProject((v) => !v); setProjectError(''); }}
              style={s.inlineBtn}
              title="Create a new project"
            >
              + New
            </button>
          </div>
          {showNewProject && (
            <div style={s.inlineForm}>
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
                  onChange={(e) => setNewProjectScope(e.target.value as Project['scope'])}
                >
                  <option value="personal">Personal</option>
                  <option value="team">Team</option>
                  <option value="cross_team">Cross-team</option>
                </select>
                <button
                  type="button"
                  onClick={submitNewProject}
                  disabled={projectSaving}
                  style={s.createBtn}
                >
                  {projectSaving ? 'Creating…' : 'Create'}
                </button>
                <button
                  type="button"
                  onClick={() => { setShowNewProject(false); setProjectError(''); }}
                  style={s.cancelBtn}
                >
                  Cancel
                </button>
              </div>
              {projectError && <p style={{ color: 'var(--error)', fontSize: '0.75rem', margin: '0.3rem 0 0' }}>{projectError}</p>}
            </div>
          )}

          {/* Status + Estimated Effort */}
          <div style={s.fieldRow}>
            <label style={s.label}>Status *</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as Task['status'])}
              style={s.select}
            >
              <option value="todo">Todo</option>
              <option value="running">Running</option>
              <option value="done">Done</option>
              <option value="blocked">Blocked</option>
            </select>

            <label style={{ ...s.label, marginLeft: '1rem' }}>Est. Effort</label>
            <select
              value={estimatedEffort ?? ''}
              onChange={(e) => setEstimatedEffort(e.target.value ? Number(e.target.value) : null)}
              style={{ ...s.select, width: '5rem' }}
            >
              <option value="">—</option>
              {[1, 2, 3, 5, 8].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>

          {/* Blocker type (when blocked) */}
          {status === 'blocked' && (
            <div style={s.fieldRow}>
              <label style={s.label}>Blocker type</label>
              <select
                value={blockerTypeId ?? ''}
                onChange={(e) => setBlockerTypeId(e.target.value || null)}
                style={s.select}
              >
                <option value="">— select —</option>
                {blockerTypes.filter((bt) => bt.is_active).map((bt) => (
                  <option key={bt.id} value={bt.id}>{bt.name}</option>
                ))}
              </select>
            </div>
          )}

          {formError && <p style={s.errorMsg}>{formError}</p>}

          <div style={s.footer}>
            <button type="button" onClick={handleClose} style={s.cancelBtn}>
              Cancel
            </button>
            <button type="submit" disabled={saving} style={s.saveBtn}>
              {saving ? 'Creating…' : 'Create Task'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const modalStyles: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.45)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  panel: {
    background: 'var(--bg)',
    borderRadius: '10px',
    padding: '1.5rem',
    width: '100%',
    maxWidth: '540px',
    maxHeight: '90vh',
    overflowY: 'auto',
    boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '1rem',
  },
  title: { margin: 0, fontSize: '1.1rem', fontWeight: 700 },
  closeBtn: {
    background: 'none',
    border: 'none',
    fontSize: '1rem',
    cursor: 'pointer',
    color: 'var(--text-secondary)',
  },
  fieldRow: {
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '0.4rem',
    marginBottom: '0.75rem',
  },
  label: {
    fontSize: '0.85rem',
    fontWeight: 600,
    color: 'var(--text-body)',
    minWidth: '7rem',
  },
  input: {
    flex: 1,
    padding: '0.35rem 0.6rem',
    border: '1px solid var(--border-strong)',
    borderRadius: '5px',
    fontSize: '0.875rem',
    minWidth: '160px',
    background: 'var(--bg)',
    color: 'var(--text-h)',
  },
  select: {
    padding: '0.35rem 0.5rem',
    border: '1px solid var(--border-strong)',
    borderRadius: '5px',
    fontSize: '0.875rem',
    background: 'var(--bg)',
    color: 'var(--text-h)',
  },
  lockedUrl: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
    flex: 1,
    fontSize: '0.875rem',
    color: 'var(--text-body)',
    background: 'var(--bg-tertiary)',
    border: '1px solid var(--border)',
    borderRadius: '5px',
    padding: '0.35rem 0.6rem',
  },
  lockIcon: { fontSize: '0.75rem' },
  inlineBtn: {
    padding: '0.2rem 0.5rem',
    background: 'none',
    border: '1px solid var(--border-strong)',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '0.8rem',
  },
  inlineForm: {
    marginBottom: '0.75rem',
    padding: '0.75rem',
    background: 'var(--bg-tertiary)',
    border: '1px solid var(--border)',
    borderRadius: '6px',
  },
  createBtn: {
    padding: '0.3rem 0.75rem',
    background: 'var(--primary)',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontWeight: 500,
    fontSize: '0.8rem',
  },
  cancelBtn: {
    padding: '0.35rem 0.9rem',
    background: 'var(--bg-tertiary)',
    border: '1px solid var(--border)',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '0.875rem',
  },
  autofillNote: {
    fontSize: '0.8rem',
    color: 'var(--text-secondary)',
    margin: '-0.25rem 0 0.5rem',
    fontStyle: 'italic',
  },
  footer: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '0.75rem',
    marginTop: '1.25rem',
  },
  saveBtn: {
    padding: '0.4rem 1.1rem',
    background: 'var(--success)',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 600,
    fontSize: '0.875rem',
  },
  errorMsg: {
    color: 'var(--error)',
    fontSize: '0.85rem',
    margin: '0.25rem 0 0.5rem',
  },
};
