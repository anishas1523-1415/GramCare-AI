import axios from 'axios';
import type { AxiosInstance } from 'axios';

export interface ApiClientOptions {
  baseURL: string;
  /** localStorage key this app stores its JWT under (each app uses its own,
   * e.g. 'access_token' / 'pharmacy_access_token' / 'lab_access_token'). */
  tokenStorageKey: string;
  /** Extra localStorage keys to clear alongside the token on a 401 (e.g. a
   * cached role string). */
  extraKeysOnUnauthorized?: string[];
}

/**
 * Shared axios client factory for every GramCare web app (web_portal,
 * react_dashboard, lab_portal). Each previously hand-rolled its own
 * near-identical version of this — same baseURL-fallback pattern, same
 * Bearer-token request interceptor, same clear-token-on-401 response
 * interceptor — which meant the same class of bug had to be found and
 * fixed independently in three places. Only the construction logic is
 * shared; each app still owns its own token storage key and base URL env
 * var name, since Next.js requires NEXT_PUBLIC_* and Vite requires VITE_*
 * and those can't be unified across bundlers.
 */
export function createApiClient({
  baseURL,
  tokenStorageKey,
  extraKeysOnUnauthorized = [],
}: ApiClientOptions): AxiosInstance {
  const api = axios.create({
    baseURL,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  api.interceptors.request.use((config) => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem(tokenStorageKey);
      if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  });

  api.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error?.response?.status === 401 && typeof window !== 'undefined') {
        localStorage.removeItem(tokenStorageKey);
        for (const key of extraKeysOnUnauthorized) {
          localStorage.removeItem(key);
        }
      }
      return Promise.reject(error);
    }
  );

  return api;
}
