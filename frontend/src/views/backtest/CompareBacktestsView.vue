<script setup lang="ts">
import { ref, onMounted, nextTick } from "vue";
import { backtestApi } from "@/api";
import { ElMessage } from "element-plus";
import * as echarts from "echarts";

const backtests = ref<any[]>([]);
const selected = ref<string[]>([]);
const results = ref<any[]>([]);
const loading = ref(false);
const chartRef = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const colors = ["#409eff", "#e8590c", "#52c41a", "#722ed1", "#fa8c16"];

onMounted(async () => {
  try {
    const res = await backtestApi.list();
    backtests.value = (res.data.data || []).filter((b: any) => b.status === "completed");
  } catch {}
});

async function compare() {
  if (selected.value.length < 2) {
    ElMessage.warning("至少选择 2 个回测对比");
    return;
  }
  loading.value = true;
  results.value = [];

  for (const id of selected.value) {
    try {
      const [rRes, tRes] = await Promise.allSettled([
        backtestApi.getResult(id),
        backtestApi.get(id),
      ]);
      const task = tRes.status === "fulfilled" ? tRes.value.data : {};
      const result = rRes.status === "fulfilled" ? rRes.value.data : {};
      results.value.push({
        id,
        name: task.name || id.slice(0, 8),
        ...result,
      });
    } catch {}
  }

  loading.value = false;
  await nextTick();
  renderCompareChart();
}

function renderCompareChart() {
  if (!chartRef.value || results.value.length < 2) return;

  // Find the union of all dates
  const dateSet = new Set<string>();
  const equityData: { name: string; data: [string, number][] }[] = [];

  for (let i = 0; i < results.value.length; i++) {
    const eq = results.value[i].equity_curve || {};
    const dates = Object.keys(eq).sort();
    dates.forEach((d) => dateSet.add(d));
    equityData.push({
      name: results.value[i].name,
      data: dates.map((d) => [d, Number(eq[d])] as [string, number]),
    });
  }

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value);
  }

  chartInstance.setOption({
    title: { text: "资金曲线对比", left: "center", top: 0 },
    tooltip: { trigger: "axis" },
    legend: {
      data: equityData.map((e) => e.name),
      bottom: 0,
    },
    grid: { top: 50, left: 70, right: 30, bottom: 50 },
    xAxis: {
      type: "category",
      axisLabel: { formatter: (v: string) => v.slice(5) },
    },
    yAxis: {
      type: "value",
      name: "净值 (¥)",
      axisLabel: { formatter: (v: number) => (v / 10000).toFixed(0) + "万" },
    },
    dataZoom: [{ type: "inside" }, { type: "slider", bottom: 30, height: 15 }],
    series: equityData.map((e, i) => ({
      name: e.name,
      type: "line",
      data: e.data,
      smooth: true,
      showSymbol: false,
      lineStyle: { color: colors[i % colors.length], width: 2 },
    })),
  }, true);
}

function fmtPct(v: number | null | undefined) {
  if (v == null) return "-";
  return (v * 100).toFixed(2) + "%";
}
function fmtNum(v: number | null | undefined) {
  if (v == null) return "-";
  return v.toFixed(2);
}
</script>

<template>
  <div class="compare-view">
    <h2>回测对比</h2>

    <el-card style="margin-bottom: 16px">
      <div class="select-row">
        <el-select
          v-model="selected"
          multiple
          placeholder="选择已完成回测（2-5个）"
          style="flex: 1"
          :multiple-limit="5"
        >
          <el-option
            v-for="b in backtests"
            :key="b.id"
            :label="`${b.name} (${b.start_date}~${b.end_date})`"
            :value="b.id"
          />
        </el-select>
        <el-button type="primary" @click="compare" :loading="loading">对比</el-button>
      </div>
    </el-card>

    <!-- Metrics table -->
    <el-card v-if="results.length" style="margin-bottom: 16px">
      <el-table :data="results" border size="small">
        <el-table-column prop="name" label="策略" width="150" />
        <el-table-column label="总收益" width="100">
          <template #default="{ row }">{{ fmtPct(row.total_return) }}</template>
        </el-table-column>
        <el-table-column label="年化收益" width="100">
          <template #default="{ row }">{{ fmtPct(row.annual_return) }}</template>
        </el-table-column>
        <el-table-column label="最大回撤" width="100">
          <template #default="{ row }">{{ fmtPct(row.max_drawdown) }}</template>
        </el-table-column>
        <el-table-column label="夏普" width="80">
          <template #default="{ row }">{{ fmtNum(row.sharpe_ratio) }}</template>
        </el-table-column>
        <el-table-column label="胜率" width="80">
          <template #default="{ row }">{{ fmtPct(row.win_rate) }}</template>
        </el-table-column>
        <el-table-column label="交易次数" width="80">
          <template #default="{ row }">{{ row.trade_count ?? "-" }}</template>
        </el-table-column>
        <el-table-column label="超额收益" width="100">
          <template #default="{ row }">{{ fmtPct(row.excess_return) }}</template>
        </el-table-column>
        <el-table-column label="最大单笔盈" width="120">
          <template #default="{ row }">
            {{ row.max_single_profit != null ? "¥" + row.max_single_profit.toFixed(0) : "-" }}
          </template>
        </el-table-column>
        <el-table-column label="最大单笔亏" width="120">
          <template #default="{ row }">
            {{ row.max_single_loss != null ? "¥" + row.max_single_loss.toFixed(0) : "-" }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Chart -->
    <el-card v-if="results.length >= 2">
      <div ref="chartRef" style="width: 100%; height: 400px"></div>
    </el-card>
  </div>
</template>

<style scoped>
.compare-view { max-width: 1200px; }
.compare-view h2 { margin-bottom: 16px; }
.select-row { display: flex; gap: 12px; align-items: center; }
</style>
