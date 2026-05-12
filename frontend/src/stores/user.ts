import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { authApi } from "@/api/index";

interface UserInfo {
  id: string;
  username: string;
  email: string;
}

export const useUserStore = defineStore("user", () => {
  const token = ref(localStorage.getItem("access_token") || "");
  const refreshToken = ref(localStorage.getItem("refresh_token") || "");
  const userInfo = ref<UserInfo | null>(null);

  const isLoggedIn = computed(() => !!token.value);

  async function login(username: string, password: string) {
    const res = await authApi.login({ username, password });
    const data = res.data.data;
    token.value = data.access_token;
    refreshToken.value = data.refresh_token;
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    await fetchUser();
  }

  async function register(email: string, username: string, password: string) {
    const res = await authApi.register({ email, username, password });
    const data = res.data.data;
    token.value = data.access_token;
    refreshToken.value = data.refresh_token;
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
  }

  async function fetchUser() {
    try {
      const res = await authApi.me();
      userInfo.value = res.data.data;
    } catch {
      userInfo.value = null;
    }
  }

  function logout() {
    token.value = "";
    refreshToken.value = "";
    userInfo.value = null;
    localStorage.clear();
  }

  return {
    token,
    refreshToken,
    userInfo,
    isLoggedIn,
    login,
    register,
    fetchUser,
    logout,
  };
});
