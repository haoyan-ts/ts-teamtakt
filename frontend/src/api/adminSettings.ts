import client from './client';

export interface AdminSettingsData {
  output_language: string;
}

export async function getAdminSettings(): Promise<AdminSettingsData> {
  const res = await client.get<AdminSettingsData>('/admin/settings');
  return res.data;
}

export async function updateAdminSettings(
  payload: { output_language?: string },
): Promise<AdminSettingsData> {
  const res = await client.patch<AdminSettingsData>('/admin/settings', payload);
  return res.data;
}
