import type { EnergyType } from '../../types/dailyRecord';

export const FIBONACCI = [1, 2, 3, 5, 8, 13, 21] as const;

export interface EnergyTypeMeta {
  label: string;
  icon: string;
  color: string;
}

export const ENERGY_TYPE_META: Record<EnergyType, EnergyTypeMeta> = {
  deep_focus:    { label: 'Focus (攻め・集中)',        icon: '🎯', color: 'var(--primary)' },
  collaborative: { label: 'Collaborative (協働)',      icon: '🤝', color: '#7c3aed' },
  admin:         { label: 'Admin (守り・事務)',         icon: '📋', color: '#0891b2' },
  creative:      { label: 'Creative (創造)',           icon: '✨', color: '#d97706' },
  reactive:      { label: 'Interrupt (割り込み・受動)', icon: '⚡', color: '#dc2626' },
};

export const ENERGY_TYPES = Object.keys(ENERGY_TYPE_META) as EnergyType[];
