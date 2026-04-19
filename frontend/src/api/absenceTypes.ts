import client from './client';
import type { AbsenceType } from '../types/dailyRecord';

export async function getAbsenceTypes(includeInactive = false): Promise<AbsenceType[]> {
  const res = await client.get<AbsenceType[]>('/absence-types', {
    params: includeInactive ? { include_inactive: true } : {},
  });
  return res.data;
}

export async function createAbsenceType(payload: { name: string }): Promise<AbsenceType> {
  const res = await client.post<AbsenceType>('/absence-types', payload);
  return res.data;
}

export async function updateAbsenceType(
  id: string,
  payload: { name?: string; is_active?: boolean }
): Promise<AbsenceType> {
  const res = await client.patch<AbsenceType>(`/absence-types/${id}`, payload);
  return res.data;
}
