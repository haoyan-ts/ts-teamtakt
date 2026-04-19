import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
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
  createSelfAssessmentTag,
  updateSelfAssessmentTag,
} from '../api/categories';
import { getAdminSettings, updateAdminSettings } from '../api/adminSettings';
import type { AdminSettingsData } from '../api/adminSettings';
import type { Category, BlockerType, SelfAssessmentTag } from '../types/dailyRecord';
import {
  getAbsenceTypes,
  createAbsenceType,
  updateAbsenceType,
} from '../api/absenceTypes';
import type { AbsenceType } from '../types/dailyRecord';

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
  const { t } = useTranslation();
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
      <div style={{ background: 'var(--bg)', borderRadius: '8px', padding: '1.5rem', maxWidth: '400px' }}>
        <p style={{ margin: '0 0 1rem' }}>{message}</p>
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
          <button onClick={onCancel} style={cancelBtn}>{t('adminLists.confirm.cancel')}</button>
          <button onClick={onConfirm} style={dangerBtn}>{t('adminLists.confirm.confirm')}</button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Categories section
// ---------------------------------------------------------------------------

function CategoriesSection({ onDirtyChange }: { onDirtyChange: (dirty: boolean) => void }) {
  const { t } = useTranslation();
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

  if (loading) return <p>{t('adminLists.categories.loading')}</p>;

  return (
    <section style={sectionStyle}>
      {confirm && (
        <ConfirmDialog
          message={t('adminLists.confirm.message')}
          onConfirm={confirmDeactivate}
          onCancel={() => setConfirm(null)}
        />
      )}
      <h3 style={sectionTitle}>{t('adminLists.categories.title')}</h3>
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={th}>{t('adminLists.categories.colName')}</th>
            <th style={th}>{t('adminLists.categories.colSubTypes')}</th>
            <th style={th}>{t('adminLists.categories.colActive')}</th>
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
                        {st.is_active ? t('adminLists.categories.deactivate') : t('adminLists.categories.activate')}
                      </button>
                    </li>
                  ))}
                </ul>
                <div style={{ display: 'flex', gap: '0.3rem', marginTop: '0.3rem' }}>
                  <input
                    style={smallInput}
                    placeholder={t('adminLists.categories.newSubTypePlaceholder')}
                    value={newSubNames[cat.id] ?? ''}
                    onChange={(e) =>
                      setNewSubNames((prev) => ({ ...prev, [cat.id]: e.target.value }))
                    }
                  />
                  <button style={tinyBtn} onClick={() => addSubType(cat.id)}>{t('adminLists.categories.addSubType')}</button>
                </div>
              </td>
              <td style={td}>
                <button style={tinyBtn} onClick={() => toggleActive(cat)}>
                  {cat.is_active ? t('adminLists.categories.deactivate') : t('adminLists.categories.activate')}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
        <input
          style={inputStyle}
          placeholder={t('adminLists.categories.newCategoryPlaceholder')}
          value={newCatName}
          onChange={(e) => { setNewCatName(e.target.value); onDirtyChange(!!e.target.value.trim()); }}
          onKeyDown={(e) => e.key === 'Enter' && addCategory()}
        />
        <button style={primaryBtn} onClick={addCategory}>{t('adminLists.categories.addCategory')}</button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Blocker types section
// ---------------------------------------------------------------------------

function BlockerTypesSection({ onDirtyChange }: { onDirtyChange: (dirty: boolean) => void }) {
  const { t } = useTranslation();
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

  if (loading) return <p>{t('adminLists.loading')}</p>;

  return (
    <section style={sectionStyle}>
      <h3 style={sectionTitle}>{t('adminLists.blockerTypes.title')}</h3>
      <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
        {types.map((bt) => (
          <li
            key={bt.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              padding: '0.35rem 0',
              borderBottom: '1px solid var(--border-subtle)',
              opacity: bt.is_active ? 1 : 0.5,
            }}
          >
            <span style={{ flex: 1 }}>{bt.name}</span>
            <button style={tinyBtn} onClick={() => toggle(bt)}>
              {bt.is_active ? t('adminLists.blockerTypes.deactivate') : t('adminLists.blockerTypes.activate')}
            </button>
          </li>
        ))}
      </ul>
      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
        <input
          style={inputStyle}
          placeholder={t('adminLists.blockerTypes.newPlaceholder')}
          value={newName}
          onChange={(e) => { setNewName(e.target.value); onDirtyChange(!!e.target.value.trim()); }}
          onKeyDown={(e) => e.key === 'Enter' && add()}
        />
        <button style={primaryBtn} onClick={add}>{t('adminLists.blockerTypes.add')}</button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Self-assessment tags section
// ---------------------------------------------------------------------------

function TagsSection({ onDirtyChange }: { onDirtyChange: (dirty: boolean) => void }) {
  const { t } = useTranslation();
  const [tags, setTags] = useState<SelfAssessmentTag[]>([]);
  const [loading, setLoading] = useState(true);
  const [editNames, setEditNames] = useState<Record<string, string>>({});
  const [newTagName, setNewTagName] = useState('');

  const reload = () => getSelfAssessmentTags().then(setTags).finally(() => setLoading(false));
  useEffect(() => { reload(); }, []);

  const save = async (tag: SelfAssessmentTag) => {
    const name = editNames[tag.id]?.trim();
    if (!name || name === tag.name) return;
    await updateSelfAssessmentTag(tag.id, { name });
    setEditNames((prev) => ({ ...prev, [tag.id]: '' }));
    reload();
  };

  const toggle = async (tag: SelfAssessmentTag) => {
    await updateSelfAssessmentTag(tag.id, { is_active: !tag.is_active });
    reload();
  };

  const add = async () => {
    const name = newTagName.trim();
    if (!name) return;
    await createSelfAssessmentTag({ name });
    setNewTagName('');
    reload();
  };

  if (loading) return <p>{t('adminLists.loading')}</p>;

  return (
    <section style={sectionStyle}>
      <h3 style={sectionTitle}>{t('adminLists.tags.title')}</h3>
      <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
        {tags.map((tag) => (
          <li
            key={tag.id}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem', opacity: tag.is_active ? 1 : 0.5 }}
          >
            <input
              style={inputStyle}
              defaultValue={tag.name}
              value={editNames[tag.id] ?? tag.name}
              onChange={(e) => setEditNames((prev) => ({ ...prev, [tag.id]: e.target.value }))}
            />
            <button style={tinyBtn} onClick={() => save(tag)}>{t('adminLists.tags.save')}</button>
            <button style={tinyBtn} onClick={() => toggle(tag)}>
              {tag.is_active ? t('adminLists.tags.deactivate') : t('adminLists.tags.activate')}
            </button>
          </li>
        ))}
      </ul>
      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
        <input
          style={inputStyle}
          placeholder={t('adminLists.tags.newPlaceholder')}
          value={newTagName}
          onChange={(e) => { setNewTagName(e.target.value); onDirtyChange(!!e.target.value.trim()); }}
          onKeyDown={(e) => e.key === 'Enter' && add()}
        />
        <button style={primaryBtn} onClick={add}>{t('adminLists.tags.add')}</button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Absence types section
// ---------------------------------------------------------------------------

function AbsenceTypesSection({ onDirtyChange }: { onDirtyChange: (dirty: boolean) => void }) {
  const { t } = useTranslation();
  const [types, setTypes] = useState<AbsenceType[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState('');

  const reload = () =>
    getAbsenceTypes(true).then(setTypes).finally(() => setLoading(false));

  useEffect(() => { reload(); }, []);

  const add = async () => {
    const name = newName.trim();
    if (!name) return;
    await createAbsenceType({ name });
    setNewName('');
    reload();
  };

  const toggle = async (at: AbsenceType) => {
    await updateAbsenceType(at.id, { is_active: !at.is_active });
    reload();
  };

  if (loading) return <p>{t('adminLists.loading')}</p>;

  return (
    <section style={sectionStyle}>
      <h3 style={sectionTitle}>{t('adminLists.absenceTypes.title')}</h3>
      <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
        {types.map((at) => (
          <li
            key={at.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              padding: '0.35rem 0',
              borderBottom: '1px solid var(--border-subtle)',
              opacity: at.is_active ? 1 : 0.5,
            }}
          >
            <span style={{ flex: 1 }}>{at.name}</span>
            <button style={tinyBtn} onClick={() => toggle(at)}>
              {at.is_active ? t('adminLists.absenceTypes.deactivate') : t('adminLists.absenceTypes.activate')}
            </button>
          </li>
        ))}
      </ul>
      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
        <input
          style={inputStyle}
          placeholder={t('adminLists.absenceTypes.newPlaceholder')}
          value={newName}
          onChange={(e) => { setNewName(e.target.value); onDirtyChange(!!e.target.value.trim()); }}
          onKeyDown={(e) => e.key === 'Enter' && add()}
        />
        <button style={primaryBtn} onClick={add}>{t('adminLists.absenceTypes.add')}</button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Output language section
// ---------------------------------------------------------------------------

const LANGUAGE_OPTIONS: { value: string; label: string }[] = [
  { value: 'en', label: 'English' },
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
  { value: 'zh', label: '中文' },
];

function AdminSettingsSection() {
  const { t } = useTranslation();
  const [settings, setSettings] = useState<AdminSettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const reload = () =>
    getAdminSettings()
      .then(setSettings)
      .finally(() => setLoading(false));

  useEffect(() => { reload(); }, []);

  const handleChange = async (lang: string) => {
    setSaving(true);
    try {
      const updated = await updateAdminSettings({ output_language: lang });
      setSettings(updated);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p>{t('adminLists.loading')}</p>;

  return (
    <section style={sectionStyle}>
      <h3 style={sectionTitle}>{t('adminLists.settings.title')}</h3>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <label style={{ fontWeight: 500, fontSize: '0.9rem' }}>{t('adminLists.settings.outputLanguageLabel')}</label>
        <select
          disabled={saving}
          value={settings?.output_language ?? ''}
          onChange={(e) => handleChange(e.target.value)}
          style={{
            border: '1px solid var(--border)',
            borderRadius: '4px',
            padding: '0.3rem 0.5rem',
            background: 'var(--bg)',
            color: 'var(--text-h)',
            cursor: saving ? 'wait' : 'pointer',
          }}
        >
          {LANGUAGE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        {saving && <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{t('adminLists.settings.saving')}</span>}
      </div>
      <p style={{ margin: '0.5rem 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        {t('adminLists.settings.description')}
      </p>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export const AdminListsPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [catDirty, setCatDirty] = useState(false);
  const [blockerDirty, setBlockerDirty] = useState(false);
  const [tagDirty, setTagDirty] = useState(false);
  const [absenceDirty, setAbsenceDirty] = useState(false);
  const isDirty = catDirty || blockerDirty || tagDirty || absenceDirty;

  const handleBack = () => {
    if (isDirty && !window.confirm(t('adminLists.unsavedWarning'))) return;
    navigate('/');
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <button
        onClick={handleBack}
        style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', padding: 0, fontSize: '0.85rem', marginBottom: '1rem', display: 'block' }}
      >
        {t('adminLists.back')}
      </button>
      <h2 style={{ marginBottom: '1rem' }}>{t('adminLists.pageTitle')}</h2>
      <AdminSettingsSection />
      <CategoriesSection onDirtyChange={setCatDirty} />
      <BlockerTypesSection onDirtyChange={setBlockerDirty} />
      <AbsenceTypesSection onDirtyChange={setAbsenceDirty} />
      <TagsSection onDirtyChange={setTagDirty} />
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
const tableStyle: React.CSSProperties = { width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' };
const th: React.CSSProperties = {
  textAlign: 'left',
  padding: '0.3rem 0.5rem',
  fontWeight: 600,
  borderBottom: '2px solid var(--border)',
};
const td: React.CSSProperties = { padding: '0.4rem 0.5rem', verticalAlign: 'top' };
const inputStyle: React.CSSProperties = {
  border: '1px solid var(--border)',
  borderRadius: '4px',
  padding: '0.3rem 0.5rem',
  flex: 1,
  background: 'var(--bg)',
  color: 'var(--text-h)',
};
const smallInput: React.CSSProperties = {
  ...inputStyle,
  flex: 1,
  fontSize: '0.8rem',
};
const primaryBtn: React.CSSProperties = {
  padding: '0.35rem 0.75rem',
  background: 'var(--primary)',
  color: '#fff',
  border: 'none',
  borderRadius: '4px',
  cursor: 'pointer',
  fontWeight: 500,
};
const tinyBtn: React.CSSProperties = {
  padding: '0.2rem 0.5rem',
  background: 'var(--bg-tertiary)',
  border: '1px solid var(--border)',
  borderRadius: '4px',
  cursor: 'pointer',
  fontSize: '0.75rem',
};
const cancelBtn: React.CSSProperties = { ...tinyBtn, padding: '0.4rem 1rem' };
const dangerBtn: React.CSSProperties = {
  ...primaryBtn,
  background: 'var(--error)',
  padding: '0.4rem 1rem',
};
