import client from './client';
import type { Project } from '../types/dailyRecord';

export async function getProjects(): Promise<Project[]> {
  const res = await client.get<Project[]>('/projects');
  return res.data;
}
