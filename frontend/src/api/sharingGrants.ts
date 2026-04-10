import client from './client';

export interface SharingGrant {
  id: string;
  granting_leader_id: string;
  granted_to_leader_id: string;
  team_id: string;
  granted_at: string;
  revoked_at: string | null;
}

interface SharingGrantCreate {
  granted_to_leader_id: string;
}

export async function listSharingGrants(): Promise<SharingGrant[]> {
  const res = await client.get<SharingGrant[]>('/sharing-grants');
  return res.data;
}

export async function createSharingGrant(
  payload: SharingGrantCreate
): Promise<SharingGrant> {
  const res = await client.post<SharingGrant>('/sharing-grants', payload);
  return res.data;
}

export async function revokeSharingGrant(id: string): Promise<void> {
  await client.delete(`/sharing-grants/${id}`);
}
