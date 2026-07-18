import { createApiClient } from '@gramcare/api-client';

const api = createApiClient({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'https://gramcare-fastapi.onrender.com/api/v1',
  tokenStorageKey: 'lab_access_token',
});

export default api;
