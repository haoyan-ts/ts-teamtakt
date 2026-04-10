import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireLeader?: boolean;
  requireAdmin?: boolean;
  allowLobby?: boolean;
}

export const ProtectedRoute = ({ children, requireLeader, requireAdmin, allowLobby }: ProtectedRouteProps) => {
  const { token, user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>Loading...</div>;
  }

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (user?.lobby && !user?.is_admin && !allowLobby && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />;
  }

  if (requireLeader && user && !user.is_leader) {
    return <Navigate to="/" replace />;
  }

  if (requireAdmin && user && !user.is_admin) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};
