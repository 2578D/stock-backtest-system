<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from "vue";
import { useRoute } from "vue-router";
import { backtestApi } from "@/api";
import * as echarts from "echarts";

const route = useRoute();
const taskId = route.params.id as string;
const loading = ref(false);
const task = ref<any>({});
const result = ref<any>({});
const trades = ref<any[]>([]);
const activeTab = ref("overview");

const chartRef = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

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

    // Render chart after data arrives
    await nextTick();
    renderChart();

    // Auto-refresh if running
    if (task.value.status === "running" || task.value.status === "pending") {
      setTimeout(load, 3000);
    }
  } finally {
    loading.value = false;
  }
}

function renderChart() {
  if (!chartRef.value) return;
  const eq = result.value.equity_curve;
  if (!eq || typeof eq !== "object") return;

  // equity_curve: { "2024-01-02": 1000123.45, ... }
  const dates = Object.keys(eq).sort();
  const navs = dates.map((d) => Number(eq[d]));
  const initialCapital = task.value.initial_capital || 1000000;
  const pcts = navs.map((v) => ((v - initialCapital) / initialCapital) * 100);

  // Build daily return data
  const dailyRets = result.value.daily_returns;
  const retValues: number[] = [];
  if (Array.isArray(dailyRets)) {
    for (let i = 0; i < dates.length; i++) {
      retValues.push(Number(dailyRets[i] || 0) * 100);
    }
  }

  // Benchmark curve: cumulative NAV from daily returns
  const benchRets = result.value.benchmark_curve || {};
  let benchNav = initialCapital;
  const benchDateIdx: Record<string, number> = {};
  const benchNavs: number[] = [];
  const benchDates = Object.keys(benchRets).sort();
  for (const d of benchDates) {
    benchNav *= (1 + Number(benchRets[d]));
    benchNavs.push(benchNav);
    benchDateIdx[d] = benchNavs.length - 1;
  }
  const benchAligned: (number | null)[] = dates.map((d) =>
    benchDateIdx[d] !== undefined ? benchNavs[benchDateIdx[d]] : null
  );

  // Max drawdown region
  let drawdownStart = 0;
  let drawdownEnd = 0;
  let peak = navs[0];
  let peakIdx = 0;
  let maxDD = 0;
  for (let i = 0; i < navs.length; i++) {
    if (navs[i] > peak) { peak = navs[i]; peakIdx = i; }
    const dd = (peak - navs[i]) / peak;
    if (dd > maxDD) { maxDD = dd; drawdownStart = peakIdx; drawdownEnd = i; }
  }
  const markArea = maxDD > 0.01 ? {
    data: [[{ xAxis: dates[drawdownStart] }, { xAxis: dates[drawdownEnd] }]],
    itemStyle: { color: "rgba(245, 108, 108, 0.1)" },
    label: { show: true, formatter: "最大回撤", position: "insideTop", color: "#f56c6c", fontSize: 11 },
  } : undefined;

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value);
  }

  chartInstance.setOption({
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      formatter(params: any) {
        const d = params[0]?.axisValue || "";
        const navItem = params.find((p: any) => p.seriesName === "资金曲线");
        const retItem = params.find((p: any) => p.seriesName === "日收益率");
        return `${d}<br/>${navItem ? `净值: ¥${Number(navItem.value).toLocaleString()}` : ""}${
          navItem ? ` (${navItem.data.pct?.toFixed(2)}%)` : ""
        }${retItem ? `<br/>日收益: ${retItem.value.toFixed(2)}%` : ""}`;
      },
    },
    legend: {
      data: ["资金曲线", "基准曲线", "日收益率"],
      top: 0,
    },
    grid: { top: 40, left: 70, right: 70, bottom: 40 },
    xAxis: {
      type: "category",
      data: dates,
      axisLabel: { formatter: (v: string) => v.slice(5) },
    },
    yAxis: [
      {
        type: "value",
        name: "净值 (¥)",
        axisLabel: { formatter: (v: number) => (v / 10000).toFixed(0) + "万" },
        splitLine: { lineStyle: { type: "dashed" } },
      },
      {
        type: "value",
        name: "日收益率 (%)",
        axisLabel: { formatter: "{value}%" },
        splitLine: { show: false },
      },
    ],
    dataZoom: [
      { type: "inside", start: 0, end: 100 },
      { type: "slider", bottom: 0, height: 20 },
    ],
    series: [
      {
        name: "资金曲线",
        type: "line",
        data: navs.map((v, i) => ({ value: v, pct: pcts[i] })),
        smooth: true,
        showSymbol: false,
        lineStyle: { color: "#409eff", width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(64,158,255,0.3)" },
            { offset: 1, color: "rgba(64,158,255,0.05)" },
          ]),
        },
        markArea: markArea,
      },
      // Benchmark curve
      ...(benchNavs.length > 0 ? [{
        name: "基准曲线",
        type: "line",
        data: benchAligned,
        smooth: true,
        showSymbol: false,
        lineStyle: { color: "#909399", width: 2, type: "dashed" as const },
        connectNulls: false,
      }] : []),
      ...(retValues.length > 0 ? [{
        name: "日收益率",
        type: "bar",
        yAxisIndex: 1,
        data: retValues.map((v) => {
          const color = v >= 0 ? "#e8590c33" : "#52c41a33";
          const border = v >= 0 ? "#e8590c" : "#52c41a";
          return { value: v, itemStyle: { color, borderColor: border, borderWidth: 1 } };
        }),
      }] : []),
    ],
  }, true);
}

// Watch for tab changes to resize chart
watch(activeTab, async (tab) => {
  if (tab === "overview") {
    await nextTick();
    chartInstance?.resize();
  }
});

function fmtPct(v: number | null | undefined) {
  if (v == null) return "-";
  return (v * 100).toFixed(2) + "%";
}
function fmtNum(v: number | null | undefined) {
  if (v == null) return "-";
  return v.toFixed(2);
}
function statusTag(s: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'info' | 'warning' | 'success' | 'danger'> = { pending: 'info', running: 'warning', completed: 'success', failed: 'danger' };
  return (map[s] as 'info' | 'warning' | 'success' | 'danger') || 'info';
}
function statusLabel(s: string) {
  const map: Record<string, string> = { pending: "等待中", running: "运行中", completed: "已完成", failed: "失败" };
  return map[s] || s;
}

onMounted(load);
onUnmounted(() => { chartInstance?.dispose(); });
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
        <el-row :gutter="16" class="metric-row">
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

        <el-row :gutter="16" style="margin-top: 16px" class="metric-row">
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

        <!-- Equity curve chart -->
        <el-card style="margin-top: 16px" v-if="result.equity_curve">
          <div ref="chartRef" style="width: 100%; height: 400px"></div>
        </el-card>
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
              <span :style="{ color: row.return_rate >= 0 ? '#e8590c' : '#52c41a' }">
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
.metric-row :deep(.el-col) {
  margin-bottom: 12px;
}
</style>
