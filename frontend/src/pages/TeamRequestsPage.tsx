import { useEffect, useState } from 'react';
import { useAuthStore } from '../stores/authStore';
import { getJoinRequests, resolveJoinRequest, type JoinRequest } from '../api/teams';

export const TeamRequestsPage = () => {
  const { user } = useAuthStore();
  const teamId = user?.team?.id;

  const [requests, setRequests] = useState<JoinRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resolving, setResolving] = useState<string | null>(null);

  const reload = () => {
    if (!teamId) return;
    setLoading(true);
    getJoinRequests(teamId)
      .then(setRequests)
      .catch(() => setError('Failed to load join requests.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { reload(); }, [teamId]);

  const handle = async (reqId: string, action: 'approve' | 'reject') => {
    if (!teamId) return;
    setResolving(reqId);
    try {
      await resolveJoinRequest(teamId, reqId, action);
      reload();
    } catch {
      setError(`Failed to ${action} request.`);
    } finally {
      setResolving(null);
    }
  };

  if (!teamId) return <div>You are not assigned to a team.</div>;

  return (
    <div style={{ maxWidth: '700px', margin: '0 auto' }}>
      <h2 style={{ marginBottom: '1rem' }}>Team Join Requests</h2>

      {error && <div style={{ color: '#e53e3e', marginBottom: '1rem' }}>{error}</div>}
      {loading ? (
        <p>Loading…</p>
      ) : requests.length === 0 ? (
        <div style={emptyCard}>No pending join requests.</div>
      ) : (
        <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
          {requests.map((req) => (
            <li key={req.id} style={reqCard}>
              <div>
                <strong>User ID:</strong> {req.user_id}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#718096', marginTop: '0.2rem' }}>
                Requested: {req.requested_at ? new Date(req.requested_at).toLocaleString() : '—'}
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
                <button
                  disabled={!!resolving}
                  onClick={() => handle(req.id, 'approve')}
                  style={approveBtn}
                >
                  {resolving === req.id ? '…' : 'Approve'}
                </button>
                <button
                  disabled={!!resolving}
                  onClick={() => handle(req.id, 'reject')}
                  style={rejectBtn}
                >
                  {resolving === req.id ? '…' : 'Reject'}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const reqCard: React.CSSProperties = {
  border: '1px solid #e2e8f0',
  borderRadius: '8px',
  padding: '0.75rem 1rem',
  marginBottom: '0.75rem',
  background: '#fff',
};
const emptyCard: React.CSSProperties = {
  ...reqCard,
  color: '#a0aec0',
  fontStyle: 'italic',
  textAlign: 'center',
};
const approveBtn: React.CSSProperties = {
  padding: '0.35rem 0.9rem',
  background: '#48bb78',
  color: '#fff',
  border: 'none',
  borderRadius: '4px',
  cursor: 'pointer',
  fontWeight: 500,
};
const rejectBtn: React.CSSProperties = {
  ...approveBtn,
  background: '#e53e3e',
};
