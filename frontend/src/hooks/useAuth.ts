import { useAuthStore } from '../stores/authStore';

export const useAuth = () => {
  const { user, token, isLoading, setToken, setUser, logout, fetchMe } = useAuthStore();
  return { user, token, isLoading, setToken, setUser, logout, fetchMe };
};
