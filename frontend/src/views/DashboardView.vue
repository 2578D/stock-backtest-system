<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { dashboardApi, backtestApi, strategyApi, dataApi } from "@/api";
import {
  Coin,
  DataAnalysis,
  TrendCharts,
  Finished,
  Loading,
} from "@element-plus/icons-vue";

const router = useRouter();

interface DashboardStats {
  stocks: { total: number; active: number };
  strategies: { total: number; top: any[] };
  backtests: { total: number; completed: number; running: number; recent: any[] };
  data: { latest_date: string | null; distinct_dates: number; total_rows: number };
}

const stats = ref<DashboardStats>({
  stocks: { total: 0, active: 0 },
  strategies: { total: 0, top: [] },
  backtests: { total: 0, completed: 0, running: 0, recent: [] },
  data: { latest_date: null, distinct_dates: 0, total_rows: 0 },
});
const loading = ref(true);

function formatNumber(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + "万";
  return n.toLocaleString();
}

type TagType = "primary" | "success" | "warning" | "info" | "danger";

function statusTag(status: string): { text: string; type: TagType } {
  const map: Record<string, { text: string; type: TagType }> = {
    pending: { text: "等待中", type: "info" },
    running: { text: "运行中", type: "warning" },
    completed: { text: "已完成", type: "success" },
    failed: { text: "失败", type: "danger" },
  };
  return map[status] || { text: status, type: "info" };
}

function goBacktest(id: string) {
  router.push(`/backtests/${id}`);
}

onMounted(async () => {
  try {
    const res = await dashboardApi.getStats();
    if (res.data?.code === 0) {
      stats.value = res.data.data;
    }
  } catch (e) {
    console.error("Failed to load dashboard stats", e);
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="dashboard" v-loading="loading">
    <h2>仪表盘</h2>

    <!-- 核心指标卡片 -->
    <el-row :gutter="16">
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #e6f4ff">
            <el-icon :size="28" color="#1677ff"><Coin /></el-icon>
          </div>
          <div class="stat-body">
            <div class="stat-title">A股总数</div>
            <div class="stat-value">{{ formatNumber(stats.stocks.total) }}</div>
            <div class="stat-sub">正常交易 {{ formatNumber(stats.stocks.active) }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #f6ffed">
            <el-icon :size="28" color="#52c41a"><DataAnalysis /></el-icon>
          </div>
          <div class="stat-body">
            <div class="stat-title">日线数据</div>
            <div class="stat-value">{{ stats.data.distinct_dates }}</div>
            <div class="stat-sub">
              {{ formatNumber(stats.data.total_rows) }} 行
              <template v-if="stats.data.latest_date">
                · 至 {{ stats.data.latest_date }}
              </template>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #fff7e6">
            <el-icon :size="28" color="#fa8c16"><TrendCharts /></el-icon>
          </div>
          <div class="stat-body">
            <div class="stat-title">策略总数</div>
            <div class="stat-value">{{ stats.strategies.total }}</div>
            <div class="stat-sub">可一键回测</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #f9f0ff">
            <el-icon :size="28" color="#722ed1"><Finished /></el-icon>
          </div>
          <div class="stat-body">
            <div class="stat-title">回测任务</div>
            <div class="stat-value">{{ stats.backtests.completed }}/{{ stats.backtests.total }}</div>
            <div class="stat-sub">
              已完成/总数
              <template v-if="stats.backtests.running > 0">
                · {{ stats.backtests.running }} 运行中
              </template>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近回测 + 常用策略 -->
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="14">
        <el-card header="最近回测" shadow="hover">
          <el-table :data="stats.backtests.recent" size="small" v-if="stats.backtests.recent.length">
            <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="statusTag(row.status).type" size="small">
                  {{ statusTag(row.status).text }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="progress" label="进度" width="80">
              <template #default="{ row }">
                <el-progress
                  v-if="row.status === 'running'"
                  :percentage="row.progress || 0"
                  :stroke-width="6"
                  :show-text="true"
                />
                <span v-else-if="row.status === 'completed'">100%</span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="160" />
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'completed'"
                  link
                  type="primary"
                  size="small"
                  @click="goBacktest(row.id)"
                >
                  查看
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无回测任务，去创建第一个吧" />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card header="常用策略" shadow="hover">
          <div v-if="stats.strategies.top.length" class="strategy-list">
            <div
              v-for="s in stats.strategies.top"
              :key="s.id"
              class="strategy-item"
              @click="router.push('/strategies')"
            >
              <div class="strategy-name">{{ s.name }}</div>
              <el-tag size="small" :type="s.type === 'code' ? 'primary' : 'success'">
                {{ s.type === 'code' ? '代码' : '可视化' }}
              </el-tag>
              <span class="strategy-runs">{{ s.run_count }} 次回测</span>
            </div>
          </div>
          <el-empty v-else description="还没有策略" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.dashboard h2 {
  margin-bottom: 16px;
}

.stat-card {
  :deep(.el-card__body) {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
  }
}

.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-body {
  flex: 1;
  min-width: 0;
}

.stat-title {
  font-size: 13px;
  color: #8c8c8c;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.3;
  margin: 2px 0;
}

.stat-sub {
  font-size: 12px;
  color: #8c8c8c;
}

.strategy-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.strategy-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.strategy-item:hover {
  background: #f5f5f5;
}

.strategy-name {
  flex: 1;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.strategy-runs {
  font-size: 12px;
  color: #8c8c8c;
  white-space: nowrap;
}
</style>
