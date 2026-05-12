<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { strategyApi } from "@/api";
import { ElMessage } from "element-plus";

const router = useRouter();

const strategyName = ref("");
const description = ref("");
const saving = ref(false);

const MA_TEMPLATE = `# 双均线金叉策略
class MACrossStrategy(IStrategy):
    def __init__(self):
        self.fast = 5
        self.slow = 20

    def on_bar(self, context, bar, portfolio):
        orders = []
        sym = list(context._provider._stock_pool)[0] if context._provider._stock_pool else None
        if sym is None:
            return orders
        df = context.data(sym, lookback=self.slow + 1)
        if len(df) < self.slow:
            return orders
        fast_ma = df['close'].tail(self.fast).mean()
        slow_ma = df['close'].tail(self.slow).mean()
        prev_fast = df['close'].iloc[-self.fast-1:-1].mean() if len(df) > self.fast else fast_ma
        prev_slow = df['close'].iloc[-self.slow-1:-1].mean() if len(df) > self.slow else slow_ma

        if prev_fast <= prev_slow and fast_ma > slow_ma:
            qty = int(portfolio.cash * 0.2 / bar['close'] / 100) * 100
            if qty >= 100:
                orders.append(Order(sym, 'buy', qty, reason='MA金叉'))
        elif prev_fast >= prev_slow and fast_ma < slow_ma:
            pos = portfolio.positions.get(sym)
            if pos and pos.quantity > 0:
                orders.append(Order(sym, 'sell', pos.quantity, reason='MA死叉'))
        return orders`;

const codeContent = ref(MA_TEMPLATE);

const templates: Record<string, { name: string; code: string }> = {
  ma: { name: "均线金叉", code: MA_TEMPLATE },
  buyhold: { name: "买入持有", code: `class BuyHoldStrategy(IStrategy):
    def __init__(self):
        self.bought = False
    def on_bar(self, context, bar, portfolio):
        if self.bought:
            return []
        sym = list(context._provider._stock_pool)[0]
        qty = int(portfolio.cash * 0.95 / bar['close'] / 100) * 100
        self.bought = True
        return [Order(sym, 'buy', qty, reason='初始建仓')]` },
  rsi: { name: "RSI 超卖", code: `class RSIStrategy(IStrategy):
    def __init__(self):
        self.period = 14
        self.oversold = 30
        self.overbought = 70
    def on_bar(self, context, bar, portfolio):
        orders = []
        sym = list(context._provider._stock_pool)[0] if context._provider._stock_pool else None
        if sym is None: return orders
        df = context.data(sym, lookback=self.period + 1)
        if len(df) < self.period + 1: return orders
        closes = df['close'].values
        gains = [max(closes[i] - closes[i-1], 0) for i in range(1, len(closes))]
        losses = [max(closes[i-1] - closes[i], 0) for i in range(1, len(closes))]
        avg_gain = sum(gains[-self.period:]) / self.period
        avg_loss = sum(losses[-self.period:]) / self.period
        rsi = 100 - 100/(1 + avg_gain/avg_loss) if avg_loss > 0 else 100
        pos = portfolio.positions.get(sym)
        if rsi < self.oversold and (not pos or pos.quantity == 0):
            qty = int(portfolio.cash * 0.3 / bar['close'] / 100) * 100
            if qty >= 100:
                orders.append(Order(sym, 'buy', qty, reason=f'RSI超卖({rsi:.0f})'))
        elif rsi > self.overbought and pos and pos.quantity > 0:
            orders.append(Order(sym, 'sell', pos.quantity, reason=f'RSI超买({rsi:.0f})'))
        return orders` },
};

function loadTemplate(key: string) {
  const t = templates[key];
  if (t) {
    codeContent.value = t.code;
    ElMessage.info(`已加载模板: ${t.name}`);
  }
}

async function save() {
  if (!strategyName.value.trim()) {
    ElMessage.warning("请输入策略名称");
    return;
  }
  saving.value = true;
  try {
    const res = await strategyApi.create({
      name: strategyName.value.trim(),
      description: description.value.trim(),
      type: "code",
      code_content: codeContent.value,
    });
    ElMessage.success("策略已保存");
    router.push(`/strategies/${res.data.id}`);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
}

async function saveAndBacktest() {
  if (!strategyName.value.trim()) {
    ElMessage.warning("请输入策略名称");
    return;
  }
  saving.value = true;
  try {
    const res = await strategyApi.create({
      name: strategyName.value.trim(),
      description: description.value.trim(),
      type: "code",
      code_content: codeContent.value,
    });
    ElMessage.success("策略已保存");
    router.push({ path: "/backtests/create", query: { strategyId: res.data.id } });
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="code-editor">
    <h2>代码策略编辑器</h2>

    <el-row :gutter="16">
      <el-col :span="18">
        <el-card header="代码编辑区">
          <el-input
            v-model="codeContent"
            type="textarea"
            :rows="20"
            placeholder="编写 Python 策略代码"
            style="font-family: 'Fira Code', monospace; font-size: 13px"
          />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card header="策略信息">
          <el-form label-position="top">
            <el-form-item label="策略名称" required>
              <el-input v-model="strategyName" placeholder="输入策略名称" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="description" type="textarea" :rows="2" placeholder="策略描述（可选）" />
            </el-form-item>
          </el-form>
        </el-card>
        <el-card header="模板" style="margin-top: 12px">
          <div style="display: flex; flex-direction: column; gap: 8px">
            <el-button v-for="(t, k) in templates" :key="k" size="small" @click="loadTemplate(k)">
              {{ t.name }}
            </el-button>
          </div>
        </el-card>
        <el-card header="操作" style="margin-top: 12px">
          <div style="display: flex; flex-direction: column; gap: 8px">
            <el-button type="primary" @click="save" :loading="saving">保存策略</el-button>
            <el-button type="success" @click="saveAndBacktest" :loading="saving">保存并回测</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.subtitle {
  color: #909399;
  margin-bottom: 20px;
}
</style>
