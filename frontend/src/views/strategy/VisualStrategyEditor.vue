<script setup lang="ts">
// Visual strategy editor — core page, P0
import { ref } from "vue";

const strategyName = ref("");
const strategyDesc = ref("");

// Mock indicator library
const indicators = [
  { category: "趋势类", items: [
    { name: "MA", params: [5, 10, 20, 60, 120, 250] },
    { name: "EMA", params: [12, 26] },
    { name: "MACD", params: [12, 26, 9] },
    { name: "BOLL", params: [20, 2] },
  ]},
  { category: "动量类", items: [
    { name: "RSI", params: [6, 14] },
    { name: "KDJ", params: [9, 3, 3] },
  ]},
  { category: "量能类", items: [
    { name: "VOL", params: [] },
    { name: "换手率", params: [] },
  ]},
];

// Risk control config
const riskControl = ref({
  maxPositionRatio: 0.3,
  maxHoldings: 10,
  stopLoss: 0.08,
  takeProfit: 0.15,
});
</script>

<template>
  <div class="visual-editor">
    <h2>可视化策略编辑器</h2>
    <p class="subtitle">拖拽式多指标组合策略创建 — MVP 版本</p>

    <el-row :gutter="16">
      <!-- Indicator Library -->
      <el-col :span="6">
        <el-card header="指标组件库">
          <div v-for="group in indicators" :key="group.category" class="indicator-group">
            <h4>{{ group.category }}</h4>
            <el-tag
              v-for="item in group.items"
              :key="item.name"
              class="indicator-tag"
              type="info"
            >
              {{ item.name }}
            </el-tag>
          </div>
        </el-card>
      </el-col>

      <!-- Rule Editor -->
      <el-col :span="12">
        <el-card header="条件编辑区">
          <div class="rule-section">
            <h4>📈 买入条件组</h4>
            <el-empty description="拖拽指标到此处配置买入条件" :image-size="60" />
          </div>
          <el-divider />
          <div class="rule-section">
            <h4>📉 卖出条件组</h4>
            <el-empty description="拖拽指标到此处配置卖出条件" :image-size="60" />
          </div>
          <el-divider />
          <div class="rule-section">
            <h4>🛡️ 仓位与风控</h4>
            <el-form label-width="140px" size="small">
              <el-form-item label="单票最大仓位">
                <el-input-number v-model="riskControl.maxPositionRatio" :min="0.01" :max="1" :step="0.05" />
                <span class="unit">(比例)</span>
              </el-form-item>
              <el-form-item label="最大持仓数">
                <el-input-number v-model="riskControl.maxHoldings" :min="1" :max="100" />
                <span class="unit">只</span>
              </el-form-item>
              <el-form-item label="止损比例">
                <el-input-number v-model="riskControl.stopLoss" :min="0.01" :max="0.5" :step="0.01" />
              </el-form-item>
              <el-form-item label="止盈比例">
                <el-input-number v-model="riskControl.takeProfit" :min="0.01" :max="1" :step="0.01" />
              </el-form-item>
            </el-form>
          </div>
        </el-card>
      </el-col>

      <!-- Preview Panel -->
      <el-col :span="6">
        <el-card header="策略信息">
          <el-form label-position="top" size="small">
            <el-form-item label="策略名称">
              <el-input v-model="strategyName" placeholder="输入策略名称" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input
                v-model="strategyDesc"
                type="textarea"
                :rows="3"
                placeholder="描述策略逻辑"
              />
            </el-form-item>
          </el-form>
        </el-card>
        <el-card header="操作" style="margin-top: 12px">
          <el-button type="primary" style="width: 100%; margin-bottom: 8px">
            保存策略
          </el-button>
          <el-button style="width: 100%; margin-bottom: 8px">
            立即选股
          </el-button>
          <el-button type="success" style="width: 100%">
            立即回测
          </el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.visual-editor h2 {
  margin-bottom: 4px;
}
.subtitle {
  color: #909399;
  margin-bottom: 20px;
}
.indicator-group {
  margin-bottom: 12px;
}
.indicator-group h4 {
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
}
.indicator-tag {
  margin: 2px;
  cursor: grab;
}
.rule-section h4 {
  font-size: 14px;
  margin-bottom: 8px;
}
.unit {
  margin-left: 8px;
  font-size: 12px;
  color: #909399;
}
</style>
