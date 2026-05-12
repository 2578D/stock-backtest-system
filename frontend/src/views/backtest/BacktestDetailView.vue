<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRoute } from "vue-router";
import { backtestApi } from "@/api";

const route = useRoute();
const taskId = route.params.id as string;
const loading = ref(false);
const task = ref<any>({});
const result = ref<any>({});
const trades = ref<any[]>([]);
const activeTab = ref("overview");

async function load() {
  loading.value = true;
  try {
    const [tRes, rRes, trRes] = await Promise.allSettled([
      backtestApi.get(taskId),
      backtestApi.getResult(taskId),
      backtestApi.getTrades(taskId),
    ]);
    if (tRes.status === "fulfilled") task.value = tRes.value.data || {};
    if (rRes.status === "fulfilled") result.value = rRes.value.data || {};
    if (trRes.status === "fulfilled") trades.value = trRes.value.data || [];

    // Auto-refresh if running
    if (task.value.status === "running" || task.value.status === "pending") {
      setTimeout(load, 3000);
    }
  } finally {
    loading.value = false;
  }
}

function fmtPct(v: number | null | undefined) {
  if (v == null) return "-";
  return (v * 100).toFixed(2) + "%";
}
function fmtNum(v: number | null | undefined) {
  if (v == null) return "-";
  return v.toFixed(2);
}
function statusTag(s: string) {
  const map: Record<string, string> = { pending: "info", running: "warning", completed: "success", failed: "danger" };
  return map[s] || "info";
}
function statusLabel(s: string) {
  const map: Record<string, string> = { pending: "等待中", running: "运行中", completed: "已完成", failed: "失败" };
  return map[s] || s;
}

onMounted(load);
</script>

<template>
  <div class="backtest-detail" v-loading="loading">
    <div class="top-bar">
      <el-page-header @back="$router.back()">
        <template #content>
          <span>{{ task.name || "回测详情" }}</span>
          <el-tag :type="statusTag(task.status)" size="small" style="margin-left: 8px">
            {{ statusLabel(task.status) }}
          </el-tag>
          <el-progress
            v-if="task.status === 'running'"
            :percentage="task.progress || 0"
            :stroke-width="4"
            style="width: 120px; margin-left: 12px; display: inline-block; vertical-align: middle"
          />
        </template>
      </el-page-header>
    </div>

    <el-tabs v-model="activeTab" style="margin-top: 16px">
      <!-- Overview -->
      <el-tab-pane label="收益概览" name="overview">
        <el-row :gutter="16">
          <el-col :span="6">
            <el-card><el-statistic title="总收益率"><template #default>{{ fmtPct(result.total_return) }}</template></el-statistic></el-card>
          </el-col>
          <el-col :span="6">
            <el-card><el-statistic title="年化收益率"><template #default>{{ fmtPct(result.annual_return) }}</template></el-statistic></el-card>
          </el-col>
          <el-col :span="6">
            <el-card><el-statistic title="最大回撤"><template #default>{{ fmtPct(result.max_drawdown) }}</template></el-statistic></el-card>
          </el-col>
          <el-col :span="6">
            <el-card><el-statistic title="夏普比率"><template #default>{{ fmtNum(result.sharpe_ratio) }}</template></el-statistic></el-card>
          </el-col>
        </el-row>

        <el-row :gutter="16" style="margin-top: 16px">
          <el-col :span="6">
            <el-card><el-statistic title="胜率"><template #default>{{ fmtPct(result.win_rate) }}</template></el-statistic></el-card>
          </el-col>
          <el-col :span="6">
            <el-card><el-statistic title="盈亏比"><template #default>{{ fmtNum(result.profit_loss_ratio) }}</template></el-statistic></el-card>
          </el-col>
          <el-col :span="6">
            <el-card><el-statistic title="交易次数"><template #default>{{ result.trade_count ?? '-' }}</template></el-statistic></el-card>
          </el-col>
          <el-col :span="6">
            <el-card><el-statistic title="超额收益"><template #default>{{ fmtPct(result.excess_return) }}</template></el-statistic></el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- Risk -->
      <el-tab-pane label="风险指标" name="risk">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="年化波动率">{{ fmtPct(result.annual_volatility) }}</el-descriptions-item>
          <el-descriptions-item label="最大回撤天数">{{ result.max_drawdown_days ?? "-" }}</el-descriptions-item>
          <el-descriptions-item label="卡尔马比率">{{ fmtNum(result.calmar_ratio) }}</el-descriptions-item>
          <el-descriptions-item label="索提诺比率">{{ fmtNum(result.sortino_ratio) }}</el-descriptions-item>
          <el-descriptions-item label="最大单笔盈利">{{ result.max_single_profit != null ? '¥' + result.max_single_profit.toFixed(2) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="最大单笔亏损">{{ result.max_single_loss != null ? '¥' + result.max_single_loss.toFixed(2) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="平均持仓天数">{{ result.avg_hold_days?.toFixed(1) ?? "-" }}</el-descriptions-item>
          <el-descriptions-item label="基准收益率">{{ fmtPct(result.benchmark_return) }}</el-descriptions-item>
        </el-descriptions>
      </el-tab-pane>

      <!-- Trades -->
      <el-tab-pane label="交易明细" name="trades">
        <el-table :data="trades" stripe max-height="500">
          <el-table-column prop="stock_code" label="代码" width="110" />
          <el-table-column prop="buy_date" label="买入日" width="110" />
          <el-table-column prop="buy_price" label="买入价" width="90">
            <template #default="{ row }">{{ row.buy_price?.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="sell_date" label="卖出日" width="110" />
          <el-table-column prop="sell_price" label="卖出价" width="90">
            <template #default="{ row }">{{ row.sell_price?.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="quantity" label="数量" width="80" />
          <el-table-column prop="hold_days" label="持有天数" width="90" />
          <el-table-column prop="return_rate" label="收益率" width="90">
            <template #default="{ row }">
              <span :style="{ color: row.return_rate >= 0 ? '#67c23a' : '#f56c6c' }">
                {{ row.return_rate != null ? (row.return_rate * 100).toFixed(2) + '%' : '-' }}
              </span>
            </template>
          </el-table-column>
          <template #empty><el-empty description="暂无交易记录" /></template>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.backtest-detail {
  max-width: 1200px;
}
.top-bar {
  display: flex;
  align-items: center;
}
</style>
