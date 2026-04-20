import client from './client';
import type { Task } from '../types/dailyRecord';

// ---- Task CRUD ----

export interface CreateTaskPayload {
  title: string;
  description?: string | null;
  project_id: string;
  category_id: string;
  sub_type_id?: string | null;
  status: 'todo' | 'running' | 'done' | 'blocked';
  estimated_effort?: number | null;
  blocker_type_id?: string | null;
  github_issue_url?: string | null;
  insight?: string | null;
}

// github_issue_url excluded: immutable after set — send only on create
export interface UpdateTaskPayload {
  title?: string;
  description?: string | null;
  project_id?: string;
  category_id?: string;
  sub_type_id?: string | null;
  status?: 'todo' | 'running' | 'done' | 'blocked';
  estimated_effort?: number | null;
  blocker_type_id?: string | null;
  insight?: string | null;
}

export async function getTasks(params?: {
  status?: string;
  assignee_id?: string;
}): Promise<Task[]> {
  const res = await client.get<Task[]>('/tasks', { params });
  return res.data;
}

export async function getTask(id: string): Promise<Task> {
  const res = await client.get<Task>(`/tasks/${id}`);
  return res.data;
}

/** Active tasks = status is not 'done' and is_active=true for the current user. */
export async function getActiveTasks(): Promise<Task[]> {
  const res = await client.get<Task[]>('/tasks', { params: { is_active: true } });
  return res.data.filter((t) => t.status !== 'done');
}

export async function createTask(payload: CreateTaskPayload): Promise<Task> {
  const res = await client.post<Task>('/tasks', payload);
  return res.data;
}

export async function updateTask(
  id: string,
  payload: UpdateTaskPayload
): Promise<Task> {
  const res = await client.put<Task>(`/tasks/${id}`, payload);
  return res.data;
}

// ---- GitHub Issue auto-fill ----

export interface GithubAutofillResult {
  title: string | null;
  description: string | null;
  project_id: string | null;
  category_id: string | null;
  sub_type_id: string | null;
  estimated_effort: number | null;
  status: 'todo' | 'done' | null;
  blocker_type_id: string | null;
  insight: string | null;
}

export async function prefillFromGithubIssue(
  url: string
): Promise<GithubAutofillResult> {
  const res = await client.get<GithubAutofillResult>('/tasks/autofill', {
    params: { url },
  });
  return res.data;
}
