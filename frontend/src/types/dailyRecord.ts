// Domain types for daily records

export interface Category {
  id: string;
  name: string;
  is_active: boolean;
  sub_types: CategorySubType[];
}

export interface CategorySubType {
  id: string;
  category_id: string;
  name: string;
  is_active: boolean;
}

export interface SelfAssessmentTag {
  id: string;
  name: string;
  is_active: boolean;
}

export interface BlockerType {
  id: string;
  name: string;
  is_active: boolean;
}

export interface Project {
  id: string;
  name: string;
  scope: 'personal' | 'team' | 'cross_team';
  is_active: boolean;
}

export interface SelfAssessmentTagRef {
  self_assessment_tag_id: string;
  is_primary: boolean;
}

export interface TaskEntry {
  id: string;
  daily_record_id: string;
  category_id: string;
  sub_type_id: string | null;
  project_id: string;
  task_description: string;
  effort: number;
  status: 'todo' | 'running' | 'done' | 'blocked';
  blocker_type_id: string | null;
  blocker_text: string | null;
  carried_from_id: string | null;
  sort_order: number;
  self_assessment_tags: SelfAssessmentTagRef[];
}

export interface DailyRecord {
  id: string;
  user_id: string;
  record_date: string; // ISO date string
  day_load: number | null;
  day_note: string | null;
  form_opened_at: string;
  created_at: string;
  updated_at: string;
  task_entries: TaskEntry[];
}

export interface Absence {
  id: string;
  user_id: string;
  record_date: string;
  absence_type: 'holiday' | 'exchanged_holiday' | 'illness' | 'other';
  note: string | null;
  created_at: string;
}

export interface UnlockGrant {
  id: string;
  user_id: string;
  record_date: string;
  granted_by: string;
  granted_at: string;
  revoked_at: string | null;
}

// Form state for a single task entry (before/during saving)
export interface TaskFormEntry {
  _key: string; // client-side only, for React key
  category_id: string;
  sub_type_id: string | null;
  project_id: string;
  task_description: string;
  effort: number;
  status: 'todo' | 'running' | 'done' | 'blocked';
  blocker_type_id: string | null;
  blocker_text: string | null;
  carried_from_id: string | null;
  sort_order: number;
  self_assessment_tags: SelfAssessmentTagRef[];
}
