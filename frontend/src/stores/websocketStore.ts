import { create } from 'zustand';
import { getWebSocketUrl } from '../api/social';

export type WsEvent =
  | { type: 'record.created' | 'record.updated'; record: unknown }
  | { type: 'comment.created' | 'comment.updated'; comment: unknown }
  | { type: 'comment.deleted'; comment_id: string }
  | { type: 'reaction.added' | 'reaction.removed'; record_id: string; emoji: string; user_id: string };

interface WebSocketState {
  connected: boolean;
  scope: 'team' | 'all';
  lastEvent: WsEvent | null;
  connect: (token: string, scope?: 'team' | 'all') => void;
  disconnect: () => void;
  setScope: (scope: 'team' | 'all') => void;
}

let ws: WebSocket | null = null;
let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
let reconnectDelay = 1000;
const MAX_DELAY = 30000;

export const useWebSocketStore = create<WebSocketState>((set, get) => ({
  connected: false,
  scope: 'team',
  lastEvent: null,

  connect: (token: string, scope: 'team' | 'all' = 'team') => {
    set({ scope });
    _connect(token, scope, set);
  },

  disconnect: () => {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }
    if (ws) {
      ws.close();
      ws = null;
    }
    set({ connected: false });
  },

  setScope: (scope: 'team' | 'all') => {
    const prevScope = get().scope;
    if (scope === prevScope) return;
    set({ scope });
    // Reconnect with the new scope
    const token = localStorage.getItem('token');
    if (token) {
      get().disconnect();
      setTimeout(() => get().connect(token, scope), 100);
    }
  },
}));

function _connect(
  token: string,
  scope: 'team' | 'all',
  set: (partial: Partial<WebSocketState>) => void
) {
  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout);
    reconnectTimeout = null;
  }
  if (ws) {
    ws.close();
    ws = null;
  }

  const url = getWebSocketUrl(token, scope);
  const socket = new WebSocket(url);
  ws = socket;

  socket.onopen = () => {
    reconnectDelay = 1000;
    set({ connected: true });
    // Start heartbeat
    const ping = setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send('ping');
      } else {
        clearInterval(ping);
      }
    }, 30000);
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data === 'pong') return;
      set({ lastEvent: data as WsEvent });
    } catch {
      // ignore malformed messages
    }
  };

  socket.onclose = () => {
    set({ connected: false });
    ws = null;
    // Exponential backoff reconnect
    reconnectTimeout = setTimeout(() => {
      const token = localStorage.getItem('token');
      if (token) {
        reconnectDelay = Math.min(reconnectDelay * 2, MAX_DELAY);
        _connect(token, scope, set);
      }
    }, reconnectDelay);
  };

  socket.onerror = () => {
    socket.close();
  };
}
