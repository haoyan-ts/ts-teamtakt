import { useState, useCallback } from 'react';
import type { ReactionGroup } from '../../api/social';
import { toggleReaction } from '../../api/social';

const QUICK_EMOJIS = ['👍', '🎉', '💪', '🤔', '❤️'];

interface ReactionBarProps {
  recordId: string;
  reactions: ReactionGroup[];
  onUpdated: () => void;
}

export const ReactionBar = ({ recordId, reactions, onUpdated }: ReactionBarProps) => {
  const [rateLimited, setRateLimited] = useState(false);
  const [pending, setPending] = useState<string | null>(null);

  const handleToggle = useCallback(async (emoji: string) => {
    if (rateLimited || pending) return;
    setPending(emoji);
    try {
      await toggleReaction(recordId, emoji);
      onUpdated();
    } catch (err: unknown) {
      if (
        err &&
        typeof err === 'object' &&
        'response' in err &&
        (err as { response?: { status?: number } }).response?.status === 429
      ) {
        setRateLimited(true);
        setTimeout(() => setRateLimited(false), 5000);
      }
    } finally {
      setPending(null);
    }
  }, [recordId, rateLimited, pending, onUpdated]);

  const groupMap = new Map<string, ReactionGroup>(reactions.map((r) => [r.emoji, r]));

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem', alignItems: 'center' }}>
      {/* Existing reactions */}
      {reactions.map((g) => (
        <button
          key={g.emoji}
          onClick={() => handleToggle(g.emoji)}
          disabled={!!pending || rateLimited}
          title={rateLimited ? 'Rate limit reached' : undefined}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.25rem',
            padding: '0.2rem 0.5rem',
            borderRadius: '999px',
            border: g.reacted_by_me ? '1.5px solid var(--primary)' : '1.5px solid var(--border-subtle)',
            background: g.reacted_by_me ? 'var(--primary-bg)' : 'var(--bg-secondary)',
            cursor: pending || rateLimited ? 'not-allowed' : 'pointer',
            fontSize: '0.9rem',
            opacity: pending === g.emoji ? 0.6 : 1,
          }}
        >
          <span>{g.emoji}</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-body)' }}>{g.count}</span>
        </button>
      ))}

      {/* Quick-add bar — only show emojis not already present */}
      {QUICK_EMOJIS.filter((e) => !groupMap.has(e)).map((emoji) => (
        <button
          key={emoji}
          onClick={() => handleToggle(emoji)}
          disabled={!!pending || rateLimited}
          title={rateLimited ? 'Rate limit reached' : `React with ${emoji}`}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '0.2rem 0.4rem',
            borderRadius: '999px',
            border: '1.5px dashed var(--border)',
            background: 'transparent',
            cursor: pending || rateLimited ? 'not-allowed' : 'pointer',
            fontSize: '0.85rem',
            opacity: rateLimited ? 0.4 : 0.7,
          }}
        >
          {emoji}
        </button>
      ))}
    </div>
  );
};
