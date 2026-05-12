<script setup lang="ts">
import { ref, watch } from "vue";
import { useRouter } from "vue-router";
import { strategyApi } from "@/api";
import { ElMessage } from "element-plus";

const router = useRouter();
const strategyName = ref("");
const strategyDesc = ref("");
const saving = ref(false);

// Indicator definitions with param config
interface IndicatorDef {
  label: string; category: string;
  params: { name: string; placeholder: string }[];  // empty = no params needed
  operators: string[];  // subset of operators applicable
  thresholdLabel: string;
}

const indicatorDefs: IndicatorDef[] = [
  // 趋势类
  { category: "趋势", label: "MA 简单均线",          params: [{ name: "周期", placeholder: "5" }],             operators: [">","<",">=","<="], thresholdLabel: "阈值" },
  { category: "趋势", label: "EMA 指数均线",         params: [{ name: "周期", placeholder: "12" }],            operators: [">","<",">=","<="], thresholdLabel: "阈值" },
  { category: "趋势", label: "BOLL 布林带",          params: [{ name: "周期", placeholder: "20" }],            operators: [">","<"],           thresholdLabel: "价格" },
  // 动量类
  { category: "动量", label: "MACD",                 params: [{ name: "快线", placeholder: "12" }, { name: "慢线", placeholder: "26" }, { name: "信号", placeholder: "9" }], operators: ["cross_above","cross_below"], thresholdLabel: "" },
  { category: "动量", label: "RSI 相对强弱",         params: [{ name: "周期", placeholder: "14" }],            operators: [">","<",">=","<="], thresholdLabel: "阈值" },
  { category: "动量", label: "KDJ 随机指标",         params: [{ name: "周期", placeholder: "9" }],             operators: ["cross_above","cross_below","<",">"], thresholdLabel: "阈值" },
  // 交叉类
  { category: "交叉", label: "金叉",                 params: [{ name: "快线周期", placeholder: "5" }, { name: "慢线周期", placeholder: "20" }], operators: [], thresholdLabel: "" },
  { category: "交叉", label: "死叉",                 params: [{ name: "快线周期", placeholder: "5" }, { name: "慢线周期", placeholder: "20" }], operators: [], thresholdLabel: "" },
  // 量能类
  { category: "量能", label: "成交量",               params: [],                                              operators: [">","<",">=","<="], thresholdLabel: "N日均量倍数" },
  { category: "量能", label: "换手率",               params: [],                                              operators: [">","<",">=","<="], thresholdLabel: "%" },
  // 价格类
  { category: "价格", label: "涨跌幅",               params: [],                                              operators: [">","<",">=","<="], thresholdLabel: "%" },
  { category: "价格", label: "收盘价",               params: [],                                              operators: [">","<",">=","<="], thresholdLabel: "价格" },
];

const operatorLabels: Record<string, string> = { ">": ">", "<": "<", ">=": "≥", "<=": "≤", "cross_above": "上穿", "cross_below": "下穿" };

interface Condition {
  defIndex: number;
  params: string[];
  operator: string;
  threshold: string;
}

const buyConditions = ref<Condition[]>([{ defIndex: 0, params: ["5"], operator: ">", threshold: "20" }]);
const sellConditions = ref<Condition[]>([{ defIndex: 0, params: ["5"], operator: "<", threshold: "20" }]);

function def(c: Condition) { return indicatorDefs[c.defIndex]; }
function paramNames(c: Condition) { return def(c).params; }
function showOperator(c: Condition) { return def(c).operators.length > 0; }
function showThreshold(c: Condition) { return def(c).thresholdLabel !== ""; }

// Reset operator/threshold when indicator changes
const buyWatched = ref<number[]>([]);
const sellWatched = ref<number[]>([]);
function resetOnChange(cond: Condition, idx: number, isBuy: boolean) {
  const d = indicatorDefs[cond.defIndex];
  if (d.operators.length > 0) cond.operator = d.operators[0];
  else cond.operator = "";
  if (d.params.length !== cond.params.length) {
    cond.params = d.params.map(() => "");
  }
}
function onIndicatorChange(c: Condition, i: number, isBuy: boolean) { resetOnChange(c, i, isBuy); }

function addBuy() { buyConditions.value.push({ defIndex: 0, params: ["5"], operator: ">", threshold: "20" }); }
function addSell() { sellConditions.value.push({ defIndex: 0, params: ["5"], operator: "<", threshold: "20" }); }
function removeBuy(i: number) { buyConditions.value.splice(i, 1); }
function removeSell(i: number) { sellConditions.value.splice(i, 1); }

function exprPreview(c: Condition): string {
  const d = def(c);
  let name = d.label;
  if (d.params.length) {
    const filled = c.params.filter(p => p).join(",");
    if (filled) name += `(${filled})`;
  }
  if (!showOperator(c)) return name;
  const op = operatorLabels[c.operator] || c.operator;
  if (!showThreshold(c)) return `${name} ${op}`;
  return `${name} ${op} ${c.threshold}`;
}

const riskControl = ref({ maxPositionRatio: 0.3, maxHoldings: 10, stopLoss: 0.08, takeProfit: 0.15 });

async function save() {
  if (!strategyName.value.trim()) { ElMessage.warning("请输入策略名称"); return; }
  saving.value = true;
  try {
    await strategyApi.create({
      name: strategyName.value.trim(), description: strategyDesc.value.trim(), type: "visual",
      rules_json: { buy: buyConditions.value, sell: sellConditions.value, risk: riskControl.value },
    });
    ElMessage.success("策略已保存");
    router.push("/strategies");
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || "保存失败"); }
  finally { saving.value = false; }
}

// Group indicators by category for dropdown
const groupedOptions = (() => {
  const cats = [...new Set(indicatorDefs.map(d => d.category))];
  return cats.map(cat => ({
    label: cat,
    options: indicatorDefs.filter(d => d.category === cat).map((d, i) => ({
      label: d.label, value: indicatorDefs.indexOf(d),
    })),
  }));
})();
</script>

<template>
  <div class="editor">
    <h2>可视化策略编辑器</h2>

    <el-row :gutter="16">
      <el-col :span="16">
        <!-- Buy -->
        <el-card>
          <template #header>
            <div class="card-hd"><span>📈 买入条件</span><el-button size="small" type="primary" @click="addBuy">+ 添加</el-button></div>
          </template>
          <div v-if="!buyConditions.length" class="empty">暂无买入条件</div>
          <div v-for="(c, i) in buyConditions" :key="'b'+i" class="cond-row">
            <el-select v-model="c.defIndex" size="small" style="width: 170px" @change="onIndicatorChange(c, i, true)">
              <el-option-group v-for="g in groupedOptions" :key="g.label" :label="g.label">
                <el-option v-for="o in g.options" :key="o.value" :label="o.label" :value="o.value" />
              </el-option-group>
            </el-select>
            <template v-for="(p, pi) in paramNames(c)" :key="pi">
              <span class="param-label">{{ p.name }}</span>
              <el-input v-model="c.params[pi]" size="small" :placeholder="p.placeholder" style="width: 70px" />
            </template>
            <template v-if="showOperator(c)">
              <el-select v-model="c.operator" size="small" style="width: 80px">
                <el-option v-for="op in def(c).operators" :key="op" :label="operatorLabels[op]" :value="op" />
              </el-select>
            </template>
            <template v-if="showThreshold(c)">
              <span class="param-label">{{ def(c).thresholdLabel }}</span>
              <el-input v-model="c.threshold" size="small" style="width: 80px" />
            </template>
            <span class="expr">{{ exprPreview(c) }}</span>
            <el-button size="small" type="danger" circle @click="removeBuy(i)">−</el-button>
          </div>
        </el-card>

        <!-- Sell -->
        <el-card style="margin-top: 12px">
          <template #header>
            <div class="card-hd"><span>📉 卖出条件</span><el-button size="small" type="danger" @click="addSell">+ 添加</el-button></div>
          </template>
          <div v-if="!sellConditions.length" class="empty">暂无卖出条件</div>
          <div v-for="(c, i) in sellConditions" :key="'s'+i" class="cond-row">
            <el-select v-model="c.defIndex" size="small" style="width: 170px" @change="onIndicatorChange(c, i, false)">
              <el-option-group v-for="g in groupedOptions" :key="g.label" :label="g.label">
                <el-option v-for="o in g.options" :key="o.value" :label="o.label" :value="o.value" />
              </el-option-group>
            </el-select>
            <template v-for="(p, pi) in paramNames(c)" :key="pi">
              <span class="param-label">{{ p.name }}</span>
              <el-input v-model="c.params[pi]" size="small" :placeholder="p.placeholder" style="width: 70px" />
            </template>
            <template v-if="showOperator(c)">
              <el-select v-model="c.operator" size="small" style="width: 80px">
                <el-option v-for="op in def(c).operators" :key="op" :label="operatorLabels[op]" :value="op" />
              </el-select>
            </template>
            <template v-if="showThreshold(c)">
              <span class="param-label">{{ def(c).thresholdLabel }}</span>
              <el-input v-model="c.threshold" size="small" style="width: 80px" />
            </template>
            <span class="expr">{{ exprPreview(c) }}</span>
            <el-button size="small" type="danger" circle @click="removeSell(i)">−</el-button>
          </div>
        </el-card>

        <!-- Risk -->
        <el-card style="margin-top: 12px">
          <template #header><span>🛡️ 风控参数</span></template>
          <el-form :inline="true" size="small">
            <el-form-item label="仓位 ≤"><el-input-number v-model="riskControl.maxPositionRatio" :min="0.01" :max="1" :step="0.05" /></el-form-item>
            <el-form-item label="持仓 ≤"><el-input-number v-model="riskControl.maxHoldings" :min="1" :max="100" /> 只</el-form-item>
            <el-form-item label="止损"><el-input-number v-model="riskControl.stopLoss" :min="0.01" :max="0.5" :step="0.01" /></el-form-item>
            <el-form-item label="止盈"><el-input-number v-model="riskControl.takeProfit" :min="0.01" :max="1" :step="0.01" /></el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card header="策略信息">
          <el-form label-position="top" size="small">
            <el-form-item label="策略名称" required><el-input v-model="strategyName" placeholder="输入策略名称" /></el-form-item>
            <el-form-item label="描述"><el-input v-model="strategyDesc" type="textarea" :rows="3" placeholder="描述策略逻辑" /></el-form-item>
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
.cond-row { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; padding: 8px 10px; background: #fafafa; border-radius: 6px; flex-wrap: wrap; }
.param-label { font-size: 11px; color: #909399; margin: 0 2px 0 4px; }
.expr { font-size: 12px; color: #409eff; font-family: monospace; margin-left: 8px; min-width: 120px; }
.empty { color: #c0c4cc; text-align: center; padding: 20px; }
</style>
