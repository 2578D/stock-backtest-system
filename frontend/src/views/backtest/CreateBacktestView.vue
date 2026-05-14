<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { strategyApi, backtestApi, dataApi } from "@/api";
import { ElMessage } from "element-plus";
import { Plus, Close } from "@element-plus/icons-vue";

const router = useRouter();
const route = useRoute();
const submitting = ref(false);

const form = ref({
  strategyId: (route.query.strategyId as string) || "",
  name: "",
  startDate: "",
  endDate: "",
  initialCapital: 1000000,
  positionMode: "fixed",
  period: "daily",
  benchmark: "000300.SH",
  adjustMode: "forward",
});

// Stock pool management
const stockCodes = ref<string[]>([]);
const stockInput = ref("");
const stockSuggestions = ref<{ code: string; name: string }[]>([]);
const stockSearching = ref(false);
let searchTimer: ReturnType<typeof setTimeout> | null = null;

function onStockInput(val: string) {
  if (searchTimer) clearTimeout(searchTimer);
  if (!val.trim()) {
    stockSuggestions.value = [];
    return;
  }
  searchTimer = setTimeout(async () => {
    stockSearching.value = true;
    try {
      const res = await dataApi.listStocks({ keyword: val, page_size: 10 });
      const list = res.data?.data || [];
      stockSuggestions.value = list.map((s: any) => ({ code: s.code, name: s.name }));
    } catch { /* ignore */ }
    finally { stockSearching.value = false; }
  }, 300);
}

// Wrapper for el-autocomplete fetch-suggestions callback
function fetchSuggestions(q: string, cb: (items: { value: string; code: string }[]) => void) {
  onStockInput(q);
  // Wait for debounce then resolve
  setTimeout(() => {
    cb(stockSuggestions.value.map(s => ({ value: `${s.code} ${s.name}`, code: s.code })));
  }, 350);
}

function addStock(code: string) {
  const clean = code.trim().toUpperCase();
  if (clean && !stockCodes.value.includes(clean)) {
    stockCodes.value.push(clean);
  }
  stockInput.value = "";
  stockSuggestions.value = [];
}

function removeStock(code: string) {
  stockCodes.value = stockCodes.value.filter(c => c !== code);
}

// Batch add from comma/newline separated input
function batchAdd() {
  const codes = stockInput.value
    .split(/[\n,，]+/)
    .map(c => c.trim())
    .filter(Boolean);
  for (const c of codes) {
    if (!stockCodes.value.includes(c)) {
      stockCodes.value.push(c);
    }
  }
  stockInput.value = "";
}

const strategies = ref<{ id: string; name: string }[]>([]);

onMounted(async () => {
  try {
    const res = await strategyApi.list();
    strategies.value = (res.data || []).map((s: any) => ({ id: s.id, name: s.name }));
  } catch { /* ignore */ }

  // Default date range: last year
  const now = new Date();
  form.value.endDate = now.toISOString().slice(0, 10);
  now.setFullYear(now.getFullYear() - 1);
  form.value.startDate = now.toISOString().slice(0, 10);
});

async function submit() {
  if (!form.value.strategyId) {
    ElMessage.warning("请选择策略");
    return;
  }
  if (!form.value.startDate || !form.value.endDate) {
    ElMessage.warning("请选择日期范围");
    return;
  }
  if (!stockCodes.value.length) {
    ElMessage.warning("请添加至少一只股票代码");
    return;
  }

  submitting.value = true;
  try {
    const payload: any = {
      strategy_id: form.value.strategyId,
      name: form.value.name || undefined,
      start_date: form.value.startDate,
      end_date: form.value.endDate,
      initial_capital: form.value.initialCapital,
      position_mode: form.value.positionMode,
      period: form.value.period,
      benchmark: form.value.benchmark,
      adjust_mode: form.value.adjustMode,
      stock_pool: { symbols: stockCodes.value },
      cost_config: {},
    };
    const res = await backtestApi.create(payload);
    const taskId = res.data?.task_id;
    ElMessage.success("回测任务已创建");
    router.push(`/backtests/${taskId}`);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "创建失败");
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="create-backtest">
    <h2>新建回测</h2>

    <el-card style="max-width: 800px">
      <el-form :model="form" label-width="140px">
        <el-form-item label="选择策略" required>
          <el-select v-model="form.strategyId" placeholder="请选择策略" style="width: 100%">
            <el-option v-for="s in strategies" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="回测股票池" required>
          <div style="width: 100%">
            <!-- Tags -->
            <div class="stock-tags" v-if="stockCodes.length">
              <el-tag
                v-for="code in stockCodes" :key="code"
                closable type="info"
                size="small"
                @close="removeStock(code)"
                style="margin: 0 6px 6px 0"
              >
                {{ code }}
              </el-tag>
            </div>
            <div style="display: flex; gap: 8px">
              <el-autocomplete
                v-model="stockInput"
                :fetch-suggestions="fetchSuggestions"
                :trigger-on-focus="false"
                placeholder="输入股票代码搜索，如 000001"
                style="flex: 1"
                @select="(item: any) => addStock(item.code)"
                @keyup.enter="batchAdd"
                clearable
              >
                <template #default="{ item }">
                  <span>{{ item.value }}</span>
                </template>
              </el-autocomplete>
              <el-button @click="batchAdd">添加</el-button>
            </div>
            <div style="font-size: 12px; color: #909399; margin-top: 4px">
              支持逗号或换行分隔批量输入，如 000001.SZ, 600000.SH
            </div>
          </div>
        </el-form-item>

        <el-form-item label="回测日期范围" required>
          <el-date-picker v-model="form.startDate" type="date" placeholder="起始日期" style="width: calc(50% - 6px)" />
          <span style="margin: 0 4px">至</span>
          <el-date-picker v-model="form.endDate" type="date" placeholder="结束日期" style="width: calc(50% - 6px)" />
        </el-form-item>

        <el-form-item label="初始资金">
          <el-input-number v-model="form.initialCapital" :min="10000" :step="100000" style="width: 100%" />
        </el-form-item>

        <el-form-item label="仓位分配">
          <el-radio-group v-model="form.positionMode">
            <el-radio-button value="fixed">固定金额</el-radio-button>
            <el-radio-button value="percent">百分比</el-radio-button>
            <el-radio-button value="equal_weight">等权重</el-radio-button>
          </el-radio-group>
          <div style="font-size: 12px; color: #909399; margin-top: 4px">
            <template v-if="form.positionMode === 'fixed'">每笔交易固定 5 万元</template>
            <template v-else-if="form.positionMode === 'percent'">每次买入总资金的 3%</template>
            <template v-else>总资金在股票池中平均分配</template>
          </div>
        </el-form-item>

        <el-form-item label="K线周期">
          <el-radio-group v-model="form.period">
            <el-radio-button value="daily">日线</el-radio-button>
            <el-radio-button value="weekly">周线</el-radio-button>
            <el-radio-button value="monthly">月线</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="基准指数">
          <el-select v-model="form.benchmark" style="width: 100%">
            <el-option label="沪深300" value="000300.SH" />
            <el-option label="中证500" value="000905.SH" />
            <el-option label="上证指数" value="000001.SH" />
          </el-select>
        </el-form-item>

        <el-form-item label="复权方式">
          <el-radio-group v-model="form.adjustMode">
            <el-radio value="forward">前复权</el-radio>
            <el-radio value="backward">后复权</el-radio>
            <el-radio value="none">不复权</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" size="large" style="width: 100%" @click="submit" :loading="submitting">
            开始回测
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.create-backtest h2 { margin-bottom: 20px; }
.stock-tags { margin-bottom: 8px; }
</style>
