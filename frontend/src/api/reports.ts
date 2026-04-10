import client from './client';

// ---- Weekly Report ----

export interface WeeklyReportSummary {
  id: string;
  user_id: string;
  week_start: string;
  data: {
    days_reported: number;
    category_breakdown: Record<string, number>;
    top_projects: { name: string; effort: number }[];
    carry_over_count: number;
    blocker_count: number;
    tag_distribution: Record<string, number>;
    avg_day_load: number;
  };
  generated_at: string;
}

export async function generateWeeklyReport(weekStart: string): Promise<WeeklyReportSummary> {
  const res = await client.post<WeeklyReportSummary>('/weekly-reports/generate', null, {
    params: { week_start: weekStart },
  });
  return res.data;
}

export async function getWeeklyReport(weekStart: string): Promise<WeeklyReportSummary | null> {
  try {
    const res = await client.get<WeeklyReportSummary>('/weekly-reports', {
      params: { week_start: weekStart },
    });
    return res.data;
  } catch {
    return null;
  }
}

// ---- Weekly Email Draft ----

export interface WeeklyEmailDraft {
  id: string;
  user_id: string;
  week_start: string;
  subject: string;
  body_sections: { tasks: string; highlights: string; next_week: string };
  status: 'draft' | 'sent' | 'failed';
  sent_at: string | null;
  last_sent_at: string | null;
  idempotency_key: string;
}

export async function createEmailDraft(weekStart: string): Promise<WeeklyEmailDraft> {
  const res = await client.post<WeeklyEmailDraft>('/weekly-emails/draft', null, {
    params: { week_start: weekStart },
  });
  return res.data;
}

export async function getEmailDraft(weekStart: string): Promise<WeeklyEmailDraft | null> {
  try {
    const res = await client.get<WeeklyEmailDraft>('/weekly-emails/draft', {
      params: { week_start: weekStart },
    });
    return res.data;
  } catch {
    return null;
  }
}

export async function updateEmailDraft(
  id: string,
  payload: Partial<Pick<WeeklyEmailDraft, 'subject' | 'body_sections'>>
): Promise<WeeklyEmailDraft> {
  const res = await client.put<WeeklyEmailDraft>(`/weekly-emails/draft/${id}`, payload);
  return res.data;
}

export async function sendEmailDraft(id: string): Promise<WeeklyEmailDraft> {
  const res = await client.post<WeeklyEmailDraft>(`/weekly-emails/${id}/send`);
  return res.data;
}

// ---- Unlock grants ----

export interface UnlockGrant {
  id: string;
  user_id: string;
  record_date: string;
  granted_by: string;
  granted_at: string;
  revoked_at: string | null;
}

export async function listUnlockGrants(): Promise<UnlockGrant[]> {
  const res = await client.get<UnlockGrant[]>('/unlock-grants');
  return res.data;
}

export async function createUnlockGrant(userId: string, recordDate: string): Promise<UnlockGrant> {
  const res = await client.post<UnlockGrant>('/unlock-grants', { user_id: userId, record_date: recordDate });
  return res.data;
}

export async function revokeUnlockGrant(id: string): Promise<void> {
  await client.delete(`/unlock-grants/${id}`);
}
