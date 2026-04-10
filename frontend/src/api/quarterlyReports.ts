import client from './client';

export interface QuarterlyReport {
  id: string;
  user_id: string;
  quarter: string;
  status: 'generating' | 'draft' | 'finalized';
  data: Record<string, unknown> | null;
  sections: {
    qualitative?: string;
    quantitative?: string;
    highlights?: string;
    overall?: string;
  } | null;
  guidance_text: string | null;
  finalized_at: string | null;
  created_at: string;
  updated_at: string;
}

export async function generateQuarterlyReport(params: {
  quarter: string;
  guidance_text?: string | null;
}): Promise<QuarterlyReport> {
  const res = await client.post<QuarterlyReport>('/quarterly-reports/generate', params);
  return res.data;
}

export async function getQuarterlyReport(quarter: string): Promise<QuarterlyReport> {
  const res = await client.get<QuarterlyReport>(`/quarterly-reports/${quarter}`);
  return res.data;
}

export async function updateQuarterlyReport(
  quarter: string,
  payload: {
    sections?: Record<string, string> | null;
    guidance_text?: string | null;
  }
): Promise<QuarterlyReport> {
  const res = await client.put<QuarterlyReport>(`/quarterly-reports/${quarter}`, payload);
  return res.data;
}

export async function finalizeQuarterlyReport(quarter: string): Promise<QuarterlyReport> {
  const res = await client.post<QuarterlyReport>(`/quarterly-reports/${quarter}/finalize`);
  return res.data;
}

export async function regenerateQuarterlyReport(
  quarter: string,
  payload: { guidance_text?: string | null }
): Promise<QuarterlyReport> {
  const res = await client.post<QuarterlyReport>(
    `/quarterly-reports/${quarter}/regenerate`,
    payload
  );
  return res.data;
}

export async function listTeamQuarterlyReports(
  teamId: string,
  quarter?: string
): Promise<QuarterlyReport[]> {
  const res = await client.get<QuarterlyReport[]>(
    `/teams/${teamId}/quarterly-reports`,
    { params: quarter ? { quarter } : undefined }
  );
  return res.data;
}
