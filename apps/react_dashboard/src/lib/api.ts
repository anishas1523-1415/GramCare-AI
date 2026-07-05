import axios from 'axios';

const api = axios.create({
  // Production-safe default: missing VITE_API_URL at build time still yields
  // a bundle pointing at the live backend. Local dev overrides via .env.local.
  baseURL: import.meta.env.VITE_API_URL || 'https://gramcare-fastapi.onrender.com/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Previously this client sent no Authorization header at all, even though
// the backend's pharmacy endpoints now require a PHARMACIST-role JWT. This
// interceptor attaches whatever token is currently stored (see AuthGate),
// and a response interceptor clears it on a 401 so the app falls back to
// the login screen instead of silently refetching forever.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('pharmacy_access_token');
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem('pharmacy_access_token');
      localStorage.removeItem('pharmacy_user_role');
    }
    return Promise.reject(error);
  }
);

export default api;
