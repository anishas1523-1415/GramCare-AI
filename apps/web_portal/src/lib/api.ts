import axios from 'axios';

const api = axios.create({
  // Production-safe default: if NEXT_PUBLIC_API_URL is not baked in at build
  // time (e.g. Vercel env var missing), the bundle still points at the live
  // backend instead of localhost. Local dev overrides via .env.local.
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'https://gramcare-fastapi.onrender.com/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request Interceptor: Attach JWT token to requests if available
api.interceptors.request.use(
  (config) => {
    // Client-side only
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('access_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: Handle 401s (Unauthorized) centrally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        // Optionally redirect to login, but wait for AuthContext to handle this via state
      }
    }
    return Promise.reject(error);
  }
);

export default api;
