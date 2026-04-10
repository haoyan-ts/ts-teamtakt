import client from './client';

export interface Holiday {
  id: string;
  date: string;
  name: string;
  source: string;
  is_workday: boolean;
}

interface HolidayCreate {
  date: string;
  name: string;
  source?: string;
  is_workday?: boolean;
}

export async function listHolidays(year: number): Promise<Holiday[]> {
  const res = await client.get<Holiday[]>('/holidays', { params: { year } });
  return res.data;
}

export async function createHoliday(payload: HolidayCreate): Promise<Holiday> {
  const res = await client.post<Holiday>('/holidays', payload);
  return res.data;
}

export async function deleteHoliday(id: string): Promise<void> {
  await client.delete(`/holidays/${id}`);
}

export async function syncHolidays(year: number): Promise<Holiday[]> {
  const res = await client.get<Holiday[]>('/holidays/sync', { params: { year } });
  return res.data;
}
