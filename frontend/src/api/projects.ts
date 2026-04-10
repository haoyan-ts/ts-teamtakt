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
