import axios from 'axios';
import type { AxiosInstance } from 'axios';

export interface ApiClientOptions {
  baseURL: string;
  /** localStorage key this app stores its JWT under (each app uses its own,
   * e.g. 'access_token' / 'pharmacy_access_token' / 'lab_access_token'). */
  tokenStorageKey: string;
  /** localStorage key for the refresh token issued alongside the access
   * token at login. Access tokens are short-lived (15 min by default) —
   * without this, any session that outlives one (a multi-step booking
   * flow, a doctor leaving a tab open) hit a 401 on the next call and was
   * silently logged out, surfacing as "invalid credentials" mid-flow even
   * though nothing about the credentials had changed. */
  refreshTokenStorageKey: string;
  /** Extra localStorage keys to clear alongside the token on a hard logout
   * (e.g. a cached role string). */
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
  refreshTokenStorageKey,
  extraKeysOnUnauthorized = [],
}: ApiClientOptions): AxiosInstance {
  const api = axios.create({
    baseURL,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  const clearTokens = () => {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(tokenStorageKey);
    localStorage.removeItem(refreshTokenStorageKey);
    for (const key of extraKeysOnUnauthorized) {
      localStorage.removeItem(key);
    }
  };

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

  // The backend rotates the refresh token on every use (the old one is
  // revoked the instant a new one is issued — see modules/auth/router.py's
  // /auth/refresh), so if two requests 401 around the same moment (e.g. a
  // page firing Promise.all([...]) right as the token expires), only ONE
  // of them may actually call /auth/refresh — a second call using the same
  // now-stale refresh token would fail and wrongly force a real logout
  // even though the first refresh succeeded. All concurrent 401s share
  // this single in-flight promise instead of each requesting their own.
  let refreshPromise: Promise<string | null> | null = null;

  const refreshAccessToken = (): Promise<string | null> => {
    if (typeof window === 'undefined') return Promise.resolve(null);
    const refreshToken = localStorage.getItem(refreshTokenStorageKey);
    if (!refreshToken) return Promise.resolve(null);

    if (!refreshPromise) {
      // A plain axios call, not `api` itself — going through `api` would
      // re-enter this same response interceptor on failure.
      refreshPromise = axios
        .post(`${baseURL}/auth/refresh`, { refresh_token: refreshToken })
        .then((res) => {
          const { access_token, refresh_token } = res.data;
          localStorage.setItem(tokenStorageKey, access_token);
          localStorage.setItem(refreshTokenStorageKey, refresh_token);
          return access_token as string;
        })
        .catch(() => null)
        .finally(() => {
          refreshPromise = null;
        });
    }
    return refreshPromise;
  };

  api.interceptors.response.use(
    (response) => response,
    async (error) => {
      const status = error?.response?.status;
      const original = error?.config;

      if (status === 401 && typeof window !== 'undefined' && original && !original._retriedAfterRefresh) {
        // A failed /auth/login attempt (wrong password) has no session to
        // refresh and isn't a sign that an existing one expired.
        const isLoginAttempt = typeof original.url === 'string' && original.url.includes('/auth/login');
        if (!isLoginAttempt) {
          original._retriedAfterRefresh = true;
          const newToken = await refreshAccessToken();
          if (newToken) {
            original.headers = original.headers || {};
            original.headers.Authorization = `Bearer ${newToken}`;
            return api(original);
          }
        }
        clearTokens();
      }
      return Promise.reject(error);
    }
  );

  return api;
}
