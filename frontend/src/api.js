const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const SCRAPE_API_KEY = import.meta.env.VITE_SCRAPE_API_KEY || "local-dev-scrape-key";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
}

export function getJobs(filters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  params.set("limit", "100");
  return request(`/jobs?${params.toString()}`);
}

export function getStats() {
  return request("/stats");
}

export function runScrape() {
  return request("/scrape/run", {
    method: "POST",
    headers: {
      "X-API-Key": SCRAPE_API_KEY,
    },
  });
}

export function exportCsv() {
  return `${API_BASE}/export/csv`;
}
