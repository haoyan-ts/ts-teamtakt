import { useState, useCallback } from 'react';
import type { FeedItem, Comment } from '../../api/social';
import { listComments, listReactions } from '../../api/social';
import type { ReactionGroup } from '../../api/social';
import { ReactionBar } from './ReactionBar';
import { CommentThread } from './CommentThread';

interface FeedCardProps {
  item: FeedItem;
}

const EFFORT_LABELS = ['', 'XS', 'S', 'M', 'L', 'XL'];

const statusBadgeColor = (status: string): string => {
  switch (status) {
    case 'done': return 'var(--success)';
    case 'in_progress': return 'var(--primary)';
    case 'blocked': return 'var(--error)';
    case 'deferred': return 'var(--text-muted)';
    default: return 'var(--text-secondary)';
  }
};

export const FeedCard = ({ item }: FeedCardProps) => {
  const [expanded, setExpanded] = useState(false);
  const [comments, setComments] = useState<Comment[] | null>(null);
  const [reactions, setReactions] = useState<ReactionGroup[]>(item.reactions);
  const [loadingComments, setLoadingComments] = useState(false);

  const loadComments = useCallback(async () => {
    setLoadingComments(true);
    try {
      const data = await listComments(item.id);
      setComments(data);
    } finally {
      setLoadingComments(false);
    }
  }, [item.id]);

  const handleToggleComments = () => {
    if (!expanded && comments === null) {
      loadComments();
    }
    setExpanded((v) => !v);
  };

  const refreshReactions = useCallback(async () => {
    const data = await listReactions(item.id);
    setReactions(data);
  }, [item.id]);

  const refreshComments = useCallback(() => {
    loadComments();
  }, [loadComments]);

  return (
    <div style={{
      background: 'var(--bg)',
      borderRadius: '10px',
      border: '1px solid var(--border-subtle)',
      padding: '1rem 1.25rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.75rem',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text-h)' }}>{item.display_name}</span>
          <span style={{ marginLeft: '0.5rem', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
            {new Date(item.record_date + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' })}
          </span>
        </div>
      </div>

      {/* Day Insight */}
      {item.day_insight && (
        <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-body)', whiteSpace: 'pre-wrap' }}>{item.day_insight}</p>
      )}

      {/* Work logs */}
      {item.daily_work_logs.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
          {item.daily_work_logs.map((t) => (
            <div
              key={t.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.375rem 0.5rem',
                borderRadius: '6px',
                background: 'var(--bg-secondary)',
                fontSize: '0.8125rem',
              }}
            >
              <span style={{
                color: 'white',
                background: statusBadgeColor(t.task?.status ?? ''),
                borderRadius: '4px',
                padding: '0.1rem 0.4rem',
                fontSize: '0.7rem',
                fontWeight: 600,
                whiteSpace: 'nowrap',
              }}>
                {(t.task?.status ?? '').replace('_', ' ')}
              </span>
              <span style={{ flex: 1, color: 'var(--text-h)' }}>{t.task?.title ?? ''}</span>
              <span style={{ color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>E{EFFORT_LABELS[t.effort] || t.effort}</span>
            </div>
          ))}
        </div>
      )}

      {/* Reaction bar */}
      <ReactionBar recordId={item.id} reactions={reactions} onUpdated={refreshReactions} />

      {/* Comments toggle */}
      <button
        onClick={handleToggleComments}
        style={{
          alignSelf: 'flex-start',
          fontSize: '0.8125rem',
          color: 'var(--primary)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: 0,
        }}
      >
        {expanded ? 'Hide comments' : `Comments (${item.comment_count})`}
      </button>

      {expanded && (
        <div style={{ marginTop: '0.25rem' }}>
          {loadingComments && <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>Loading…</p>}
          {!loadingComments && comments !== null && (
            <CommentThread recordId={item.id} comments={comments} onMutated={refreshComments} />
          )}
        </div>
      )}
    </div>
  );
};
