import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
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
