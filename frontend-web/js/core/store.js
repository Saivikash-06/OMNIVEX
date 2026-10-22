/**
 * OMNIVEX Store
 * Centralized, observable reactive session state.
 */

class Store {
  constructor() {
    this.state = {
      user: null,
      apiKey: null,
      backendStatus: "checking", // "online" | "offline" | "checking"
      backendVersion: null,
      backendLatencyMs: null,
      lastCheckTime: null,
      activeView: "overview",
      cachedDatasets: [],
      cachedModels: [],
      activeAlertsCount: 0,
    };
    this.listeners = new Set();
    this._loadFromStorage();
  }

  _loadFromStorage() {
    if (typeof window === "undefined" || !window.sessionStorage) return;
    try {
      const user = window.sessionStorage.getItem("omnivex_user");
      const apiKey = window.sessionStorage.getItem("omnivex_api_key");
      if (user) this.state.user = user;
      if (apiKey) this.state.apiKey = apiKey;
    } catch {
      // Ignore sessionStorage access errors
    }
  }

  getState() {
    return this.state;
  }

  setState(partialState) {
    this.state = { ...this.state, ...partialState };
    this._persistAuth();
    this.notify();
  }

  _persistAuth() {
    if (typeof window === "undefined" || !window.sessionStorage) return;
    try {
      if (this.state.user) {
        window.sessionStorage.setItem("omnivex_user", this.state.user);
      } else {
        window.sessionStorage.removeItem("omnivex_user");
      }

      if (this.state.apiKey) {
        window.sessionStorage.setItem("omnivex_api_key", this.state.apiKey);
      } else {
        window.sessionStorage.removeItem("omnivex_api_key");
      }
    } catch {
      // Ignore storage errors
    }
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  notify() {
    for (const listener of this.listeners) {
      try {
        listener(this.state);
      } catch (err) {
        console.error("Store listener error:", err);
      }
    }
  }

  clearSession() {
    this.setState({ user: null, apiKey: null });
    if (typeof window !== "undefined" && window.sessionStorage) {
      window.sessionStorage.removeItem("omnivex_user");
      window.sessionStorage.removeItem("omnivex_api_key");
    }
  }
}

export const store = new Store();
