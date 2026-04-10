import client from './client';
import type { Category, SelfAssessmentTag, BlockerType } from '../types/dailyRecord';

export async function getCategories(includeInactive = false): Promise<Category[]> {
  const res = await client.get<Category[]>('/categories', {
    params: includeInactive ? { include_inactive: true } : {},
  });
  return res.data;
}

export async function createCategory(payload: { name: string; sort_order?: number }): Promise<Category> {
  const res = await client.post<Category>('/categories', payload);
  return res.data;
}

export async function updateCategory(
  id: string,
  payload: { name?: string; sort_order?: number; is_active?: boolean }
): Promise<Category> {
  const res = await client.patch<Category>(`/categories/${id}`, payload);
  return res.data;
}

export async function createSubType(
  categoryId: string,
  payload: { name: string; sort_order?: number }
): Promise<Category['sub_types'][number]> {
  const res = await client.post<Category['sub_types'][number]>(
    `/categories/${categoryId}/sub-types`,
    payload
  );
  return res.data;
}

export async function updateSubType(
  subTypeId: string,
  payload: { name?: string; sort_order?: number; is_active?: boolean }
): Promise<Category['sub_types'][number]> {
  const res = await client.patch<Category['sub_types'][number]>(
    `/category-sub-types/${subTypeId}`,
    payload
  );
  return res.data;
}

export async function getSelfAssessmentTags(): Promise<SelfAssessmentTag[]> {
  const res = await client.get<SelfAssessmentTag[]>('/self-assessment-tags');
  return res.data;
}

export async function updateSelfAssessmentTag(
  id: string,
  payload: { name?: string; is_active?: boolean }
): Promise<SelfAssessmentTag> {
  const res = await client.patch<SelfAssessmentTag>(`/self-assessment-tags/${id}`, payload);
  return res.data;
}

export async function getBlockerTypes(): Promise<BlockerType[]> {
  const res = await client.get<BlockerType[]>('/blocker-types');
  return res.data;
}

export async function createBlockerType(payload: { name: string }): Promise<BlockerType> {
  const res = await client.post<BlockerType>('/blocker-types', payload);
  return res.data;
}

export async function updateBlockerType(
  id: string,
  payload: { name?: string; is_active?: boolean }
): Promise<BlockerType> {
  const res = await client.patch<BlockerType>(`/blocker-types/${id}`, payload);
  return res.data;
}
