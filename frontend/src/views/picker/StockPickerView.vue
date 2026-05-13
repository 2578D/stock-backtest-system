<script setup lang="ts">
import { ref, onMounted } from "vue";
import { strategyApi, pickerApi } from "@/api";
import { ElMessage } from "element-plus";
import { Search } from "@element-plus/icons-vue";

const strategies = ref<{ id: string; name: string }[]>([]);
const strategyId = ref("");
const market = ref("all");
const excludeST = ref(true);
const excludeSuspend = ref(true);
const maxResults = ref(50);

const running = ref(false);
const pickResult = ref<{
  date: string;
  strategy: string;
  total: number;
  results: any[];
} | null>(null);

onMounted(async () => {
  try {
    const res = await strategyApi.list();
    strategies.value = (res.data.data || []).map((s: any) => ({
      id: s.id,
      name: s.name,
    }));
  } catch { /* ignore */ }
});

async function run() {
  if (!strategyId.value) {
    ElMessage.warning("请选择策略");
    return;
  }
  running.value = true;
  pickResult.value = null;
  try {
    const res = await pickerApi.run({
      strategy_id: strategyId.value,
      market: market.value,
      exclude_st: excludeST.value,
      exclude_suspend: excludeSuspend.value,
      max_results: maxResults.value,
    });
    pickResult.value = res.data.data;
    ElMessage.success(`扫描完成，选中 ${pickResult.value?.total || 0} 只股票`);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "选股失败");
  } finally {
    running.value = false;
  }
}
</script>

<template>
  <div class="stock-picker">
    <h2>策略选股器</h2>

    <el-row :gutter="16">
      <el-col :span="7">
        <el-card shadow="hover" header="筛选条件">
          <el-form label-position="top" size="small">
            <el-form-item label="选择策略" required>
              <el-select v-model="strategyId" placeholder="选择策略" style="width: 100%">
                <el-option v-for="s in strategies" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>

            <el-form-item label="选股范围">
              <el-radio-group v-model="market" style="width: 100%">
                <el-radio-button value="all">全市场</el-radio-button>
                <el-radio-button value="main">沪深主板</el-radio-button>
                <el-radio-button value="SH">沪市</el-radio-button>
                <el-radio-button value="SZ">深市</el-radio-button>
              </el-radio-group>
            </el-form-item>

            <el-form-item label="风险过滤">
              <el-checkbox v-model="excludeST">排除 ST</el-checkbox>
              <el-checkbox v-model="excludeSuspend">排除停牌</el-checkbox>
            </el-form-item>

            <el-form-item label="最大结果数">
              <el-input-number v-model="maxResults" :min="10" :max="200" :step="10" style="width: 100%" />
            </el-form-item>

            <el-button type="primary" style="width: 100%" @click="run" :loading="running">
              <el-icon><Search /></el-icon> 开始选股
            </el-button>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="17">
        <el-card shadow="hover">
          <template #header>
            <div class="result-header">
              <span>选股结果</span>
              <span v-if="pickResult" class="result-meta">
                {{ pickResult.date }} · {{ pickResult.strategy }} · {{ pickResult.total }} 只
              </span>
            </div>
          </template>

          <el-table :data="pickResult?.results || []" stripe max-height="520" v-loading="running" size="small">
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
            <template #empty>
              <el-empty description="选择策略，点击「开始选股」扫描全市场" />
            </template>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.stock-picker h2 { margin-bottom: 16px; }
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.result-meta {
  font-size: 12px;
  color: #909399;
}
</style>
