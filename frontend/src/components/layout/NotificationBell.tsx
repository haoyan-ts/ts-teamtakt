import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getNotifications,
  getUnreadCount,
  markAllRead,
  markNotificationRead,
  type NotificationItem,
} from '../../api/notifications';

const ICON: Record<string, string> = {
  missing_day: '📅',
  edit_window_closing: '⏰',
  blocker_aging: '🔴',
  team_member_blocked: '⚠️',
  social_reaction: '👍',
  weekly_report_ready: '📊',
  quarterly_draft_ready: '📋',
  team_join_request: '🙋',
};

function timeAgo(isoStr: string): string {
  const diff = Date.now() - new Date(isoStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function navTarget(n: NotificationItem): string | null {
  if (n.data?.record_date) return `/daily/${n.data.record_date}`;
  if (n.data?.week_start) return `/reports/weekly/${n.data.week_start}`;
  if (n.trigger_type === 'team_join_request') return '/team/requests';
  if (n.trigger_type === 'weekly_report_ready') return '/reports/weekly';
  if (n.trigger_type === 'quarterly_draft_ready') return '/reports/quarterly';
  return null;
}

export const NotificationBell = () => {
  const [count, setCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Poll unread count every 30 s
  useEffect(() => {
    const fetchCount = () => getUnreadCount().then(setCount).catch(() => {});
    fetchCount();
    const id = setInterval(fetchCount, 30000);
    return () => clearInterval(id);
  }, []);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleOpen = () => {
    if (!open) {
      setLoading(true);
      getNotifications({ limit: 20 })
        .then(setItems)
        .catch(() => setItems([]))
        .finally(() => setLoading(false));
    }
    setOpen((o) => !o);
  };

  const handleMarkAll = async () => {
    await markAllRead().catch(() => {});
    setCount(0);
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
  };

  const handleClick = async (n: NotificationItem) => {
    if (!n.is_read) {
      await markNotificationRead(n.id).catch(() => {});
      setCount((c) => Math.max(0, c - 1));
      setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)));
    }
    const target = navTarget(n);
    if (target) { setOpen(false); navigate(target); }
  };

  return (
    <div ref={ref} style={{ position: 'relative', marginRight: '0.75rem' }}>
      <button
        onClick={handleOpen}
        style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.25rem', position: 'relative', padding: '2px 4px' }}
        aria-label="Notifications"
      >
        🔔
        {count > 0 && (
          <span style={{
            position: 'absolute', top: -4, right: -6,
            background: 'var(--error)', color: '#fff', borderRadius: '50%',
            width: 16, height: 16, fontSize: '0.65rem', display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            {count > 9 ? '9+' : count}
          </span>
        )}
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: '2rem', right: 0,
          width: 340, maxHeight: 420, overflowY: 'auto',
          background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8,
          boxShadow: '0 4px 16px rgba(0,0,0,0.12)', zIndex: 1000,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--border)' }}>
            <span style={{ fontWeight: 600, fontSize: '0.88rem' }}>Notifications</span>
            <button onClick={handleMarkAll} style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', fontSize: '0.78rem' }}>
              Mark all read
            </button>
          </div>
          {loading ? (
            <div style={{ padding: '1rem', textAlign: 'center', fontSize: '0.85rem', color: 'var(--text-muted)' }}>Loading…</div>
          ) : items.length === 0 ? (
            <div style={{ padding: '1rem', textAlign: 'center', fontSize: '0.85rem', color: 'var(--text-muted)' }}>No notifications</div>
          ) : (
            items.map((n) => (
              <div
                key={n.id}
                onClick={() => handleClick(n)}
                style={{
                  padding: '0.6rem 0.75rem',
                  borderBottom: '1px solid var(--bg-tertiary)',
                  cursor: navTarget(n) ? 'pointer' : 'default',
                  background: n.is_read ? 'var(--bg)' : 'var(--bg-info)',
                  display: 'flex', gap: '0.5rem',
                }}
              >
                <span style={{ fontSize: '1rem', flexShrink: 0 }}>{ICON[n.trigger_type] ?? '📢'}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.83rem', fontWeight: n.is_read ? 400 : 600 }}>
                    {n.title}{n.batch_count > 1 ? ` (×${n.batch_count})` : ''}
                  </div>
                  {n.body && <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: 1 }}>{n.body}</div>}
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 2 }}>{timeAgo(n.created_at)}</div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
