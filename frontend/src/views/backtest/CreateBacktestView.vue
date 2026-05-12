<script setup lang="ts">
import { ref } from "vue";

const form = ref({
  strategyId: "",
  startDate: "",
  endDate: "",
  stockPool: "custom",
  initialCapital: 1000000,
  positionMode: "fixed",
  benchmark: "000300.SH",
  adjustMode: "forward",
  commission: 0.0003,
  stampTax: 0.001,
});

const strategies = ref<{ id: string; name: string }[]>([]);
</script>

<template>
  <div class="create-backtest">
    <h2>新建回测</h2>

    <el-card style="max-width: 800px">
      <el-form :model="form" label-width="140px">
        <el-form-item label="选择策略" required>
          <el-select v-model="form.strategyId" placeholder="请选择策略" style="width: 100%">
            <el-option
              v-for="s in strategies"
              :key="s.id"
              :label="s.name"
              :value="s.id"
            />
          </el-select>
          <div style="margin-top: 4px">
            <el-button type="primary" link>或新建策略</el-button>
          </div>
        </el-form-item>

        <el-form-item label="回测日期范围" required>
          <el-date-picker
            v-model="form.startDate"
            type="date"
            placeholder="起始日期"
            style="width: calc(50% - 6px)"
          />
          <span style="margin: 0 4px">至</span>
          <el-date-picker
            v-model="form.endDate"
            type="date"
            placeholder="结束日期"
            style="width: calc(50% - 6px)"
          />
        </el-form-item>

        <el-form-item label="初始资金">
          <el-input-number
            v-model="form.initialCapital"
            :min="10000"
            :step="100000"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="仓位模式">
          <el-radio-group v-model="form.positionMode">
            <el-radio value="fixed">固定仓位</el-radio>
            <el-radio value="equal">等权分配</el-radio>
            <el-radio value="ratio">按资金比例</el-radio>
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

        <el-divider>交易成本</el-divider>

        <el-form-item label="佣金">
          <el-input-number v-model="form.commission" :min="0" :step="0.0001" :precision="4" style="width: 100%" />
          <span class="hint">默认万3</span>
        </el-form-item>

        <el-form-item label="印花税">
          <el-input-number v-model="form.stampTax" :min="0" :step="0.001" :precision="3" style="width: 100%" />
          <span class="hint">卖出时千1</span>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" size="large" style="width: 100%">
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
.hint {
  margin-left: 8px;
  font-size: 12px;
  color: #909399;
}
</style>
