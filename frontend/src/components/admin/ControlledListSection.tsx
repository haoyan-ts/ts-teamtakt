import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ConfirmDialog } from './ConfirmDialog';
import {
  sectionStyle,
  sectionTitle,
  tableStyle,
  th,
  td,
  inputStyle,
  tinyBtn,
  primaryBtn,
} from './adminStyles';

export interface ControlledListItem {
  id: string;
  name: string;
  is_active: boolean;
}

export interface ExtraColumn<T extends ControlledListItem> {
  header: string;
  render: (item: T) => React.ReactNode;
}

interface Props<T extends ControlledListItem> {
  title: string;
  items: T[];
  loading?: boolean;
  /** Placeholder for the add-new input */
  addPlaceholder: string;
  /** Called when user submits a new item name */
  onAdd: (name: string) => Promise<void>;
  /** Called when user saves a renamed item */
  onRename: (id: string, name: string) => Promise<void>;
  /** Called when user toggles active/inactive */
  onToggleActive: (item: T) => Promise<void>;
  /** If true, show a ConfirmDialog before deactivating */
  confirmDeactivate?: boolean;
  /** Message shown in the deactivation confirm dialog */
  confirmMessage?: string;
  /** Extra columns rendered after the Name column */
  extraColumns?: ExtraColumn<T>[];
}

export function ControlledListSection<T extends ControlledListItem>({
  title,
  items,
  loading,
  addPlaceholder,
  onAdd,
  onRename,
  onToggleActive,
  confirmDeactivate = false,
  confirmMessage,
  extraColumns = [],
}: Props<T>) {
  const { t } = useTranslation();
  const [newName, setNewName] = useState('');
  const [editNames, setEditNames] = useState<Record<string, string>>({});
  const [confirmTarget, setConfirmTarget] = useState<T | null>(null);
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState<Record<string, boolean>>({});

  const handleAdd = async () => {
    const name = newName.trim();
    if (!name) return;
    setAdding(true);
    try {
      await onAdd(name);
      setNewName('');
    } finally {
      setAdding(false);
    }
  };

  const handleRename = async (item: T) => {
    const name = (editNames[item.id] ?? '').trim();
    if (!name || name === item.name) return;
    setSaving((prev) => ({ ...prev, [item.id]: true }));
    try {
      await onRename(item.id, name);
      setEditNames((prev) => ({ ...prev, [item.id]: '' }));
    } finally {
      setSaving((prev) => ({ ...prev, [item.id]: false }));
    }
  };

  const handleToggle = async (item: T) => {
    if (item.is_active && confirmDeactivate) {
      setConfirmTarget(item);
    } else {
      await onToggleActive(item);
    }
  };

  const handleConfirmDeactivate = async () => {
    if (!confirmTarget) return;
    await onToggleActive(confirmTarget);
    setConfirmTarget(null);
  };

  if (loading) return <p>{t('adminLists.loading')}</p>;

  return (
    <section style={sectionStyle}>
      {confirmTarget && (
        <ConfirmDialog
          message={confirmMessage ?? t('adminLists.confirm.message')}
          onConfirm={handleConfirmDeactivate}
          onCancel={() => setConfirmTarget(null)}
        />
      )}
      <h3 style={sectionTitle}>{title}</h3>
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={th}>{t('adminLists.col.name')}</th>
            {extraColumns.map((col) => (
              <th key={col.header} style={th}>{col.header}</th>
            ))}
            <th style={th}>{t('adminLists.col.actions')}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} style={{ opacity: item.is_active ? 1 : 0.5 }}>
              <td style={td}>
                <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                  <input
                    style={{ ...inputStyle, flex: 1, fontSize: '0.85rem' }}
                    value={editNames[item.id] ?? item.name}
                    onChange={(e) =>
                      setEditNames((prev) => ({ ...prev, [item.id]: e.target.value }))
                    }
                    onKeyDown={(e) => e.key === 'Enter' && handleRename(item)}
                  />
                  <button
                    style={tinyBtn}
                    disabled={saving[item.id]}
                    onClick={() => handleRename(item)}
                  >
                    {t('adminLists.col.save')}
                  </button>
                </div>
              </td>
              {extraColumns.map((col) => (
                <td key={col.header} style={td}>{col.render(item)}</td>
              ))}
              <td style={{ ...td, whiteSpace: 'nowrap' }}>
                <button style={tinyBtn} onClick={() => handleToggle(item)}>
                  {item.is_active
                    ? t('adminLists.col.deactivate')
                    : t('adminLists.col.activate')}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
        <input
          style={inputStyle}
          placeholder={addPlaceholder}
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
        />
        <button style={primaryBtn} disabled={adding} onClick={handleAdd}>
          {t('adminLists.col.add')}
        </button>
      </div>
    </section>
  );
}
