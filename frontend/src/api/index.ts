import http from "./http";

export const authApi = {
  register(data: { email: string; username: string; password: string }) {
    return http.post("/auth/register", data);
  },
  login(data: { username: string; password: string }) {
    return http.post("/auth/login", data);
  },
  refresh(data: { refresh_token: string }) {
    return http.post("/auth/refresh", data);
  },
  me() {
    return http.get("/auth/me");
  },
};

export const dataApi = {
  listStocks(params: Record<string, any> = {}) {
    return http.get("/data/stocks", { params });
  },
  getStock(code: string) {
    return http.get(`/data/stocks/${code}`);
  },
  getDailyBars(code: string, params: Record<string, any> = {}) {
    return http.get(`/data/daily/${code}`, { params });
  },
  listDataSources() {
    return http.get("/data/sources");
  },
};

export const strategyApi = {
  list(params: Record<string, any> = {}) {
    return http.get("/strategies", { params });
  },
  create(data: Record<string, any>) {
    return http.post("/strategies", data);
  },
  get(id: string) {
    return http.get(`/strategies/${id}`);
  },
  update(id: string, data: Record<string, any>) {
    return http.put(`/strategies/${id}`, data);
  },
  delete(id: string) {
    return http.delete(`/strategies/${id}`);
  },
};

export const backtestApi = {
  list(params: Record<string, any> = {}) {
    return http.get("/backtests", { params });
  },
  create(data: Record<string, any>) {
    return http.post("/backtests", data);
  },
  get(id: string) {
    return http.get(`/backtests/${id}`);
  },
  getResult(id: string) {
    return http.get(`/backtests/${id}/result`);
  },
  getTrades(id: string, params: Record<string, any> = {}) {
    return http.get(`/backtests/${id}/trades`, { params });
  },
  stop(id: string) {
    return http.post(`/backtests/${id}/stop`);
  },
};

export const systemApi = {
  getProfile() {
    return http.get("/system/profile");
  },
  updateProfile(data: Record<string, any>) {
    return http.put("/system/profile", data);
  },
  getConfig() {
    return http.get("/system/config");
  },
};
