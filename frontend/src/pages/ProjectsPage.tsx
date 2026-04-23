import { useCallback, useEffect, useState } from 'react';
import { AxiosError } from 'axios';
import { useNavigate } from 'react-router-dom';
import { getProjects, updateProject, getAvailableGitHubProjects, createProject } from '../api/projects';
import type { GitHubAvailableProject } from '../api/projects';
import type { Project } from '../types/dailyRecord';
import { useAuthStore } from '../stores/authStore';

export const ProjectsPage = () => {
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();

  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [editNames, setEditNames] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  // Link Project flow
  const [linkOpen, setLinkOpen] = useState(false);
  const [available, setAvailable] = useState<GitHubAvailableProject[]>([]);
  const [linkLoading, setLinkLoading] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);

  const reload = useCallback(() => {
    getProjects()
      .then(setProjects)
      .catch(() => setError('Failed to load projects'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (user?.github_linked) {
      reload();
    }
  }, [user?.github_linked, reload]);

  const rename = async (project: Project) => {
    const name = editNames[project.id]?.trim();
    if (!name || name === project.name) return;
    await updateProject(project.id, { name });
    setEditNames((prev) => ({ ...prev, [project.id]: '' }));
    reload();
  };

  const toggleActive = async (project: Project) => {
    await updateProject(project.id, { is_active: !project.is_active });
    reload();
  };

  const openLinkPanel = async () => {
    setLinkOpen(true);
    setLinkError(null);
    setLinkLoading(true);
    try {
      const results = await getAvailableGitHubProjects();
      setAvailable(results);
    } catch (err) {
      const detail =
        err instanceof AxiosError
          ? (err.response?.data as { detail?: string } | undefined)?.detail
          : undefined;
      setLinkError(detail ?? 'Failed to load GitHub Projects.');
    } finally {
      setLinkLoading(false);
    }
  };

  const closeLinkPanel = () => {
    setLinkOpen(false);
    setAvailable([]);
    setLinkError(null);
  };

  const selectProject = async (proj: GitHubAvailableProject) => {
    setLinkError(null);
    try {
      await createProject({
        name: proj.title,
        github_project_node_id: proj.node_id,
        github_project_number: proj.number,
        github_project_owner: proj.owner_login,
      });
      closeLinkPanel();
      reload();
    } catch (err) {
      const detail =
        err instanceof AxiosError
          ? (err.response?.data as { detail?: string } | undefined)?.detail
          : undefined;
      setLinkError(detail ?? 'Failed to link project. Please try again.');
    }
  };

  // GitHub connection gate — skip all fetches when not linked
  if (!user?.github_linked) {
    return (
      <div style={{ maxWidth: '800px', margin: '0 auto', textAlign: 'center', paddingTop: '4rem' }}>
        <h2 style={{ marginBottom: '1rem' }}>Projects</h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
          Connect your GitHub account to link and manage GitHub Projects.
        </p>
        <button style={primaryBtn} onClick={() => navigate('/settings/profile')}>
          Connect GitHub
        </button>
      </div>
    );
  }

  if (loading) return <p>Loading projects…</p>;
  if (error) return <p style={{ color: 'var(--error)' }}>{error}</p>;

  const active = projects.filter((p) => p.is_active);
  const inactive = projects.filter((p) => !p.is_active);

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <h2 style={{ margin: 0 }}>Projects</h2>
        <button style={primaryBtn} onClick={openLinkPanel}>Link Project</button>
      </div>

      {linkOpen && (
        <section style={{ ...sectionStyle, marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
            <h3 style={{ ...sectionTitle, margin: 0 }}>Select a GitHub Project</h3>
            <button style={tinyBtn} onClick={closeLinkPanel}>Cancel</button>
          </div>
          {linkLoading && <p style={{ margin: 0 }}>Loading GitHub Projects…</p>}
          {linkError && <p style={{ color: 'var(--error)', margin: '0 0 0.5rem' }}>{linkError}</p>}
          {!linkLoading && available.length === 0 && !linkError && (
            <p style={emptyMsg}>No GitHub Projects found.</p>
          )}
          <ul style={listStyle}>
            {available.map((proj) => (
              <li key={proj.node_id} style={itemStyle}>
                <span style={ownerBadge}>@{proj.owner_login}</span>
                <span style={{ flex: 1 }}>{proj.title}</span>
                <button style={tinyBtn} onClick={() => selectProject(proj)}>Select</button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section style={sectionStyle}>
        <h3 style={sectionTitle}>Active ({active.length})</h3>
        {active.length === 0 && <p style={emptyMsg}>No active projects.</p>}
        <ul style={listStyle}>
          {active.map((p) => (
            <li key={p.id} style={itemStyle}>
              {p.github_project_owner && (
                <span style={ownerBadge}>@{p.github_project_owner}</span>
              )}
              <input
                style={inputStyle}
                value={editNames[p.id] ?? p.name}
                onChange={(e) =>
                  setEditNames((prev) => ({ ...prev, [p.id]: e.target.value }))
                }
                onKeyDown={(e) => e.key === 'Enter' && rename(p)}
              />
              <button style={tinyBtn} onClick={() => rename(p)}>Rename</button>
              <button style={dangerBtn} onClick={() => toggleActive(p)}>Deactivate</button>
            </li>
          ))}
        </ul>
      </section>

      {inactive.length > 0 && (
        <section style={sectionStyle}>
          <h3 style={sectionTitle}>Inactive ({inactive.length})</h3>
          <ul style={listStyle}>
            {inactive.map((p) => (
              <li key={p.id} style={{ ...itemStyle, opacity: 0.5 }}>
                {p.github_project_owner && (
                  <span style={ownerBadge}>@{p.github_project_owner}</span>
                )}
                <span style={{ flex: 1 }}>{p.name}</span>
                <button style={tinyBtn} onClick={() => toggleActive(p)}>Reactivate</button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const sectionStyle: React.CSSProperties = {
  border: '1px solid var(--border)',
  borderRadius: '8px',
  padding: '1rem',
  marginBottom: '1rem',
  background: 'var(--bg)',
};
const sectionTitle: React.CSSProperties = { margin: '0 0 0.75rem', fontSize: '1rem', fontWeight: 600 };
const listStyle: React.CSSProperties = { margin: 0, padding: 0, listStyle: 'none' };
const itemStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '0.5rem',
  padding: '0.35rem 0',
  borderBottom: '1px solid var(--border-subtle)',
};
const emptyMsg: React.CSSProperties = { margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' };
const ownerBadge: React.CSSProperties = {
  padding: '0.1rem 0.4rem',
  borderRadius: '4px',
  fontSize: '0.7rem',
  fontWeight: 600,
  background: '#e9ecef',
  color: '#495057',
  whiteSpace: 'nowrap',
};
const inputStyle: React.CSSProperties = {
  flex: 1,
  border: '1px solid var(--border)',
  borderRadius: '4px',
  padding: '0.3rem 0.5rem',
  background: 'var(--bg)',
  color: 'var(--text-h)',
};
const tinyBtn: React.CSSProperties = {
  padding: '0.2rem 0.5rem',
  background: 'var(--bg-tertiary)',
  border: '1px solid var(--border)',
  borderRadius: '4px',
  cursor: 'pointer',
  fontSize: '0.75rem',
};
const dangerBtn: React.CSSProperties = {
  ...tinyBtn,
  color: 'var(--error)',
  borderColor: 'var(--error)',
};
const primaryBtn: React.CSSProperties = {
  padding: '0.4rem 1rem',
  background: 'var(--accent)',
  color: '#fff',
  border: 'none',
  borderRadius: '4px',
  cursor: 'pointer',
  fontWeight: 600,
};
