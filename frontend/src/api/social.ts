import client from './client';
import type { DailyWorkLog } from '../types/dailyRecord';

export interface ReactionGroup {
  emoji: string;
  count: number;
  reacted_by_me: boolean;
  user_ids: string[];
}

export interface FeedItem {
  id: string;
  user_id: string;
  display_name: string;
  record_date: string;
  day_note: string | null;
  daily_work_logs: DailyWorkLog[];
  comment_count: number;
  reactions: ReactionGroup[];
  created_at: string;
  updated_at: string;
}

export interface Comment {
  id: string;
  daily_record_id: string;
  parent_comment_id: string | null;
  author_id: string;
  author_name: string;
  body: string;
  created_at: string;
  updated_at: string;
  replies: Comment[];
}

// ---- Feed ----

export async function getFeed(params: {
  scope?: 'team' | 'all';
  cursor?: string;
  limit?: number;
}): Promise<FeedItem[]> {
  const res = await client.get<FeedItem[]>('/feed', { params });
  return res.data;
}

// ---- Comments ----

export async function addComment(
  recordId: string,
  body: string,
  parentCommentId?: string
): Promise<Comment> {
  const res = await client.post<Comment>(`/daily-records/${recordId}/comments`, {
    body,
    parent_comment_id: parentCommentId ?? null,
  });
  return res.data;
}

export async function listComments(recordId: string): Promise<Comment[]> {
  const res = await client.get<Comment[]>(`/daily-records/${recordId}/comments`);
  return res.data;
}

export async function updateComment(commentId: string, body: string): Promise<Comment> {
  const res = await client.put<Comment>(`/comments/${commentId}`, { body });
  return res.data;
}

export async function deleteComment(commentId: string): Promise<void> {
  await client.delete(`/comments/${commentId}`);
}

// ---- Reactions ----

export async function toggleReaction(recordId: string, emoji: string): Promise<void> {
  await client.post(`/daily-records/${recordId}/reactions`, { emoji });
}

export async function listReactions(recordId: string): Promise<ReactionGroup[]> {
  const res = await client.get<ReactionGroup[]>(`/daily-records/${recordId}/reactions`);
  return res.data;
}

export async function deleteReaction(recordId: string, emoji: string): Promise<void> {
  await client.delete(`/daily-records/${recordId}/reactions/${encodeURIComponent(emoji)}`);
}

// ---- WebSocket URL helper ----

export function getWebSocketUrl(token: string, scope: 'team' | 'all' = 'team'): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return `${protocol}//${host}/api/v1/ws?token=${encodeURIComponent(token)}&scope=${scope}`;
}
