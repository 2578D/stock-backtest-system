<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { strategyApi } from "@/api";
import { ElMessage } from "element-plus";

const router = useRouter();
const strategyName = ref("");
const strategyDesc = ref("");
const saving = ref(false);

// Indicator library
const indicators = [
  { category: "趋势类", items: [
    { name: "MA(5)", key: "ma5", desc: "5日均线" },
    { name: "MA(10)", key: "ma10", desc: "10日均线" },
    { name: "MA(20)", key: "ma20", desc: "20日均线" },
    { name: "MA(60)", key: "ma60", desc: "60日均线" },
    { name: "EMA(12)", key: "ema12", desc: "12日指数均线" },
    { name: "EMA(26)", key: "ema26", desc: "26日指数均线" },
    { name: "MACD", key: "macd", desc: "MACD指标" },
  ]},
  { category: "动量类", items: [
    { name: "RSI(14)", key: "rsi14", desc: "14日RSI" },
    { name: "KDJ", key: "kdj", desc: "KDJ随机指标" },
  ]},
  { category: "均线交叉", items: [
    { name: "金叉(5/20)", key: "golden_cross_5_20", desc: "MA5上穿MA20" },
    { name: "死叉(5/20)", key: "death_cross_5_20", desc: "MA5下穿MA20" },
    { name: "金叉(10/60)", key: "golden_cross_10_60", desc: "MA10上穿MA60" },
    { name: "死叉(10/60)", key: "death_cross_10_60", desc: "MA10下穿MA60" },
  ]},
  { category: "量能类", items: [
    { name: "放量突破", key: "vol_break", desc: "成交量突破N日均量" },
    { name: "缩量回调", key: "vol_shrink", desc: "成交量萎缩至N日均量以下" },
  ]},
];

// Buy / Sell conditions
const buyConditions = ref<{ key: string; name: string }[]>([]);
const sellConditions = ref<{ key: string; name: string }[]>([]);

function addBuy(item: { key: string; name: string }) {
  if (!buyConditions.value.find(c => c.key === item.key)) {
    buyConditions.value.push({ key: item.key, name: item.name });
  }
}
function addSell(item: { key: string; name: string }) {
  if (!sellConditions.value.find(c => c.key === item.key)) {
    sellConditions.value.push({ key: item.key, name: item.name });
  }
}
function removeBuy(idx: number) {
  buyConditions.value.splice(idx, 1);
}
function removeSell(idx: number) {
  sellConditions.value.splice(idx, 1);
}

const riskControl = ref({
  maxPositionRatio: 0.3,
  maxHoldings: 10,
  stopLoss: 0.08,
  takeProfit: 0.15,
});

async function save() {
  if (!strategyName.value.trim()) {
    ElMessage.warning("请输入策略名称");
    return;
  }
  saving.value = true;
  try {
    const rules = {
      buy: buyConditions.value.map(c => c.key),
      sell: sellConditions.value.map(c => c.key),
    };
    await strategyApi.create({
      name: strategyName.value.trim(),
      description: strategyDesc.value.trim(),
      type: "visual",
      rules_json: rules,
      risk_control: riskControl.value,
    });
    ElMessage.success("策略已保存");
    router.push("/strategies");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="visual-editor">
    <h2>可视化策略编辑器</h2>
    <p class="subtitle">点击指标添加条件 — 组合买卖规则即可创建策略</p>

    <el-row :gutter="16">
      <!-- Indicator Library -->
      <el-col :span="5">
        <el-card header="指标组件库">
          <div v-for="group in indicators" :key="group.category" class="indicator-group">
            <h4>{{ group.category }}</h4>
            <div class="tag-row">
              <el-tag
                v-for="item in group.items"
                :key="item.key"
                class="indicator-tag"
                effect="plain"
                @click="addBuy(item)"
              >
                {{ item.name }}
              </el-tag>
            </div>
            <div style="margin-top: 4px">
              <el-button
                v-for="item in group.items"
                :key="'sell-' + item.key"
                size="small"
                type="danger"
                plain
                style="margin: 2px; font-size: 11px"
                @click="addSell(item)"
              >
                {{ item.name }} → 卖出
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- Rule Editor -->
      <el-col :span="12">
        <el-card header="条件编辑区">
          <!-- Buy -->
          <div class="rule-section">
            <h4>📈 买入条件</h4>
            <div v-if="buyConditions.length === 0" class="empty-hint">
              点击左侧蓝色标签添加买入条件
            </div>
            <el-tag
              v-for="(c, idx) in buyConditions"
              :key="c.key"
              closable
              type="success"
              size="large"
              style="margin: 4px"
              @close="removeBuy(idx)"
            >
              {{ c.name }}
            </el-tag>
          </div>

          <el-divider />

          <!-- Sell -->
          <div class="rule-section">
            <h4>📉 卖出条件</h4>
            <div v-if="sellConditions.length === 0" class="empty-hint">
              点击左侧红色按钮添加卖出条件
            </div>
            <el-tag
              v-for="(c, idx) in sellConditions"
              :key="c.key"
              closable
              type="danger"
              size="large"
              style="margin: 4px"
              @close="removeSell(idx)"
            >
              {{ c.name }}
            </el-tag>
          </div>

          <el-divider />

          <!-- Risk -->
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

      <!-- Preview -->
      <el-col :span="7">
        <el-card header="策略信息">
          <el-form label-position="top" size="small">
            <el-form-item label="策略名称" required>
              <el-input v-model="strategyName" placeholder="输入策略名称" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="strategyDesc" type="textarea" :rows="3" placeholder="描述策略逻辑" />
            </el-form-item>
          </el-form>
        </el-card>

        <el-card header="策略预览" style="margin-top: 12px">
          <div class="preview-item">
            <strong>买入：</strong>
            <span v-if="buyConditions.length === 0" class="muted">未配置</span>
            <span v-else>{{ buyConditions.map(c => c.name).join(' + ') }}</span>
          </div>
          <div class="preview-item">
            <strong>卖出：</strong>
            <span v-if="sellConditions.length === 0" class="muted">未配置</span>
            <span v-else>{{ sellConditions.map(c => c.name).join(' + ') }}</span>
          </div>
          <div class="preview-item">
            <strong>仓位：</strong>单票 ≤ {{ (riskControl.maxPositionRatio * 100).toFixed(0) }}%
          </div>
          <div class="preview-item">
            <strong>风控：</strong>止损 {{ (riskControl.stopLoss * 100).toFixed(0) }}% / 止盈 {{ (riskControl.takeProfit * 100).toFixed(0) }}%
          </div>
        </el-card>

        <el-card header="操作" style="margin-top: 12px">
          <el-button type="primary" style="width: 100%; margin-bottom: 8px" @click="save" :loading="saving">
            保存策略
          </el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.visual-editor h2 { margin-bottom: 4px; }
.subtitle { color: #909399; margin-bottom: 20px; }
.indicator-group { margin-bottom: 14px; }
.indicator-group h4 { font-size: 13px; color: #606266; margin-bottom: 6px; }
.tag-row { display: flex; flex-wrap: wrap; gap: 4px; }
.indicator-tag { cursor: pointer; user-select: none; }
.indicator-tag:hover { opacity: 0.8; }
.rule-section { min-height: 60px; }
.rule-section h4 { font-size: 14px; margin-bottom: 8px; }
.empty-hint { color: #c0c4cc; font-size: 13px; text-align: center; padding: 20px; }
.unit { margin-left: 8px; font-size: 12px; color: #909399; }
.preview-item { margin-bottom: 8px; font-size: 13px; line-height: 1.6; }
.muted { color: #c0c4cc; }
</style>
