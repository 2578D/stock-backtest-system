import axios from "axios";
import type { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse } from "axios";
import { ElMessage } from "element-plus";
import router from "@/router";

const http: AxiosInstance = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

// Request interceptor: attach token
http.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: handle errors
http.interceptors.response.use(
  (response: AxiosResponse) => {
    const data = response.data;
    if (data.code !== 0 && data.code !== undefined) {
      ElMessage.error(data.message || "请求失败");
      return Promise.reject(new Error(data.message));
    }
    return response;
  },
  async (error) => {
    if (error.response?.status === 401) {
      // Try refresh token
      const refreshToken = localStorage.getItem("refresh_token");
      if (refreshToken && !error.config._retry) {
        error.config._retry = true;
        try {
          const res = await axios.post("/api/v1/auth/refresh", {
            refresh_token: refreshToken,
          });
          const { access_token, refresh_token } = res.data.data;
          localStorage.setItem("access_token", access_token);
          localStorage.setItem("refresh_token", refresh_token);
          error.config.headers.Authorization = `Bearer ${access_token}`;
          return http(error.config);
        } catch {
          // Refresh failed, redirect to login
          localStorage.clear();
          router.push("/login");
        }
      } else {
        localStorage.clear();
        router.push("/login");
      }
    }
    const msg = error.response?.data?.message || error.message || "网络错误";
    ElMessage.error(msg);
    return Promise.reject(error);
  }
);

export default http;
