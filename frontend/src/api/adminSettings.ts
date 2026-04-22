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

export interface TeamsConfigData {
  team_id: string;
  teams_team_id: string | null;
  teams_channel_id: string | null;
}

export async function getTeamsConfig(teamId: string): Promise<TeamsConfigData | null> {
  try {
    const res = await client.get<TeamsConfigData>(`/admin/teams-config/${teamId}`);
    return res.data;
  } catch (err: unknown) {
    if (err && typeof err === 'object' && 'response' in err) {
      const e = err as { response?: { status?: number } };
      if (e.response?.status === 404) return null;
    }
    throw err;
  }
}

export async function upsertTeamsConfig(
  teamId: string,
  payload: { teams_team_id: string | null; teams_channel_id: string | null },
): Promise<TeamsConfigData> {
  const res = await client.put<TeamsConfigData>(`/admin/teams-config/${teamId}`, payload);
  return res.data;
}
