const TOKEN_KEY = "hotel_faceid_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(path, options = {}) {
  const token = getToken();
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (response.status === 401) {
    clearToken();
    window.location.hash = "#/login";
    throw new Error("نشست شما منقضی شده است");
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `خطای سرور (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}

export const api = {
  login: (username, password) =>
    request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  me: () => request("/api/auth/me"),

  dashboard: () => request("/api/dashboard"),
  occupancy: (at) => request(`/api/occupancy${at ? `?at=${encodeURIComponent(at)}` : ""}`),

  present: () => request("/api/persons/present"),
  persons: (params = {}) => request(`/api/persons?${new URLSearchParams(params)}`),
  person: (id) => request(`/api/persons/${id}`),
  updatePerson: (id, body) =>
    request(`/api/persons/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  personEvents: (id) => request(`/api/persons/${id}/events`),
  personStays: (id) => request(`/api/persons/${id}/stays`),
  mergePersons: (source_id, target_id) =>
    request("/api/persons/merge", {
      method: "POST",
      body: JSON.stringify({ source_id, target_id }),
    }),

  events: (params = {}) => request(`/api/events?${new URLSearchParams(params)}`),

  cameras: () => request("/api/cameras"),
  createCamera: (body) => request("/api/cameras", { method: "POST", body: JSON.stringify(body) }),
  updateCamera: (id, body) =>
    request(`/api/cameras/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteCamera: (id) => request(`/api/cameras/${id}`, { method: "DELETE" }),
  probeCamera: (body) => request("/api/cameras/probe", { method: "POST", body: JSON.stringify(body) }),

  alerts: (params = {}) => request(`/api/alerts?${new URLSearchParams(params)}`),
  acknowledgeAlert: (id) => request(`/api/alerts/${id}/acknowledge`, { method: "POST" }),
  deleteAlert: (id) => request(`/api/alerts/${id}`, { method: "DELETE" }),

  analyticsModules: () => request("/api/analytics/modules"),
  installModule: (id, body = {}) =>
    request(`/api/analytics/modules/${id}/install`, { method: "POST", body: JSON.stringify(body) }),
  removeModule: (id) => request(`/api/analytics/modules/${id}`, { method: "DELETE" }),
  refreshModules: (body = {}) =>
    request("/api/analytics/modules/refresh", { method: "POST", body: JSON.stringify(body) }),

  dailyReport: (start, end) =>
    request(`/api/reports/daily?${new URLSearchParams({ ...(start && { start }), ...(end && { end }) })}`),
  topGuests: (limit = 20) => request(`/api/reports/top-guests?limit=${limit}`),

  faceSearch: async (file) => {
    const token = getToken();
    const form = new FormData();
    form.append("file", file);
    const response = await fetch("/api/faces/search", {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (response.status === 401) {
      clearToken();
      window.location.hash = "#/login";
      throw new Error("نشست شما منقضی شده است");
    }
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || `خطای سرور (${response.status})`);
    }
    return response.json();
  },

  users: () => request("/api/users"),
  createUser: (body) => request("/api/users", { method: "POST", body: JSON.stringify(body) }),
  updateUser: (id, body) => request(`/api/users/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteUser: (id) => request(`/api/users/${id}`, { method: "DELETE" }),
  changeOwnPassword: (body) =>
    request("/api/users/me/password", { method: "POST", body: JSON.stringify(body) }),

  audit: (params = {}) => request(`/api/audit?${new URLSearchParams(params)}`),
};

/** Opens the live-updates socket. Returns a cleanup function. */
export function connectLiveUpdates(onMessage) {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${window.location.host}/api/ws`);

  socket.onmessage = (event) => {
    try {
      onMessage(JSON.parse(event.data));
    } catch {
      /* ignore malformed frames */
    }
  };

  // Some proxies drop idle sockets; a periodic ping keeps the link open.
  const ping = setInterval(() => {
    if (socket.readyState === WebSocket.OPEN) socket.send("ping");
  }, 30000);

  return () => {
    clearInterval(ping);
    socket.close();
  };
}
