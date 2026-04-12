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
  github_repo: string | null;
  is_active: boolean;
}

export interface SelfAssessmentTagRef {
  self_assessment_tag_id: string;
  is_primary: boolean;
}

// ---- Task entity (persists across days) ----

export interface Task {
  id: string;
  title: string;
  description: string | null;
  assignee_id: string;
  project_id: string;
  category_id: string;
  sub_type_id: string | null;
  status: 'todo' | 'running' | 'done' | 'blocked';
  estimated_effort: number | null;
  blocker_type_id: string | null;
  github_issue_url: string | null; // immutable after set
  created_by: string;
  created_at: string;
  closed_at: string | null;
  is_active: boolean;
}

// ---- DailyWorkLog (what I did today on a task) ----

export interface DailyWorkLog {
  id: string;
  task_id: string;
  task?: Task; // populated when returned as part of DailyRecord
  daily_record_id: string;
  effort: number; // 1-5 actual effort today
  work_note: string | null;
  blocker_type_id: string | null;
  blocker_text: string | null; // private
  sort_order: number;
  self_assessment_tags: SelfAssessmentTagRef[];
}

// Form-side type for a single work log row (includes the parent Task for display)
export interface DailyWorkLogFormEntry {
  _key: string; // client-side only
  task: Task;
  task_id: string;
  effort: number;
  work_note: string | null;
  blocker_type_id: string | null;
  blocker_text: string | null;
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
  daily_work_logs: DailyWorkLog[];
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
