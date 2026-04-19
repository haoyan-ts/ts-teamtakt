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
  created_at: string | null;
  team: UserTeam | null;
}

export interface CurrentUser extends User {
  lobby: boolean;
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
