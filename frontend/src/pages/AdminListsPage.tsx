import { useEffect, useState } from 'react';
import {
  getCategories,
  createCategory,
  updateCategory,
  createSubType,
  updateSubType,
  getBlockerTypes,
  createBlockerType,
  updateBlockerType,
  getSelfAssessmentTags,
  updateSelfAssessmentTag,
} from '../api/categories';
import type { Category, BlockerType, SelfAssessmentTag } from '../types/dailyRecord';

// ---------------------------------------------------------------------------
// Confirmation dialog helper (inline, no library)
// ---------------------------------------------------------------------------

function ConfirmDialog({
  message,
  onConfirm,
  onCancel,
}: {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
    >
      <div style={{ background: '#fff', borderRadius: '8px', padding: '1.5rem', maxWidth: '400px' }}>
        <p style={{ margin: '0 0 1rem' }}>{message}</p>
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
          <button onClick={onCancel} style={cancelBtn}>Cancel</button>
          <button onClick={onConfirm} style={dangerBtn}>Confirm</button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Categories section
// ---------------------------------------------------------------------------

function CategoriesSection() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [newCatName, setNewCatName] = useState('');
  const [newSubNames, setNewSubNames] = useState<Record<string, string>>({});
  const [confirm, setConfirm] = useState<{ catId: string; active: boolean } | null>(null);

  const reload = () =>
    getCategories(true)
      .then(setCategories)
      .finally(() => setLoading(false));

  useEffect(() => { reload(); }, []);

  const addCategory = async () => {
    const name = newCatName.trim();
    if (!name) return;
    await createCategory({ name, sort_order: categories.length });
    setNewCatName('');
    reload();
  };

  const toggleActive = async (cat: Category) => {
    if (!cat.is_active) {
      // Re-activating: no confirmation needed
      await updateCategory(cat.id, { is_active: true });
      reload();
    } else {
      setConfirm({ catId: cat.id, active: false });
    }
  };

  const confirmDeactivate = async () => {
    if (!confirm) return;
    await updateCategory(confirm.catId, { is_active: confirm.active });
    setConfirm(null);
    reload();
  };

  const addSubType = async (catId: string) => {
    const name = (newSubNames[catId] ?? '').trim();
    if (!name) return;
    await createSubType(catId, { name });
    setNewSubNames((prev) => ({ ...prev, [catId]: '' }));
    reload();
  };

  const toggleSubActive = async (subId: string, isActive: boolean) => {
    await updateSubType(subId, { is_active: !isActive });
    reload();
  };

  if (loading) return <p>Loading categories…</p>;

  return (
    <section style={sectionStyle}>
      {confirm && (
        <ConfirmDialog
          message="Deactivating will hide this category from new forms. Historical records are unaffected."
          onConfirm={confirmDeactivate}
          onCancel={() => setConfirm(null)}
        />
      )}
      <h3 style={sectionTitle}>Categories</h3>
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={th}>Name</th>
            <th style={th}>Sub-types</th>
            <th style={th}>Active</th>
          </tr>
        </thead>
        <tbody>
          {categories.map((cat) => (
            <tr key={cat.id} style={{ opacity: cat.is_active ? 1 : 0.5 }}>
              <td style={td}><strong>{cat.name}</strong></td>
              <td style={td}>
                <ul style={{ margin: 0, paddingLeft: '1rem', fontSize: '0.8rem' }}>
                  {cat.sub_types.map((st) => (
                    <li key={st.id} style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                      <span style={{ textDecoration: st.is_active ? 'none' : 'line-through' }}>{st.name}</span>
                      <button
                        style={tinyBtn}
                        onClick={() => toggleSubActive(st.id, st.is_active)}
                      >
                        {st.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </li>
                  ))}
                </ul>
                <div style={{ display: 'flex', gap: '0.3rem', marginTop: '0.3rem' }}>
                  <input
                    style={smallInput}
                    placeholder="New sub-type"
                    value={newSubNames[cat.id] ?? ''}
                    onChange={(e) =>
                      setNewSubNames((prev) => ({ ...prev, [cat.id]: e.target.value }))
                    }
                  />
                  <button style={tinyBtn} onClick={() => addSubType(cat.id)}>Add</button>
                </div>
              </td>
              <td style={td}>
                <button style={tinyBtn} onClick={() => toggleActive(cat)}>
                  {cat.is_active ? 'Deactivate' : 'Activate'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
        <input
          style={inputStyle}
          placeholder="New category name"
          value={newCatName}
          onChange={(e) => setNewCatName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addCategory()}
        />
        <button style={primaryBtn} onClick={addCategory}>Add Category</button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Blocker types section
// ---------------------------------------------------------------------------

function BlockerTypesSection() {
  const [types, setTypes] = useState<BlockerType[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState('');

  const reload = () =>
    // blocker-types endpoint doesn't have include_inactive param yet; show all active
    getBlockerTypes().then(setTypes).finally(() => setLoading(false));

  useEffect(() => { reload(); }, []);

  const add = async () => {
    const name = newName.trim();
    if (!name) return;
    await createBlockerType({ name });
    setNewName('');
    reload();
  };

  const toggle = async (bt: BlockerType) => {
    await updateBlockerType(bt.id, { is_active: !bt.is_active });
    reload();
  };

  if (loading) return <p>Loading…</p>;

  return (
    <section style={sectionStyle}>
      <h3 style={sectionTitle}>Blocker Types</h3>
      <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
        {types.map((bt) => (
          <li
            key={bt.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              padding: '0.35rem 0',
              borderBottom: '1px solid #f0f0f0',
              opacity: bt.is_active ? 1 : 0.5,
            }}
          >
            <span style={{ flex: 1 }}>{bt.name}</span>
            <button style={tinyBtn} onClick={() => toggle(bt)}>
              {bt.is_active ? 'Deactivate' : 'Activate'}
            </button>
          </li>
        ))}
      </ul>
      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
        <input
          style={inputStyle}
          placeholder="New blocker type"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && add()}
        />
        <button style={primaryBtn} onClick={add}>Add</button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Self-assessment tags section
// ---------------------------------------------------------------------------

function TagsSection() {
  const [tags, setTags] = useState<SelfAssessmentTag[]>([]);
  const [loading, setLoading] = useState(true);
  const [editNames, setEditNames] = useState<Record<string, string>>({});

  const reload = () => getSelfAssessmentTags().then(setTags).finally(() => setLoading(false));
  useEffect(() => { reload(); }, []);

  const save = async (tag: SelfAssessmentTag) => {
    const name = editNames[tag.id]?.trim();
    if (!name || name === tag.name) return;
    await updateSelfAssessmentTag(tag.id, { name });
    setEditNames((prev) => ({ ...prev, [tag.id]: '' }));
    reload();
  };

  if (loading) return <p>Loading…</p>;

  return (
    <section style={sectionStyle}>
      <h3 style={sectionTitle}>Self-Assessment Tags</h3>
      <p style={{ fontSize: '0.8rem', color: '#718096', marginBottom: '0.5rem' }}>
        Fixed 4 tags — edit names only.
      </p>
      <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
        {tags.map((tag) => (
          <li
            key={tag.id}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}
          >
            <input
              style={inputStyle}
              defaultValue={tag.name}
              value={editNames[tag.id] ?? tag.name}
              onChange={(e) => setEditNames((prev) => ({ ...prev, [tag.id]: e.target.value }))}
            />
            <button style={tinyBtn} onClick={() => save(tag)}>Save</button>
          </li>
        ))}
      </ul>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export const AdminListsPage = () => (
  <div style={{ maxWidth: '800px', margin: '0 auto' }}>
    <h2 style={{ marginBottom: '1rem' }}>Controlled Lists (Admin)</h2>
    <CategoriesSection />
    <BlockerTypesSection />
    <TagsSection />
  </div>
);

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const sectionStyle: React.CSSProperties = {
  border: '1px solid #e2e8f0',
  borderRadius: '8px',
  padding: '1rem',
  marginBottom: '1rem',
  background: '#fff',
};
const sectionTitle: React.CSSProperties = { margin: '0 0 0.75rem', fontSize: '1rem', fontWeight: 600 };
const tableStyle: React.CSSProperties = { width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' };
const th: React.CSSProperties = {
  textAlign: 'left',
  padding: '0.3rem 0.5rem',
  fontWeight: 600,
  borderBottom: '2px solid #e2e8f0',
};
const td: React.CSSProperties = { padding: '0.4rem 0.5rem', verticalAlign: 'top' };
const inputStyle: React.CSSProperties = {
  border: '1px solid #e2e8f0',
  borderRadius: '4px',
  padding: '0.3rem 0.5rem',
  flex: 1,
};
const smallInput: React.CSSProperties = {
  ...inputStyle,
  flex: 1,
  fontSize: '0.8rem',
};
const primaryBtn: React.CSSProperties = {
  padding: '0.35rem 0.75rem',
  background: '#3182ce',
  color: '#fff',
  border: 'none',
  borderRadius: '4px',
  cursor: 'pointer',
  fontWeight: 500,
};
const tinyBtn: React.CSSProperties = {
  padding: '0.2rem 0.5rem',
  background: '#edf2f7',
  border: '1px solid #e2e8f0',
  borderRadius: '4px',
  cursor: 'pointer',
  fontSize: '0.75rem',
};
const cancelBtn: React.CSSProperties = { ...tinyBtn, padding: '0.4rem 1rem' };
const dangerBtn: React.CSSProperties = {
  ...primaryBtn,
  background: '#e53e3e',
  padding: '0.4rem 1rem',
};
