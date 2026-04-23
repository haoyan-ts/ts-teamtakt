import type React from 'react';

export const sectionStyle: React.CSSProperties = {
  border: '1px solid var(--border)',
  borderRadius: '8px',
  padding: '1rem',
  marginBottom: '1rem',
  background: 'var(--bg)',
};

export const sectionTitle: React.CSSProperties = {
  margin: '0 0 0.75rem',
  fontSize: '1rem',
  fontWeight: 600,
};

export const tableStyle: React.CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: '0.85rem',
};

export const th: React.CSSProperties = {
  textAlign: 'left',
  padding: '0.3rem 0.5rem',
  fontWeight: 600,
  borderBottom: '2px solid var(--border)',
};

export const td: React.CSSProperties = {
  padding: '0.4rem 0.5rem',
  verticalAlign: 'top',
};

export const tdMiddle: React.CSSProperties = {
  ...td,
  verticalAlign: 'middle',
};

export const inputStyle: React.CSSProperties = {
  border: '1px solid var(--border)',
  borderRadius: '4px',
  padding: '0.3rem 0.5rem',
  flex: 1,
  background: 'var(--bg)',
  color: 'var(--text-h)',
};

export const smallInput: React.CSSProperties = {
  ...inputStyle,
  flex: 1,
  fontSize: '0.8rem',
};

export const primaryBtn: React.CSSProperties = {
  padding: '0.35rem 0.75rem',
  background: 'var(--primary)',
  color: '#fff',
  border: 'none',
  borderRadius: '4px',
  cursor: 'pointer',
  fontWeight: 500,
};

export const tinyBtn: React.CSSProperties = {
  padding: '0.2rem 0.5rem',
  background: 'var(--bg-tertiary)',
  border: '1px solid var(--border)',
  borderRadius: '4px',
  cursor: 'pointer',
  fontSize: '0.75rem',
};

export const dangerTinyBtn: React.CSSProperties = {
  ...tinyBtn,
  background: 'var(--error-bg)',
  border: '1px solid var(--error-bg)',
  color: 'var(--error)',
};

export const cancelBtn: React.CSSProperties = {
  ...tinyBtn,
  padding: '0.4rem 1rem',
};

export const dangerBtn: React.CSSProperties = {
  ...primaryBtn,
  background: 'var(--error)',
  padding: '0.4rem 1rem',
};
