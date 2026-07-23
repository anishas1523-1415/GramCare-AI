import { createApiClient } from '@gramcare/api-client';

// Production-safe default: if NEXT_PUBLIC_API_URL is not baked in at build
// time (e.g. Vercel env var missing), the bundle still points at the live
// backend instead of localhost. Local dev overrides via .env.local.
const api = createApiClient({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'https://gramcare-fastapi.onrender.com/api/v1',
  tokenStorageKey: 'access_token',
  refreshTokenStorageKey: 'refresh_token',
});

export default api;
