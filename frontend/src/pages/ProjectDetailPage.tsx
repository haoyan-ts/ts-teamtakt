import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getProjects } from '../api/projects';
import { getTasks, getWorkTypes } from '../api/tasks';
import type { Project, Task, WorkType } from '../types/dailyRecord';

type StatusFilter = 'todo' | 'running' | 'done' | 'blocked' | 'all';

const STATUS_TABS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'todo', label: 'Todo' },
  { value: 'running', label: 'Running' },
  { value: 'done', label: 'Done' },
  { value: 'blocked', label: 'Blocked' },
];

const STATUS_COLORS: Record<string, string> = {
  todo: '#868e96',
  running: '#1971c2',
  done: '#2f9e44',
  blocked: '#c92a2a',
};

export const ProjectDetailPage = () => {
  const { id } = useParams<{ id: string }>();

  const [project, setProject] = useState<Project | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [workTypes, setWorkTypes] = useState<WorkType[]>([]);
  const [filter, setFilter] = useState<StatusFilter>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    Promise.all([getProjects(), getTasks({ project_id: id }), getWorkTypes()])
      .then(([projects, taskList, wtList]) => {
        if (cancelled) return;
        const found = projects.find((p) => p.id === id) ?? null;
        setProject(found);
        setTasks(taskList);
        setWorkTypes(wtList);
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) {
          setError('Failed to load project details.');
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) return <p style={{ padding: '1rem' }}>Loading…</p>;
  if (error) return <p style={{ padding: '1rem', color: 'var(--error)' }}>{error}</p>;
  if (!project) return <p style={{ padding: '1rem', color: 'var(--error)' }}>Project not found.</p>;

  const workTypeMap = new Map(workTypes.map((wt) => [wt.id, wt.name]));

  const filteredTasks =
    filter === 'all' ? tasks : tasks.filter((t) => t.status === filter);

  const activeTasks = tasks.filter((t) => t.status === 'todo' || t.status === 'running');
  const defaultFilterCount = activeTasks.length;

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto' }}>
      {/* Back link */}
      <Link to="/projects" style={backLinkStyle}>
        ← Projects
      </Link>

      {/* Project header */}
      <div style={headerStyle}>
        <div>
          <h2 style={{ margin: '0 0 0.25rem' }}>{project.name}</h2>
          {project.github_project_owner && (
            <a
              href={`https://github.com/${project.github_project_owner}`}
              target="_blank"
              rel="noreferrer"
              style={ownerLinkStyle}
            >
              @{project.github_project_owner}
            </a>
          )}
        </div>
        <span style={activeBadgeStyle}>{defaultFilterCount} active</span>
      </div>

      {/* Status filter tabs */}
      <div style={tabsContainerStyle}>
        {STATUS_TABS.map((tab) => {
          const count = tab.value === 'all' ? tasks.length : tasks.filter((t) => t.status === tab.value).length;
          return (
            <button
              key={tab.value}
              onClick={() => setFilter(tab.value)}
              style={{
                ...tabBtnStyle,
                ...(filter === tab.value ? activeTabStyle : {}),
              }}
            >
              {tab.label}
              <span style={tabCountStyle}>{count}</span>
            </button>
          );
        })}
      </div>

      {/* Task list */}
      {filteredTasks.length === 0 ? (
        <p style={emptyMsgStyle}>No tasks match this filter.</p>
      ) : (
        <ul style={listStyle}>
          {filteredTasks.map((task) => (
            <li key={task.id} style={taskRowStyle}>
              {/* Internal status badge */}
              <span
                style={{
                  ...statusBadgeStyle,
                  background: STATUS_COLORS[task.status] ?? '#868e96',
                }}
              >
                {task.status}
              </span>

              {/* GitHub board column badge (when present) */}
              {task.github_status && (
                <span style={githubStatusBadgeStyle} title="GitHub Project board column">
                  {task.github_status}
                </span>
              )}

              {/* Title + optional GitHub link */}
              <span style={{ flex: 1 }}>
                {task.title}
                {task.github_issue_url && (
                  <a
                    href={task.github_issue_url}
                    target="_blank"
                    rel="noreferrer"
                    style={ghLinkStyle}
                    title="Open GitHub Issue"
                  >
                    ↗
                  </a>
                )}
              </span>

              {/* Work type */}
              <span style={metaChipStyle}>
                {task.work_type_id ? (workTypeMap.get(task.work_type_id) ?? '—') : '—'}
              </span>

              {/* Effort */}
              <span style={effortBadgeStyle}>
                {task.estimated_effort != null ? `${task.estimated_effort} pts` : '—'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const backLinkStyle: React.CSSProperties = {
  display: 'inline-block',
  marginBottom: '1rem',
  color: 'var(--text-secondary)',
  fontSize: '0.85rem',
  textDecoration: 'none',
};

const headerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  marginBottom: '1.25rem',
  padding: '1rem',
  background: 'var(--bg)',
  border: '1px solid var(--border)',
  borderRadius: '8px',
};

const ownerLinkStyle: React.CSSProperties = {
  fontSize: '0.82rem',
  color: 'var(--text-secondary)',
  textDecoration: 'none',
};

const activeBadgeStyle: React.CSSProperties = {
  padding: '0.25rem 0.75rem',
  borderRadius: '999px',
  background: 'var(--bg-tertiary)',
  border: '1px solid var(--border)',
  fontSize: '0.8rem',
  color: 'var(--text-secondary)',
  whiteSpace: 'nowrap',
};

const tabsContainerStyle: React.CSSProperties = {
  display: 'flex',
  gap: '0.25rem',
  marginBottom: '0.75rem',
  flexWrap: 'wrap',
};

const tabBtnStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '0.35rem',
  padding: '0.35rem 0.75rem',
  borderWidth: '1px',
  borderStyle: 'solid',
  borderColor: 'var(--border)',
  borderRadius: '4px',
  background: 'var(--bg)',
  cursor: 'pointer',
  fontSize: '0.85rem',
  color: 'var(--text-secondary)',
};

const activeTabStyle: React.CSSProperties = {
  background: 'var(--accent)',
  color: '#fff',
  borderWidth: '1px',
  borderStyle: 'solid',
  borderColor: 'var(--accent)',
};

const tabCountStyle: React.CSSProperties = {
  fontSize: '0.75rem',
  opacity: 0.8,
};

const listStyle: React.CSSProperties = {
  margin: 0,
  padding: 0,
  listStyle: 'none',
  border: '1px solid var(--border)',
  borderRadius: '8px',
  overflow: 'hidden',
};

const taskRowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '0.75rem',
  padding: '0.6rem 1rem',
  borderBottom: '1px solid var(--border-subtle)',
  background: 'var(--bg)',
};

const statusBadgeStyle: React.CSSProperties = {
  padding: '0.15rem 0.5rem',
  borderRadius: '4px',
  fontSize: '0.7rem',
  fontWeight: 700,
  color: '#fff',
  textTransform: 'capitalize',
  whiteSpace: 'nowrap',
};

const githubStatusBadgeStyle: React.CSSProperties = {
  padding: '0.15rem 0.5rem',
  borderRadius: '4px',
  fontSize: '0.7rem',
  fontWeight: 500,
  color: 'var(--text-secondary)',
  background: 'var(--bg-tertiary)',
  border: '1px solid var(--border)',
  whiteSpace: 'nowrap',
};

const metaChipStyle: React.CSSProperties = {
  fontSize: '0.78rem',
  color: 'var(--text-secondary)',
  whiteSpace: 'nowrap',
};

const effortBadgeStyle: React.CSSProperties = {
  padding: '0.1rem 0.45rem',
  borderRadius: '4px',
  background: 'var(--bg-tertiary)',
  border: '1px solid var(--border)',
  fontSize: '0.75rem',
  fontWeight: 600,
  whiteSpace: 'nowrap',
};

const emptyMsgStyle: React.CSSProperties = {
  padding: '2rem',
  textAlign: 'center',
  color: 'var(--text-secondary)',
  fontSize: '0.9rem',
};

const ghLinkStyle: React.CSSProperties = {
  marginLeft: '0.35rem',
  fontSize: '0.75rem',
  color: 'var(--text-secondary)',
  textDecoration: 'none',
};
