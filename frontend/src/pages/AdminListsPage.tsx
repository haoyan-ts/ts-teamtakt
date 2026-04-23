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
  getWorkTypes,
  createWorkType,
  updateWorkType,
} from '../api/categories';
import { getAdminSettings, updateAdminSettings } from '../api/adminSettings';
import type { AdminSettingsData } from '../api/adminSettings';
import type { Category, BlockerType, SelfAssessmentTag, WorkType } from '../types/dailyRecord';
import { ControlledListSection } from '../components/admin/ControlledListSection';
import {
  sectionStyle,
  sectionTitle,
  smallInput,
  tinyBtn,
  inputStyle,
  primaryBtn,
} from '../components/admin/adminStyles';

// ---------------------------------------------------------------------------
// Categories section
// ---------------------------------------------------------------------------

function CategoriesSection() {
  const { t } = useTranslation();
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [newSubNames, setNewSubNames] = useState<Record<string, string>>({});

  const reload = () =>
    getCategories(true)
      .then(setCategories)
      .finally(() => setLoading(false));

  useEffect(() => { reload(); }, []);

  const toggleSubActive = async (subId: string, isActive: boolean) => {
    await updateSubType(subId, { is_active: !isActive });
    reload();
  };

  const addSubType = async (catId: string) => {
    const name = (newSubNames[catId] ?? '').trim();
    if (!name) return;
    await createSubType(catId, { name });
    setNewSubNames((prev) => ({ ...prev, [catId]: '' }));
    reload();
  };

  const renameSubType = async (subId: string, name: string) => {
    if (!name.trim()) return;
    await updateSubType(subId, { name: name.trim() });
    reload();
  };

  return (
    <ControlledListSection
      title={t('adminLists.categories.title')}
      items={categories}
      loading={loading}
      addPlaceholder={t('adminLists.categories.newCategoryPlaceholder')}
      onAdd={async (name) => {
        await createCategory({ name, sort_order: categories.length });
        reload();
      }}
      onRename={async (id, name) => {
        await updateCategory(id, { name });
        reload();
      }}
      onToggleActive={async (cat) => {
        await updateCategory(cat.id, { is_active: !cat.is_active });
        reload();
      }}
      confirmDeactivate
      confirmMessage={t('adminLists.confirm.message')}
      extraColumns={[
        {
          header: t('adminLists.categories.colSubTypes'),
          render: (cat) => (
            <>
              <ul style={{ margin: 0, paddingLeft: '1rem', fontSize: '0.8rem' }}>
                {cat.sub_types.map((st) => {
                  const stEditKey = `st-${st.id}`;
                  return (
                    <li key={st.id} style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', marginBottom: '0.2rem' }}>
                      <input
                        style={smallInput}
                        value={newSubNames[stEditKey] ?? st.name}
                        onChange={(e) =>
                          setNewSubNames((prev) => ({ ...prev, [stEditKey]: e.target.value }))
                        }
                        onKeyDown={(e) => e.key === 'Enter' && renameSubType(st.id, newSubNames[stEditKey] ?? st.name)}
                      />
                      <button
                        style={tinyBtn}
                        onClick={() => renameSubType(st.id, newSubNames[stEditKey] ?? st.name)}
                      >
                        {t('adminLists.col.save')}
                      </button>
                      <button
                        style={tinyBtn}
                        onClick={() => toggleSubActive(st.id, st.is_active)}
                      >
                        {st.is_active
                          ? t('adminLists.categories.deactivate')
                          : t('adminLists.categories.activate')}
                      </button>
                    </li>
                  );
                })}
              </ul>
              <div style={{ display: 'flex', gap: '0.3rem', marginTop: '0.3rem' }}>
                <input
                  style={smallInput}
                  placeholder={t('adminLists.categories.newSubTypePlaceholder')}
                  value={newSubNames[cat.id] ?? ''}
                  onChange={(e) =>
                    setNewSubNames((prev) => ({ ...prev, [cat.id]: e.target.value }))
                  }
                  onKeyDown={(e) => e.key === 'Enter' && addSubType(cat.id)}
                />
                <button style={tinyBtn} onClick={() => addSubType(cat.id)}>
                  {t('adminLists.categories.addSubType')}
                </button>
              </div>
            </>
          ),
        },
      ]}
    />
  );
}

// ---------------------------------------------------------------------------
// Blocker types section
// ---------------------------------------------------------------------------

function BlockerTypesSection() {
  const { t } = useTranslation();
  const [types, setTypes] = useState<BlockerType[]>([]);
  const [loading, setLoading] = useState(true);

  const reload = () => getBlockerTypes(true).then(setTypes).finally(() => setLoading(false));
  useEffect(() => { reload(); }, []);

  return (
    <ControlledListSection<BlockerType>
      title={t('adminLists.blockerTypes.title')}
      items={types}
      loading={loading}
      addPlaceholder={t('adminLists.blockerTypes.newPlaceholder')}
      onAdd={async (name) => { await createBlockerType({ name }); reload(); }}
      onRename={async (id, name) => { await updateBlockerType(id, { name }); reload(); }}
      onToggleActive={async (bt) => { await updateBlockerType(bt.id, { is_active: !bt.is_active }); reload(); }}
    />
  );
}

// ---------------------------------------------------------------------------
// Work types section
// ---------------------------------------------------------------------------

function WorkTypesSection() {
  const { t } = useTranslation();
  const [types, setTypes] = useState<WorkType[]>([]);
  const [loading, setLoading] = useState(true);

  const reload = () => getWorkTypes(true).then(setTypes).finally(() => setLoading(false));
  useEffect(() => { reload(); }, []);

  return (
    <ControlledListSection<WorkType>
      title={t('adminLists.workTypes.title')}
      items={types}
      loading={loading}
      addPlaceholder={t('adminLists.workTypes.newPlaceholder')}
      onAdd={async (name) => { await createWorkType({ name }); reload(); }}
      onRename={async (id, name) => { await updateWorkType(id, { name }); reload(); }}
      onToggleActive={async (wt) => { await updateWorkType(wt.id, { is_active: !wt.is_active }); reload(); }}
    />
  );
}

// ---------------------------------------------------------------------------
// Self-assessment tags section
// ---------------------------------------------------------------------------

function TagsSection() {
  const { t } = useTranslation();
  const [tags, setTags] = useState<SelfAssessmentTag[]>([]);
  const [loading, setLoading] = useState(true);

  const reload = () => getSelfAssessmentTags().then(setTags).finally(() => setLoading(false));
  useEffect(() => { reload(); }, []);

  return (
    <ControlledListSection<SelfAssessmentTag>
      title={t('adminLists.tags.title')}
      items={tags}
      loading={loading}
      addPlaceholder={t('adminLists.tags.newPlaceholder')}
      onAdd={async (name) => { await createSelfAssessmentTag({ name }); reload(); }}
      onRename={async (id, name) => { await updateSelfAssessmentTag(id, { name }); reload(); }}
      onToggleActive={async (tag) => { await updateSelfAssessmentTag(tag.id, { is_active: !tag.is_active }); reload(); }}
    />
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

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <button
        onClick={() => navigate('/')}
        style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', padding: 0, fontSize: '0.85rem', marginBottom: '1rem', display: 'block' }}
      >
        {t('adminLists.back')}
      </button>
      <h2 style={{ marginBottom: '1rem' }}>{t('adminLists.pageTitle')}</h2>
      <AdminSettingsSection />
      <CategoriesSection />
      <BlockerTypesSection />
      <WorkTypesSection />
      <TagsSection />
    </div>
  );
};

export { sectionStyle, sectionTitle, inputStyle, tinyBtn, primaryBtn };
