import client from './client';
import type {
  DailyRecord,
  DailyWorkLogFormEntry,
  DailyEffortBreakdown,
  UnlockGrant,
} from '../types/dailyRecord';

// ---- Daily Records ----

type WorkLogPayload = Omit<DailyWorkLogFormEntry, '_key' | 'task'>;

interface CreateDailyRecordPayload {
  record_date: string;
  day_load: number;
  day_insight?: string | null;
  form_opened_at: string;
  daily_work_logs: WorkLogPayload[];
}

interface UpdateDailyRecordPayload {
  day_load?: number | null;
  day_insight?: string | null;
  form_opened_at: string;
  daily_work_logs?: WorkLogPayload[] | null;
}

export async function createDailyRecord(
  payload: CreateDailyRecordPayload
): Promise<DailyRecord> {
  const res = await client.post<DailyRecord>('/daily-records', payload);
  return res.data;
}

export async function updateDailyRecord(
  id: string,
  payload: UpdateDailyRecordPayload
): Promise<DailyRecord> {
  const res = await client.put<DailyRecord>(`/daily-records/${id}`, payload);
  return res.data;
}

export async function getDailyRecords(params: {
  date?: string;
  start_date?: string;
  end_date?: string;
  user_id?: string;
}): Promise<DailyRecord[]> {
  const res = await client.get<DailyRecord[]>('/daily-records', { params });
  return res.data;
}

// ---- Unlock Grants ----

export async function getUnlockGrants(params: {
  user_id?: string;
  record_date?: string;
}): Promise<UnlockGrant[]> {
  const res = await client.get<UnlockGrant[]>('/unlock-grants', { params });
  return res.data;
}

// ---- Effort Breakdown ----

export async function getEffortBreakdown(params: {
  date: string;
  user_id?: string;
}): Promise<DailyEffortBreakdown> {
  const res = await client.get<DailyEffortBreakdown>('/daily-records/breakdown', { params });
  return res.data;
}
