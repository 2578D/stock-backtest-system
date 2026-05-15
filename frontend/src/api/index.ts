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
  triggerFullSync() {
    return http.post("/data/sync/full", { cookie: "" });
  },
  triggerIncrementalSync() {
    return http.post("/data/sync/incremental");
  },
  getSyncStatus() {
    return http.get("/data/sync/status");
  },
  getSyncStats() {
    return http.get("/data/sync/stats");
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

export const dashboardApi = {
  getStats() {
    return http.get("/dashboard/stats");
  },
};

export const pickerApi = {
  run(data: { strategy_id: string; market?: string; exclude_st?: boolean; exclude_suspend?: boolean; max_results?: number }) {
    return http.post("/picks/run", data);
  },
};
export const factorApi = {
  list(params?: { category?: string }) {
    return http.get("/factors", { params });
  },
  get(id: string) {
    return http.get(`/factors/${id}`);
  },
  analyze(id: string, data: { start_date: string; end_date: string; group_count?: number; forward_days?: number }) {
    return http.post(`/factors/${id}/analyze`, data);
  },
  listAnalyses(id: string, params?: { status?: string }) {
    return http.get(`/factors/${id}/analysis`, { params });
  },
  getAnalysis(factorId: string, analysisId: string) {
    return http.get(`/factors/${factorId}/analysis/${analysisId}`);
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
