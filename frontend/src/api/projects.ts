import client from './client';
import type { Project } from '../types/dailyRecord';

export async function getProjects(): Promise<Project[]> {
  const res = await client.get<Project[]>('/projects');
  return res.data;
}

export async function createProject(payload: { name: string; scope: 'personal' | 'team' | 'cross_team' }): Promise<Project> {
  const res = await client.post<Project>('/projects', payload);
  return res.data;
}

export async function updateProject(
  id: string,
  payload: { name?: string; is_active?: boolean }
): Promise<Project> {
  const res = await client.patch<Project>(`/projects/${id}`, payload);
  return res.data;
}

export async function deleteProject(id: string): Promise<Project> {
  return updateProject(id, { is_active: false });
}
