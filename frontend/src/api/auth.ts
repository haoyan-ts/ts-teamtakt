import client from './client';
import type { User } from '../types';

export const authApi = {
  me: () => client.get<User>('/auth/me'),
  logout: () => client.post('/auth/logout'),
  getLoginUrl: () => '/api/v1/auth/login',
  localLogin: (email: string, password: string) =>
    client.post<{ access_token: string }>('/auth/local-login', { email, password }),
};
