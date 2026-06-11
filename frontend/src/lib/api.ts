/* API client — komunikasi dengan backend FastAPI */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

async function request<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<{ success: boolean; message: string; data?: T; error?: any }> {
  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const json = await res.json();
    return json;
  } catch (e: any) {
    return {
      success: false,
      message: `Koneksi ke backend gagal: ${e.message}. Pastikan backend jalan di ${BASE}`,
      error: { type: "NetworkError" },
    };
  }
}

export const api = {
  base: BASE,

  // ── Health & Debug ──
  health: () => request("/api/v1/health"),
  systemInfo: () => request("/api/v1/debug/system"),
  getLogs: (lines = 200) => request(`/api/v1/debug/logs?lines=${lines}`),
  clearLogs: () => request("/api/v1/debug/logs", { method: "DELETE" }),

  // ── Auth ──
  authStatus: () => request("/api/v1/auth/status"),
  sessionInfo: () => request("/api/v1/auth/session-info"),
  importCookies: (cookies: any[], username = "") =>
    request("/api/v1/auth/import-cookies", {
      method: "POST",
      body: JSON.stringify({ cookies, username }),
    }),
  loginBrowser: (timeout_minutes = 5, headless = false) =>
    request("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ timeout_minutes, headless }),
    }),
  logout: (hard_reset = false) =>
    request("/api/v1/auth/logout", {
      method: "POST",
      body: JSON.stringify({ hard_reset }),
    }),

  // ── Scrape ──
  scrapeProfile: (username: string, save_tracking = true) =>
    request("/api/v1/scrape/profile", {
      method: "POST",
      body: JSON.stringify({ username, save_tracking }),
    }),
  scrapeBatch: (usernames: string[], delay_between = 12, save_tracking = true) =>
    request("/api/v1/scrape/profiles/batch", {
      method: "POST",
      body: JSON.stringify({ usernames, delay_between, save_tracking }),
    }),

  // ── Tweets / Posts ──
  scrapeUserTweets: (username: string, max_tweets = 40, sentiment_mode: string | null = null) =>
    request("/api/v1/tweets/user", {
      method: "POST",
      body: JSON.stringify({ username, max_tweets, sentiment_mode }),
    }),
  scrapeReplies: (
    tweet_url: string,
    max_replies = 50,
    sort_by = "newest",
    sentiment_mode: string | null = null
  ) =>
    request("/api/v1/tweets/replies", {
      method: "POST",
      body: JSON.stringify({ tweet_url, max_replies, sort_by, sentiment_mode }),
    }),
  scrapeSearch: (
    query: string,
    max_tweets = 40,
    search_type = "Latest",
    sentiment_mode: string | null = null
  ) =>
    request("/api/v1/tweets/search", {
      method: "POST",
      body: JSON.stringify({ query, max_tweets, search_type, sentiment_mode }),
    }),

  // ── Exports ──────────────────────────────────────────────────────────────
  /** Ambil daftar semua file JSON hasil scrape di folder exports/ */
  listExports: () => request("/api/v1/exports"),

  /** URL langsung untuk download / buka file JSON (pakai <a href> atau fetch) */
  downloadExportUrl: (filename: string) =>
    `${BASE}/api/v1/exports/${encodeURIComponent(filename)}`,

  /** Hapus file export dari server */
  deleteExport: (filename: string) =>
    request(`/api/v1/exports/${encodeURIComponent(filename)}`, {
      method: "DELETE",
    }),

  // ── Tracking / Profiles ──
  listProfiles: () => request("/api/v1/profiles"),
  getProfile: (username: string) => request(`/api/v1/profiles/${username}`),
  getGrowth: (username: string, days = 30) =>
    request(`/api/v1/profiles/${username}/growth?days=${days}`),
  manualTrack: (payload: any) =>
    request("/api/v1/profiles/track", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteProfile: (username: string) =>
    request(`/api/v1/profiles/${username}`, { method: "DELETE" }),
  exportCsvUrl: (username: string) =>
    `${BASE}/api/v1/profiles/${username}/export-csv`,
};

export function parseCookies(raw: string): any[] | null {
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function fmtNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "K";
  return n.toLocaleString();
}