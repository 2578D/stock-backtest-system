<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { strategyApi } from "@/api";
import { ElMessage } from "element-plus";

const router = useRouter();
const strategyName = ref("");
const strategyDesc = ref("");
const saving = ref(false);

// Available indicators for dropdown
const indicatorOptions = [
  { label: "MA 均线", value: "ma" },
  { label: "EMA 指数均线", value: "ema" },
  { label: "MACD 快慢线", value: "macd" },
  { label: "RSI 相对强弱", value: "rsi" },
  { label: "KDJ 随机指标", value: "kdj" },
  { label: "BOLL 布林带", value: "boll" },
  { label: "成交量", value: "volume" },
  { label: "换手率", value: "turnover" },
  { label: "涨跌幅", value: "change_pct" },
  { label: "金叉", value: "cross_up" },
  { label: "死叉", value: "cross_down" },
];

// Operator options
const operators = [
  { label: "> (大于)", value: ">" },
  { label: "< (小于)", value: "<" },
  { label: ">= (大于等于)", value: ">=" },
  { label: "<= (小于等于)", value: "<=" },
  { label: "上穿 (金叉)", value: "cross_above" },
  { label: "下穿 (死叉)", value: "cross_below" },
];

interface Condition {
  indicator: string;
  params: string;     // e.g. "5" for MA(5), "12,26" for MACD
  operator: string;
  threshold: string;  // e.g. "30" or "ma20" for cross
}

const buyConditions = ref<Condition[]>([{ indicator: "ma", params: "5", operator: ">", threshold: "10" }]);
const sellConditions = ref<Condition[]>([{ indicator: "ma", params: "5", operator: "<", threshold: "10" }]);

function addBuy() { buyConditions.value.push({ indicator: "ma", params: "5", operator: ">", threshold: "10" }); }
function addSell() { sellConditions.value.push({ indicator: "ma", params: "5", operator: "<", threshold: "10" }); }
function removeBuy(i: number) { buyConditions.value.splice(i, 1); }
function removeSell(i: number) { sellConditions.value.splice(i, 1); }

function indicatorLabel(c: Condition): string {
  const ind = indicatorOptions.find(o => o.value === c.indicator);
  const name = ind?.label || c.indicator;
  if (c.params) return `${name}(${c.params})`;
  return name;
}
function conditionExpr(c: Condition): string {
  const op = operators.find(o => o.value === c.operator);
  return `${indicatorLabel(c)} ${op?.label || c.operator} ${c.threshold}`;
}

const riskControl = ref({ maxPositionRatio: 0.3, maxHoldings: 10, stopLoss: 0.08, takeProfit: 0.15 });

async function save() {
  if (!strategyName.value.trim()) { ElMessage.warning("请输入策略名称"); return; }
  saving.value = true;
  try {
    await strategyApi.create({
      name: strategyName.value.trim(),
      description: strategyDesc.value.trim(),
      type: "visual",
      rules_json: {
        buy: buyConditions.value,
        sell: sellConditions.value,
        risk: riskControl.value,
      },
    });
    ElMessage.success("策略已保存");
    router.push("/strategies");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  } finally { saving.value = false; }
}
</script>

<template>
  <div class="editor">
    <h2>可视化策略编辑器</h2>

    <el-row :gutter="16">
      <!-- Conditions -->
      <el-col :span="16">
        <!-- Buy -->
        <el-card>
          <template #header>
            <div class="card-hd">
              <span>📈 买入条件</span>
              <el-button size="small" type="primary" @click="addBuy">+ 添加条件</el-button>
            </div>
          </template>
          <div v-if="buyConditions.length === 0" class="empty">暂无买入条件，点击上方按钮添加</div>
          <div v-for="(c, i) in buyConditions" :key="'b'+i" class="cond-row">
            <el-select v-model="c.indicator" size="small" style="width: 140px">
              <el-option v-for="o in indicatorOptions" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-input v-model="c.params" size="small" placeholder="参数 (如 5,10)" style="width: 110px" />
            <el-select v-model="c.operator" size="small" style="width: 150px">
              <el-option v-for="o in operators" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-input v-model="c.threshold" size="small" placeholder="阈值" style="width: 100px" />
            <span class="expr-preview">{{ conditionExpr(c) }}</span>
            <el-button size="small" type="danger" circle @click="removeBuy(i)">−</el-button>
          </div>
        </el-card>

        <!-- Sell -->
        <el-card style="margin-top: 12px">
          <template #header>
            <div class="card-hd">
              <span>📉 卖出条件</span>
              <el-button size="small" type="danger" @click="addSell">+ 添加条件</el-button>
            </div>
          </template>
          <div v-if="sellConditions.length === 0" class="empty">暂无卖出条件，点击上方按钮添加</div>
          <div v-for="(c, i) in sellConditions" :key="'s'+i" class="cond-row">
            <el-select v-model="c.indicator" size="small" style="width: 140px">
              <el-option v-for="o in indicatorOptions" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-input v-model="c.params" size="small" placeholder="参数 (如 5,10)" style="width: 110px" />
            <el-select v-model="c.operator" size="small" style="width: 150px">
              <el-option v-for="o in operators" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-input v-model="c.threshold" size="small" placeholder="阈值" style="width: 100px" />
            <span class="expr-preview">{{ conditionExpr(c) }}</span>
            <el-button size="small" type="danger" circle @click="removeSell(i)">−</el-button>
          </div>
        </el-card>

        <!-- Risk -->
        <el-card style="margin-top: 12px">
          <template #header><span>🛡️ 风控参数</span></template>
          <el-form :inline="true" size="small">
            <el-form-item label="单票仓位 ≤">
              <el-input-number v-model="riskControl.maxPositionRatio" :min="0.01" :max="1" :step="0.05" />
            </el-form-item>
            <el-form-item label="最大持仓 ≤">
              <el-input-number v-model="riskControl.maxHoldings" :min="1" :max="100" /> 只
            </el-form-item>
            <el-form-item label="止损">
              <el-input-number v-model="riskControl.stopLoss" :min="0.01" :max="0.5" :step="0.01" />
            </el-form-item>
            <el-form-item label="止盈">
              <el-input-number v-model="riskControl.takeProfit" :min="0.01" :max="1" :step="0.01" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- Sidebar -->
      <el-col :span="8">
        <el-card header="策略信息">
          <el-form label-position="top" size="small">
            <el-form-item label="策略名称" required>
              <el-input v-model="strategyName" placeholder="输入策略名称" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="strategyDesc" type="textarea" :rows="3" placeholder="描述策略逻辑" />
            </el-form-item>
          </el-form>
          <el-button type="primary" style="width: 100%; margin-top: 12px" @click="save" :loading="saving">保存策略</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.editor h2 { margin-bottom: 16px; }
.card-hd { display: flex; justify-content: space-between; align-items: center; }
.cond-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; padding: 8px; background: #fafafa; border-radius: 6px; }
.expr-preview { font-size: 12px; color: #909399; font-family: monospace; min-width: 180px; }
.empty { color: #c0c4cc; text-align: center; padding: 20px; }
</style>
