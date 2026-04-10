import client from './client';

export interface NotificationItem {
  id: string;
  trigger_type: string;
  title: string;
  body: string | null;
  data: Record<string, unknown> | null;
  batch_count: number;
  is_read: boolean;
  created_at: string;
}

export interface NotificationPreference {
  trigger_type: string;
  channel_email: boolean;
  channel_teams: boolean;
}

export async function getNotifications(params?: { unread_only?: boolean; limit?: number }): Promise<NotificationItem[]> {
  const res = await client.get<NotificationItem[]>('/notifications', { params });
  return res.data;
}

export async function getUnreadCount(): Promise<number> {
  const res = await client.get<{ count: number }>('/notifications/unread-count');
  return res.data.count;
}

export async function markNotificationRead(id: string): Promise<void> {
  await client.post(`/notifications/${id}/read`);
}

export async function markAllRead(): Promise<void> {
  await client.post('/notifications/mark-all-read');
}

export async function getNotificationPreferences(): Promise<NotificationPreference[]> {
  const res = await client.get<NotificationPreference[]>('/notification-preferences');
  return res.data;
}

export async function updateNotificationPreferences(preferences: NotificationPreference[]): Promise<void> {
  await client.put('/notification-preferences', { preferences });
}
