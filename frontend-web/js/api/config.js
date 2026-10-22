/**
 * OMNIVEX Web Frontend Configuration
 */

const defaultBaseUrl = (typeof window !== "undefined" && window.OMNIVEX_CONFIG && window.OMNIVEX_CONFIG.BASE_URL)
  ? window.OMNIVEX_CONFIG.BASE_URL
  : "http://127.0.0.1:8000";

export const API_CONFIG = {
  BASE_URL: defaultBaseUrl,
  API_PREFIX: "/api",
  REQUEST_TIMEOUT_MS: 20000,
  MAX_GET_RETRIES: 2,
  RETRY_BACKOFF_BASE_MS: 300,
  DEFAULT_PAGE_LIMIT: 50,
  MAX_ID_LENGTH: 150,
};

export function getApiBaseUrl() {
  if (typeof window !== "undefined" && window.sessionStorage) {
    const saved = window.sessionStorage.getItem("omnivex_api_base_url");
    if (saved) return saved.replace(/\/+$/, "");
  }
  return API_CONFIG.BASE_URL;
}

export function setApiBaseUrl(url) {
  if (typeof window !== "undefined" && window.sessionStorage) {
    window.sessionStorage.setItem("omnivex_api_base_url", url.replace(/\/+$/, ""));
  }
}
