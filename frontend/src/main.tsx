import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './i18n/index';
import { useAuthStore } from './stores/authStore';
import './index.css';

const token = localStorage.getItem('token');
if (token) {
  useAuthStore.getState().fetchMe().catch(() => {
    useAuthStore.getState().logout();
  });
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
