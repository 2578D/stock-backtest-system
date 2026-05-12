<script setup lang="ts">
// Backtest detail view — results, charts, trades
import { ref } from "vue";

const activeTab = ref("overview");
</script>

<template>
  <div class="backtest-detail">
    <el-page-header content="回测详情" />

    <el-tabs v-model="activeTab" style="margin-top: 16px">
      <el-tab-pane label="收益概览" name="overview">
        <el-row :gutter="16">
          <el-col :span="6">
            <el-statistic title="总收益率" :value="0" suffix="%" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="年化收益率" :value="0" suffix="%" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="最大回撤" :value="0" suffix="%" />
          </el-col>
          <el-col :span="6">
            <el-statistic title="夏普比率" :value="0" />
          </el-col>
        </el-row>
        <el-card style="margin-top: 16px">
          <h4>资金曲线</h4>
          <el-empty description="图表区域 — 待实现 ECharts 资金曲线" :image-size="100" />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="风险指标" name="risk">
        <el-empty description="风险指标详情" />
      </el-tab-pane>

      <el-tab-pane label="交易统计" name="stats">
        <el-empty description="交易统计数据" />
      </el-tab-pane>

      <el-tab-pane label="交易明细" name="trades">
        <el-empty description="交易明细列表" />
      </el-tab-pane>

      <el-tab-pane label="图表分析" name="charts">
        <el-empty description="图表分析区域" />
      </el-tab-pane>

      <el-tab-pane label="K线复盘" name="replay">
        <el-empty description="K线复盘 — 开发中" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.backtest-detail {
  max-width: 1200px;
}
</style>
