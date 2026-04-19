import { useState } from 'react';
import type { Comment } from '../../api/social';
import { addComment, updateComment, deleteComment } from '../../api/social';
import { CommentInput } from './CommentInput';
import { useAuth } from '../../hooks/useAuth';

interface CommentNodeProps {
  comment: Comment;
  recordId: string;
  depth: number;
  onMutated: () => void;
}

const CommentNode = ({ comment, recordId, depth, onMutated }: CommentNodeProps) => {
  const { user } = useAuth();
  const [replying, setReplying] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editBody, setEditBody] = useState(comment.body);

  const isOwner = user?.id === comment.author_id;

  const handleReply = async (body: string) => {
    await addComment(recordId, body, comment.id);
    setReplying(false);
    onMutated();
  };

  const handleEdit = async (body: string) => {
    await updateComment(comment.id, body);
    setEditBody(body);
    setEditing(false);
    onMutated();
  };

  const handleDelete = async () => {
    if (!confirm('Delete this comment?')) return;
    await deleteComment(comment.id);
    onMutated();
  };

  return (
    <div style={{ marginLeft: depth > 0 ? '1.5rem' : 0, borderLeft: depth > 0 ? '2px solid var(--border-subtle)' : 'none', paddingLeft: depth > 0 ? '0.75rem' : 0 }}>
      <div style={{ padding: '0.5rem', borderRadius: '6px', background: 'var(--bg-secondary)', marginBottom: '0.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-h)' }}>
            {comment.author_name}
          </span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            {new Date(comment.created_at).toLocaleString()}
            {comment.updated_at !== comment.created_at && ' (edited)'}
          </span>
        </div>

        {editing ? (
          <CommentInput
            onSubmit={handleEdit}
            placeholder={editBody}
            autoFocus
            onCancel={() => setEditing(false)}
          />
        ) : (
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.875rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: 'var(--text-body)' }}>
            {comment.body}
          </p>
        )}

        {!editing && (
          <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.375rem' }}>
            {depth < 3 && (
              <button
                onClick={() => setReplying((v) => !v)}
                style={{ fontSize: '0.75rem', color: 'var(--primary)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
              >
                Reply
              </button>
            )}
            {isOwner && (
              <>
                <button
                  onClick={() => setEditing(true)}
                  style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                >
                  Edit
                </button>
                <button
                  onClick={handleDelete}
                  style={{ fontSize: '0.75rem', color: 'var(--error)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                >
                  Delete
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {replying && (
        <div style={{ margin: '0.5rem 0 0.75rem 0' }}>
          <CommentInput
            onSubmit={handleReply}
            placeholder={`Reply to ${comment.author_name}…`}
            autoFocus
            onCancel={() => setReplying(false)}
          />
        </div>
      )}

      {comment.replies?.map((reply) => (
        <CommentNode key={reply.id} comment={reply} recordId={recordId} depth={depth + 1} onMutated={onMutated} />
      ))}
    </div>
  );
};

interface CommentThreadProps {
  recordId: string;
  comments: Comment[];
  onMutated: () => void;
}

export const CommentThread = ({ recordId, comments, onMutated }: CommentThreadProps) => {
  const handleNewComment = async (body: string) => {
    await addComment(recordId, body);
    onMutated();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      {comments.map((c) => (
        <CommentNode key={c.id} comment={c} recordId={recordId} depth={0} onMutated={onMutated} />
      ))}
      <CommentInput onSubmit={handleNewComment} placeholder="Add a comment…" />
    </div>
  );
};
