<script setup lang="ts">
import { ref, onMounted } from "vue";
import { pickerApi, strategyApi } from "@/api";
import { ElMessage } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";

interface Signal {
  code: string;
  name: string;
  exchange: string;
  industry: string;
  close: number;
  change_pct: number | null;
  signal_reason: string;
}

interface StrategySignal {
  strategyId: string;
  strategyName: string;
  date: string;
  total: number;
  results: Signal[];
}

const signals = ref<StrategySignal[]>([]);
const strategies = ref<{ id: string; name: string }[]>([]);
const running = ref(false);
const loading = ref(true);

onMounted(async () => {
  try {
    const res = await strategyApi.list();
    strategies.value = (res.data.data || []).map((s: any) => ({
      id: s.id,
      name: s.name,
    }));
  } catch {}
  loading.value = false;
});

async function scanAll() {
  running.value = true;
  signals.value = [];
  let completed = 0;

  for (const s of strategies.value) {
    try {
      const res = await pickerApi.run({
        strategy_id: s.id,
        market: "all",
        exclude_st: true,
        exclude_suspend: true,
        max_results: 30,
      });
      const data = res.data.data;
      if (data.results?.length) {
        signals.value.push({
          strategyId: s.id,
          strategyName: data.strategy,
          date: data.date,
          total: data.total,
          results: data.results,
        });
      }
    } catch {}
    completed++;
    // Avoid rate limiting
    if (completed < strategies.value.length) {
      await new Promise((r) => setTimeout(r, 500));
    }
  }

  running.value = false;
  ElMessage.success(`扫描完成，${signals.value.length} 个策略产生信号`);
}
</script>

<template>
  <div class="daily-signals">
    <div class="header">
      <h2>每日信号</h2>
      <el-button type="primary" :loading="running" @click="scanAll" :icon="Refresh">
        {{ running ? "扫描中..." : "全策略扫描" }}
      </el-button>
    </div>

    <el-empty
      v-if="!running && !signals.length && !loading"
      description="点击「全策略扫描」，对所有启用策略运行选股器"
    />

    <div v-for="sg in signals" :key="sg.strategyId" style="margin-bottom: 16px">
      <el-card shadow="hover">
        <template #header>
          <div class="signal-header">
            <span class="strategy-name">{{ sg.strategyName }}</span>
            <span class="signal-meta">
              {{ sg.date }} · {{ sg.total }} 只信号
            </span>
          </div>
        </template>
        <el-table :data="sg.results" size="small" stripe max-height="320">
          <el-table-column prop="code" label="代码" width="110" />
          <el-table-column prop="name" label="名称" width="130" />
          <el-table-column prop="exchange" label="市场" width="70" />
          <el-table-column prop="industry" label="行业" min-width="120" show-overflow-tooltip />
          <el-table-column prop="close" label="最新价" width="90">
            <template #default="{ row }">{{ row.close?.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="change_pct" label="涨跌幅" width="90">
            <template #default="{ row }">
              <span :style="{ color: (row.change_pct || 0) >= 0 ? '#e8590c' : '#52c41a' }">
                {{ row.change_pct != null ? (row.change_pct > 0 ? '+' : '') + row.change_pct.toFixed(2) + '%' : '-' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="signal_reason" label="买入信号" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag type="success" size="small">{{ row.signal_reason }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.daily-signals { max-width: 1200px; }
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.header h2 { margin: 0; }
.signal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.strategy-name {
  font-weight: 600;
  font-size: 15px;
}
.signal-meta {
  font-size: 12px;
  color: #909399;
}
</style>
