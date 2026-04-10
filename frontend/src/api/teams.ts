import client from './client';

export interface TeamMember {
  user_id: string;
  display_name: string;
  email: string;
  is_leader: boolean;
  joined_at: string;
}

export interface JoinRequest {
  id: string;
  user_id: string;
  team_id: string;
  status: 'pending' | 'approved' | 'rejected';
  requested_at: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
}

export interface MissingDay {
  user_id: string;
  display_name: string;
  last_reported: string | null;
  missing_dates: string[];
  consecutive_missing: number;
}

export interface TeamSettings {
  team_id: string;
  overload_load_threshold: number;
  overload_streak_days: number;
  fragmentation_task_threshold: number;
  carryover_aging_days: number;
  balance_targets: Record<string, number>;
}

export interface MemberBalance {
  user_id: string;
  display_name: string;
  categories: Record<string, number>;
}

export interface TeamBalance {
  members: MemberBalance[];
  team_aggregate: Record<string, number>;
  targets: Record<string, number>;
}

// ---- Metrics types ----

export interface OverloadEntry {
  user_id: string;
  display_name: string;
  streak_start: string;
  streak_end: string;
  max_load: number;
}

export interface BlockerByType {
  type: string;
  count: number;
}

export interface RecurringBlocker {
  task_desc: string;
  project: string;
  days_blocked: number;
}

export interface BlockerSummary {
  by_type: BlockerByType[];
  recurring: RecurringBlocker[];
}

export interface FragmentationEntry {
  user_id: string;
  display_name: string;
  date: string;
  task_count: number;
}

export interface CarryoverAgingEntry {
  user_id: string;
  display_name: string;
  task_desc: string;
  project: string;
  root_date: string;
  working_days_aged: number;
}

export interface MemberEffort {
  user_id: string;
  display_name: string;
  effort: number;
}

export interface ProjectEffortEntry {
  project_id: string;
  name: string;
  scope: string;
  total_effort: number;
  member_effort: MemberEffort[];
}

// ---- Team Members ----

export async function getTeamMembers(teamId: string): Promise<TeamMember[]> {
  const res = await client.get<TeamMember[]>(`/teams/${teamId}/members`);
  return res.data;
}

// ---- Missing Days ----

export async function getTeamMissingDays(
  teamId: string,
  params: { start_date: string; end_date: string }
): Promise<MissingDay[]> {
  const res = await client.get<MissingDay[]>(`/teams/${teamId}/missing-days`, { params });
  return res.data;
}

// ---- Join Requests ----

export async function getJoinRequests(teamId: string): Promise<JoinRequest[]> {
  const res = await client.get<JoinRequest[]>(`/teams/${teamId}/join-requests`);
  return res.data;
}

export async function resolveJoinRequest(
  teamId: string,
  reqId: string,
  action: 'approve' | 'reject'
): Promise<JoinRequest> {
  const res = await client.patch<JoinRequest>(`/teams/${teamId}/join-requests/${reqId}`, { action });
  return res.data;
}

// ---- Settings ----

export async function getTeamSettings(teamId: string): Promise<TeamSettings> {
  const res = await client.get<TeamSettings>(`/teams/${teamId}/settings`);
  return res.data;
}

export async function updateTeamSettings(
  teamId: string,
  payload: Partial<Omit<TeamSettings, 'team_id'>>
): Promise<TeamSettings> {
  const res = await client.patch<TeamSettings>(`/teams/${teamId}/settings`, payload);
  return res.data;
}

// ---- Metrics ----

export async function getCategoryBalance(
  teamId: string,
  params: { start_date: string; end_date: string }
): Promise<TeamBalance> {
  const res = await client.get<TeamBalance>(`/teams/${teamId}/metrics/balance`, { params });
  return res.data;
}

export async function getOverloadMetrics(
  teamId: string,
  params: { start_date: string; end_date: string }
): Promise<OverloadEntry[]> {
  const res = await client.get<OverloadEntry[]>(`/teams/${teamId}/metrics/overload`, { params });
  return res.data;
}

export async function getBlockerMetrics(
  teamId: string,
  params: { start_date: string; end_date: string }
): Promise<BlockerSummary> {
  const res = await client.get<BlockerSummary>(`/teams/${teamId}/metrics/blockers`, { params });
  return res.data;
}

export async function getFragmentationMetrics(
  teamId: string,
  params: { start_date: string; end_date: string }
): Promise<FragmentationEntry[]> {
  const res = await client.get<FragmentationEntry[]>(`/teams/${teamId}/metrics/fragmentation`, { params });
  return res.data;
}

export async function getCarryoverAgingMetrics(
  teamId: string,
  params: { start_date: string; end_date: string }
): Promise<CarryoverAgingEntry[]> {
  const res = await client.get<CarryoverAgingEntry[]>(`/teams/${teamId}/metrics/carryover-aging`, { params });
  return res.data;
}

export async function getProjectEffortMetrics(
  teamId: string,
  params: { start_date: string; end_date: string }
): Promise<ProjectEffortEntry[]> {
  const res = await client.get<ProjectEffortEntry[]>(`/teams/${teamId}/metrics/project-effort`, { params });
  return res.data;
}
