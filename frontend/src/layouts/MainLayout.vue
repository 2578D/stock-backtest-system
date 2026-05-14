<script setup lang="ts">
import { useRouter, useRoute } from "vue-router";
import { useUserStore } from "@/stores/user";
import { computed } from "vue";

const router = useRouter();
const route = useRoute();
const userStore = useUserStore();

const menuItems = computed(() => [
  { path: "/dashboard", title: "首页", icon: "HomeFilled" },
  { path: "/data/stocks", title: "数据中心", icon: "Coin" },
  { path: "/strategies", title: "策略中心", icon: "Opportunity" },
  { path: "/picker", title: "选股器", icon: "Filter" },
  { path: "/signals", title: "每日信号", icon: "AlarmClock" },
  { path: "/backtests", title: "回测中心", icon: "DataAnalysis" },
  { path: "/settings", title: "系统设置", icon: "Tools" },
]);

function handleLogout() {
  userStore.logout();
  router.push("/login");
}

const activeMenu = computed(() => {
  const path = route.path;
  for (const item of menuItems.value) {
    if (path.startsWith(item.path)) return item.path;
  }
  return "/dashboard";
});
</script>

<template>
  <el-container class="main-layout">
    <el-aside width="220px">
      <div class="logo">
        <h1>📈 大A回测</h1>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
      >
        <el-menu-item
          v-for="item in menuItems"
          :key="item.path"
          :index="item.path"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header>
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.meta.title">
              {{ route.meta.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <span class="username">{{ userStore.userInfo?.username || "用户" }}</span>
          <el-button type="danger" text @click="handleLogout">退出</el-button>
        </div>
      </el-header>

      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.main-layout {
  height: 100vh;
}

.el-aside {
  background-color: #304156;
  overflow: hidden;
}

.logo {
  padding: 16px;
  text-align: center;
}

.logo h1 {
  color: #fff;
  font-size: 18px;
  margin: 0;
}

.el-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e6e6e6;
  padding: 0 20px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.el-main {
  background: #f5f7fa;
  padding: 20px;
}
</style>
