import { createApiClient } from '@gramcare/api-client';

// Production-safe default: missing VITE_API_URL at build time still yields
// a bundle pointing at the live backend. Local dev overrides via .env.local.
const api = createApiClient({
  baseURL: import.meta.env.VITE_API_URL || 'https://gramcare-fastapi.onrender.com/api/v1',
  tokenStorageKey: 'pharmacy_access_token',
  extraKeysOnUnauthorized: ['pharmacy_user_role'],
});

export default api;
