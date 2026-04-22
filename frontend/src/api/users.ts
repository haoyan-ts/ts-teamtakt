import client from './client';

export interface UserTeam {
  id: string;
  name: string;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  is_leader: boolean;
  is_admin: boolean;
  preferred_locale: string;
  avatar_url: string | null;
  created_at: string | null;
  team: UserTeam | null;
}

export interface CurrentUser extends User {
  lobby: boolean;
  ms365_connected: boolean;
  github_linked: boolean;
  github_login: string | null;
}

interface UserRoleUpdate {
  is_leader?: boolean;
  is_admin?: boolean;
}

export async function getCurrentUser(): Promise<CurrentUser> {
  const res = await client.get<CurrentUser>('/users/me');
  return res.data;
}

export async function listUsers(): Promise<User[]> {
  const res = await client.get<User[]>('/users');
  return res.data;
}

export async function updateUserRoles(
  userId: string,
  payload: UserRoleUpdate
): Promise<User> {
  const res = await client.patch<User>(`/users/${userId}/roles`, payload);
  return res.data;
}

export interface UserProfileUpdate {
  display_name?: string;
  preferred_locale?: string;
}

export async function updateUserProfile(payload: UserProfileUpdate): Promise<CurrentUser> {
  const res = await client.patch<CurrentUser>('/users/me', payload);
  return res.data;
}

export async function disconnectMs365(): Promise<void> {
  await client.delete('/auth/ms365/disconnect');
}

export async function ms365Reconnect(): Promise<string> {
  const res = await client.get<never>('/auth/ms365/reconnect', {
    maxRedirects: 0,
    validateStatus: (status) => status === 307,
  });
  return res.headers['location'] as string;
}

export async function syncAvatarFromMs365(): Promise<{ avatar_url: string }> {
  const res = await client.post<{ avatar_url: string }>('/users/me/sync-avatar');
  return res.data;
}

export async function connectGithub(): Promise<string> {
  const res = await client.get<{ url: string }>('/auth/github/authorize');
  return res.data.url;
}

export async function unlinkGithub(): Promise<void> {
  await client.delete('/auth/github/unlink');
}
