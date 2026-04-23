import client from './client';
import type { Project } from '../types/dailyRecord';

export interface GitHubAvailableProject {
  node_id: string;
  number: number;
  title: string;
  owner_login: string;
  url: string;
}

export async function getProjects(): Promise<Project[]> {
  const res = await client.get<Project[]>('/projects');
  return res.data;
}

export async function getAvailableGitHubProjects(): Promise<GitHubAvailableProject[]> {
  const res = await client.get<GitHubAvailableProject[]>('/projects/github/available');
  return res.data;
}

export async function createProject(payload: {
  name: string;
  github_project_node_id: string;
  github_project_number?: number;
  github_project_owner?: string;
}): Promise<Project> {
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
