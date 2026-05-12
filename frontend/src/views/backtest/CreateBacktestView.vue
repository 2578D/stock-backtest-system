<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { strategyApi, backtestApi } from "@/api";
import { ElMessage } from "element-plus";

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
  benchmark: "000300.SH",
  adjustMode: "forward",
  stockPool: {} as Record<string, any>,
});

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

  submitting.value = true;
  try {
    const payload: any = {
      strategy_id: form.value.strategyId,
      name: form.value.name || undefined,
      start_date: form.value.startDate,
      end_date: form.value.endDate,
      initial_capital: form.value.initialCapital,
      position_mode: form.value.positionMode,
      benchmark: form.value.benchmark,
      adjust_mode: form.value.adjustMode,
      stock_pool: form.value.stockPool,
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

        <el-form-item label="回测日期范围" required>
          <el-date-picker v-model="form.startDate" type="date" placeholder="起始日期" style="width: calc(50% - 6px)" />
          <span style="margin: 0 4px">至</span>
          <el-date-picker v-model="form.endDate" type="date" placeholder="结束日期" style="width: calc(50% - 6px)" />
        </el-form-item>

        <el-form-item label="初始资金">
          <el-input-number v-model="form.initialCapital" :min="10000" :step="100000" style="width: 100%" />
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
.create-backtest h2 {
  margin-bottom: 20px;
}
</style>
