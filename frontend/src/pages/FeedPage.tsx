import { useEffect, useState, useCallback, useRef } from 'react';
import { getFeed } from '../api/social';
import type { FeedItem } from '../api/social';
import { FeedCard } from '../components/social/FeedCard';
import { useWebSocketStore } from '../stores/websocketStore';
import { useAuth } from '../hooks/useAuth';

export const FeedPage = () => {
  const { user, token } = useAuth();
  const [scope, setScope] = useState<'team' | 'all'>('team');
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [cursor, setCursor] = useState<string | undefined>();
  const [hasMore, setHasMore] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadingRef = useRef(false);

  const { connect, disconnect, lastEvent, setScope: setWsScope } = useWebSocketStore();

  // Connect WebSocket on mount
  useEffect(() => {
    if (token) {
      connect(token, scope);
    }
    return () => { disconnect(); };
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  // Refresh feed on WS record events
  useEffect(() => {
    if (lastEvent?.type === 'record.created' || lastEvent?.type === 'record.updated') {
      loadItems(true);
    }
  }, [lastEvent]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadItems = useCallback(async (reset = false) => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setLoading(true);
    setError(null);
    try {
      const newCursor = reset ? undefined : cursor;
      const data = await getFeed({ scope, cursor: newCursor, limit: 20 });
      if (reset) {
        setItems(data);
      } else {
        setItems((prev) => [...prev, ...data]);
      }
      setHasMore(data.length === 20);
      setCursor(data.length > 0 ? data[data.length - 1].created_at : undefined);
    } catch {
      setError('Failed to load feed.');
    } finally {
      setLoading(false);
      loadingRef.current = false;
    }
  }, [scope, cursor]);

  // Reload when scope changes
  useEffect(() => {
    setItems([]);
    setCursor(undefined);
    setHasMore(true);
    setWsScope(scope);
    loadItems(true);
  }, [scope]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{ maxWidth: '700px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 700 }}>Feed</h1>
        {user?.is_leader && (
          <div style={{ display: 'flex', gap: 0, border: '1px solid var(--border-subtle)', borderRadius: '6px', overflow: 'hidden' }}>
            {(['team', 'all'] as const).map((s) => (
              <button
                key={s}
                onClick={() => setScope(s)}
                style={{
                  padding: '0.375rem 1rem',
                  border: 'none',
                  background: scope === s ? 'var(--primary)' : 'var(--bg)',
                  color: scope === s ? '#fff' : 'var(--text-body)',
                  cursor: 'pointer',
                  fontSize: '0.875rem',
                  fontWeight: scope === s ? 600 : 400,
                }}
              >
                {s === 'team' ? 'My Team' : 'All Teams'}
              </button>
            ))}
          </div>
        )}
      </div>

      {error && (
        <div style={{ color: 'var(--error)', background: 'var(--error-bg)', border: '1px solid var(--error-bg)', borderRadius: '6px', padding: '0.75rem', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {items.map((item) => (
          <FeedCard key={item.id} item={item} />
        ))}
      </div>

      {loading && (
        <p style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: '1rem' }}>Loading…</p>
      )}

      {!loading && hasMore && items.length > 0 && (
        <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
          <button
            onClick={() => loadItems()}
            style={{
              padding: '0.5rem 1.5rem',
              background: 'var(--bg)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '0.875rem',
              color: 'var(--text-body)',
            }}
          >
            Load more
          </button>
        </div>
      )}

      {!loading && items.length === 0 && !error && (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: '3rem', fontSize: '1rem' }}>
          No records to show yet.
        </div>
      )}
    </div>
  );
};
