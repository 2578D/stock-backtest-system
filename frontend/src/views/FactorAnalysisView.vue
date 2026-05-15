<template>
  <div class="factor-analysis">
    <el-card class="config-card">
      <template #header>
        <div class="card-header">
          <span>因子研究</span>
          <el-tag v-if="selectedFactor" type="primary">{{ selectedFactor.label }}</el-tag>
        </div>
      </template>

      <el-form :model="config" label-width="100px" inline>
        <el-form-item label="因子">
          <el-select
            v-model="config.factorId"
            placeholder="选择因子"
            filterable
            @change="onFactorChange"
            style="width: 240px"
          >
            <el-option-group
              v-for="cat in factorCategories"
              :key="cat.value"
              :label="cat.label"
            >
              <el-option
                v-for="f in factorsByCategory[cat.value]"
                :key="f.id"
                :label="`${f.label} (${f.name})`"
                :value="f.id"
              />
            </el-option-group>
          </el-select>
        </el-form-item>

        <el-form-item label="回测区间">
          <el-date-picker
            v-model="config.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>

        <el-form-item label="分组数">
          <el-input-number v-model="config.groupCount" :min="3" :max="20" :step="1" />
        </el-form-item>

        <el-form-item label="未来N天">
          <el-input-number v-model="config.forwardDays" :min="1" :max="60" :step="1" />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            @click="startAnalysis"
            :loading="analyzing"
            :disabled="!canAnalyze"
          >
            {{ analyzing ? '分析中...' : '开始分析' }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Loading -->
    <el-card v-if="analyzing" class="status-card">
      <el-alert title="因子计算进行中..." type="info" :closable="false" show-icon>
        <template #default>
          正在对全市场股票计算因子值、分组回测、计算IC序列。数据量大，可能需要1-3分钟。
        </template>
      </el-alert>
    </el-card>

    <!-- Error -->
    <el-card v-if="resultError" class="status-card">
      <el-alert :title="resultError" type="error" show-icon :closable="false" />
    </el-card>

    <!-- Results -->
    <template v-if="currentAnalysis && currentAnalysis.status === 'completed'">
      <!-- Summary Cards -->
      <el-row :gutter="16" class="summary-row">
        <el-col :span="6">
          <el-statistic title="IC 均值" :value="currentAnalysis.ic_mean ?? 0" :precision="4" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="IC 标准差" :value="currentAnalysis.ic_std ?? 0" :precision="4" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="ICIR" :value="currentAnalysis.icir ?? 0" :precision="4" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="单调性" :value="currentAnalysis.monotonicity ?? 0" :precision="4" />
        </el-col>
      </el-row>

      <!-- Layer Returns Bar Chart -->
      <el-card>
        <template #header>分层收益（10组）</template>
        <div ref="layerChartRef" class="chart-container" />
      </el-card>

      <!-- IC Series Line Chart -->
      <el-card style="margin-top: 16px">
        <template #header>IC 序列</template>
        <div ref="icChartRef" class="chart-container" />
      </el-card>

      <!-- Layer Cumulative Returns -->
      <el-card style="margin-top: 16px">
        <template #header>分层累积收益曲线</template>
        <div ref="cumulativeChartRef" class="chart-container" />
      </el-card>
    </template>

    <!-- Empty state -->
    <el-empty
      v-if="!analyzing && !currentAnalysis && !resultError"
      description="选择因子和参数，点击「开始分析」查看结果"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import * as echarts from "echarts";
import { factorApi } from "@/api";

interface FactorDef {
  id: string;
  name: string;
  label: string;
  category: string;
  description: string | null;
}

interface AnalysisResult {
  id: string;
  factor_id: string;
  start_date: string;
  end_date: string;
  group_count: number;
  forward_days: number;
  ic_mean: number | null;
  ic_std: number | null;
  icir: number | null;
  ic_series: Record<string, number> | null;
  layer_returns: Record<string, number> | null;
  layer_cumulative: Record<string, Record<string, number>> | null;
  monotonicity: number | null;
  status: string;
}

const CATEGORY_LABELS: Record<string, string> = {
  reversal: "反转因子",
  momentum: "动量因子",
  volatility: "波动因子",
  volume: "量价因子",
  price_pattern: "价格形态因子",
  trend: "趋势因子",
};

const factors = ref<FactorDef[]>([]);
const analyzing = ref(false);
const resultError = ref("");
const currentAnalysis = ref<AnalysisResult | null>(null);

const config = reactive({
  factorId: "",
  dateRange: ["2023-01-01", "2025-12-31"] as string[],
  groupCount: 10,
  forwardDays: 10,
});

const factorCategories = computed(() => {
  const cats = new Set(factors.value.map((f) => f.category));
  return Array.from(cats).map((v) => ({
    value: v,
    label: CATEGORY_LABELS[v] || v,
  }));
});

const factorsByCategory = computed(() => {
  const map: Record<string, FactorDef[]> = {};
  for (const f of factors.value) {
    (map[f.category] ||= []).push(f);
  }
  return map;
});

const selectedFactor = computed(() =>
  factors.value.find((f) => f.id === config.factorId) || null
);

const canAnalyze = computed(
  () => config.factorId && config.dateRange[0] && config.dateRange[1] && !analyzing.value
);

// Charts
const layerChartRef = ref<HTMLDivElement | null>(null);
const icChartRef = ref<HTMLDivElement | null>(null);
const cumulativeChartRef = ref<HTMLDivElement | null>(null);

let layerChart: echarts.ECharts | null = null;
let icChart: echarts.ECharts | null = null;
let cumulativeChart: echarts.ECharts | null = null;

onMounted(() => {
  loadFactors();
});

function onFactorChange() {
  resultError.value = "";
  currentAnalysis.value = null;
}

async function loadFactors() {
  try {
    const res = await factorApi.list();
    factors.value = res.data;
  } catch (e) {
    console.error("Failed to load factors", e);
  }
}

async function startAnalysis() {
  analyzing.value = true;
  resultError.value = "";
  currentAnalysis.value = null;

  try {
    const res = await factorApi.analyze(config.factorId, {
      start_date: config.dateRange[0],
      end_date: config.dateRange[1],
      group_count: config.groupCount,
      forward_days: config.forwardDays,
    });

    // Poll for results
    await pollAnalysis();
  } catch (e: any) {
    resultError.value = e.response?.data?.detail || e.message || "分析失败";
    analyzing.value = false;
  }
}

async function pollAnalysis() {
  let attempts = 0;
  const maxAttempts = 60; // 3 min at 3s intervals

  const poll = async () => {
    try {
      const res = await factorApi.listAnalyses(config.factorId);
      const latest = res.data?.[0];

      if (latest?.status === "completed") {
        const detail = await factorApi.getAnalysis(config.factorId, latest.id);
        currentAnalysis.value = detail.data;
        analyzing.value = false;
        await nextTick();
        renderCharts();
        return;
      }

      if (latest?.status === "failed") {
        resultError.value = latest.error_message || "分析失败";
        analyzing.value = false;
        return;
      }

      attempts++;
      if (attempts < maxAttempts) {
        setTimeout(poll, 3000);
      } else {
        resultError.value = "分析超时，请稍后查看";
        analyzing.value = false;
      }
    } catch (e) {
      attempts++;
      if (attempts < maxAttempts) {
        setTimeout(poll, 3000);
      }
    }
  };

  poll();
}

function renderCharts() {
  renderLayerChart();
  renderICChart();
  renderCumulativeChart();
}

function renderLayerChart() {
  if (!layerChartRef.value || !currentAnalysis.value?.layer_returns) return;
  if (!layerChart) {
    layerChart = echarts.init(layerChartRef.value);
  }

  const data = currentAnalysis.value.layer_returns;
  const groups = Object.keys(data).sort((a, b) => Number(a) - Number(b));
  const values = groups.map((g) => data[g]);

  layerChart.setOption({
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: groups.map((g) => `G${Number(g) + 1}`),
      name: "分组（因子值低→高）",
    },
    yAxis: {
      type: "value",
      name: `${currentAnalysis.value.forward_days}日平均收益`,
      axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(2)}%` },
    },
    series: [
      {
        type: "bar",
        data: values.map((v, i) => ({
          value: v,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: "#5470c6" },
              { offset: 1, color: "#ee6666" },
            ]),
          },
        })),
        label: { show: true, formatter: (p: any) => `${(p.value * 100).toFixed(3)}%` },
      },
    ],
    grid: { top: 20, right: 20, bottom: 40, left: 80 },
  });
}

function renderICChart() {
  if (!icChartRef.value || !currentAnalysis.value?.ic_series) return;
  if (!icChart) {
    icChart = echarts.init(icChartRef.value);
  }

  const data = currentAnalysis.value.ic_series;
  const dates = Object.keys(data).sort();
  const values = dates.map((d) => data[d]);
  const icMean = currentAnalysis.value.ic_mean || 0;

  icChart.setOption({
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: dates,
      axisLabel: { show: false },
    },
    yAxis: {
      type: "value",
      name: "IC",
    },
    series: [
      {
        type: "line",
        data: values,
        showSymbol: false,
        lineStyle: { width: 1 },
      },
      {
        type: "line",
        data: [],
        markLine: {
          silent: true,
          data: [{ yAxis: icMean, label: { formatter: `均值: ${icMean.toFixed(4)}` } }],
          lineStyle: { color: "#e6a23c", type: "dashed" },
        },
      },
    ],
    grid: { top: 20, right: 20, bottom: 40, left: 60 },
  });
}

function renderCumulativeChart() {
  if (!cumulativeChartRef.value || !currentAnalysis.value?.layer_cumulative) return;
  if (!cumulativeChart) {
    cumulativeChart = echarts.init(cumulativeChartRef.value);
  }

  const data = currentAnalysis.value.layer_cumulative;
  const groups = Object.keys(data).sort((a, b) => Number(a) - Number(b));

  const colorPalette = [
    "#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de",
    "#3ba272", "#fc8452", "#9a60b4", "#ea7ccc", "#20c997",
  ];

  cumulativeChart.setOption({
    tooltip: { trigger: "axis" },
    legend: {
      data: groups.map((g) => `G${Number(g) + 1}`),
      bottom: 0,
    },
    xAxis: {
      type: "category",
      data: [] as string[],
      axisLabel: { show: false },
    },
    yAxis: {
      type: "value",
      name: "累积收益",
      axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(1)}%` },
    },
    series: [] as any[],
  });

  // Build datasets
  const allDates = new Set<string>();
  for (const g of groups) {
    for (const d of Object.keys(data[g] || {})) {
      allDates.add(d);
    }
  }
  const sortedDates = Array.from(allDates).sort();

  const series = groups.map((g, i) => {
    const groupData = data[g] || {};
    const values = sortedDates.map((d) => groupData[d] || null);
    return {
      name: `G${Number(g) + 1}`,
      type: "line",
      data: values,
      showSymbol: false,
      lineStyle: { width: 1.5 },
      itemStyle: { color: colorPalette[i % colorPalette.length] },
    };
  });

  cumulativeChart.setOption({
    xAxis: { data: sortedDates },
    series,
  });
}
</script>

<style scoped>
.factor-analysis {
  padding: 16px;
}

.config-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.summary-row {
  margin-bottom: 16px;
}

.chart-container {
  width: 100%;
  height: 350px;
}

.status-card {
  margin-bottom: 16px;
}

:deep(.el-statistic__number) {
  font-size: 20px;
}
</style>
