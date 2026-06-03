// Minimal typed REST client with JWT handling.

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

const TOKEN_KEY = 'thermobaby.access';
const REFRESH_KEY = 'thermobaby.refresh';

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setTokens(access: string, refresh: string): void {
  window.localStorage.setItem(TOKEN_KEY, access);
  window.localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (!(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API ${res.status}: ${detail}`);
  }
  const ct = res.headers.get('content-type') || '';
  return (ct.includes('application/json') ? res.json() : (res.text() as unknown)) as T;
}

export const api = {
  base: API_BASE,
  health: () => request<{ status: string }>('/health'),
  config: () => request<any>('/api/config'),

  async login(email: string, password: string) {
    const form = new URLSearchParams({ username: email, password });
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form,
    });
    if (!res.ok) throw new Error('Login failed');
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    return data;
  },

  patients: () => request<any[]>('/api/patients'),
  createPatient: (body: { name: string; birth_date?: string; notes?: string }) =>
    request('/api/patients', { method: 'POST', body: JSON.stringify(body) }),

  startSession: (body: { patient_id: string; palette: string; mode: string; rois: any[] }) =>
    request<{ id: string }>('/api/sessions', { method: 'POST', body: JSON.stringify(body) }),
  endSession: (id: string) => request(`/api/sessions/${id}/end`, { method: 'POST' }),
  readings: (id: string) => request<any[]>(`/api/sessions/${id}/readings`),
  alerts: (id: string) => request<any[]>(`/api/sessions/${id}/alerts`),

  exportUrl: (id: string, fmt: 'csv' | 'json' | 'pdf') => `${API_BASE}/api/export/${id}.${fmt}`,
};
