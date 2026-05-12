import { createRouter, createWebHistory } from "vue-router";
import type { RouteRecordRaw } from "vue-router";

const routes: RouteRecordRaw[] = [
  {
    path: "/login",
    name: "Login",
    component: () => import("@/views/LoginView.vue"),
    meta: { requiresAuth: false },
  },
  {
    path: "/",
    component: () => import("@/layouts/MainLayout.vue"),
    redirect: "/dashboard",
    children: [
      {
        path: "dashboard",
        name: "Dashboard",
        component: () => import("@/views/DashboardView.vue"),
        meta: { title: "首页", icon: "HomeFilled" },
      },
      {
        path: "data",
        name: "Data",
        redirect: "/data/stocks",
        children: [
          {
            path: "stocks",
            name: "StockList",
            component: () => import("@/views/data/StockListView.vue"),
            meta: { title: "股票列表", icon: "List" },
          },
          {
            path: "daily",
            name: "DailyData",
            component: () => import("@/views/data/DailyDataView.vue"),
            meta: { title: "行情数据", icon: "TrendCharts" },
          },
          {
            path: "sources",
            name: "DataSourceConfig",
            component: () => import("@/views/data/DataSourceView.vue"),
            meta: { title: "数据源配置", icon: "Setting" },
          },
        ],
      },
      {
        path: "strategies",
        name: "StrategyList",
        component: () => import("@/views/strategy/StrategyListView.vue"),
        meta: { title: "策略中心", icon: "Opportunity" },
      },
      {
        path: "strategies/create/visual",
        name: "VisualStrategyEditor",
        component: () => import("@/views/strategy/VisualStrategyEditor.vue"),
        meta: { title: "可视化策略编辑器", icon: "Edit" },
      },
      {
        path: "strategies/create/code",
        name: "CodeStrategyEditor",
        component: () => import("@/views/strategy/CodeStrategyEditor.vue"),
        meta: { title: "代码策略编辑器", icon: "Document" },
      },
      {
        path: "picker",
        name: "StockPicker",
        component: () => import("@/views/picker/StockPickerView.vue"),
        meta: { title: "策略选股器", icon: "Filter" },
      },
      {
        path: "backtests",
        children: [
          {
            path: "",
            name: "BacktestList",
            component: () => import("@/views/backtest/BacktestListView.vue"),
            meta: { title: "回测中心", icon: "DataAnalysis" },
          },
          {
            path: "create",
            name: "CreateBacktest",
            component: () => import("@/views/backtest/CreateBacktestView.vue"),
            meta: { title: "新建回测", icon: "Plus" },
          },
          {
            path: ":id",
            name: "BacktestDetail",
            component: () => import("@/views/backtest/BacktestDetailView.vue"),
            meta: { title: "回测详情", icon: "Reading" },
          },
        ],
      },
      {
        path: "settings",
        name: "Settings",
        component: () => import("@/views/system/SettingsView.vue"),
        meta: { title: "系统设置", icon: "Tools" },
      },
    ],
  },
  {
    path: "/:pathMatch(.*)*",
    name: "NotFound",
    component: () => import("@/views/NotFoundView.vue"),
  },
];

const router = createRouter({
  history: createWebHistory('/stock/'),
  routes,
});

// Navigation guard: redirect to login if not authenticated
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem("access_token");
  if (to.path === "/login") {
    if (token) return next("/dashboard");
    return next();
  }
  if (!token && to.meta.requiresAuth !== false) {
    return next("/login");
  }
  next();
});

export default router;
