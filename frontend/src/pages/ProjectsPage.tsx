import { useEffect, useState } from 'react';
import { getProjects, updateProject } from '../api/projects';
import type { Project } from '../types/dailyRecord';

export const ProjectsPage = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [editNames, setEditNames] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const reload = () =>
    getProjects()
      .then(setProjects)
      .catch(() => setError('Failed to load projects'))
      .finally(() => setLoading(false));

  useEffect(() => { reload(); }, []);

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

  if (loading) return <p>Loading projects…</p>;
  if (error) return <p style={{ color: 'var(--error)' }}>{error}</p>;

  const active = projects.filter((p) => p.is_active);
  const inactive = projects.filter((p) => !p.is_active);

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <h2 style={{ marginBottom: '1rem' }}>Projects</h2>

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
