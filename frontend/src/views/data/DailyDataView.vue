<script setup lang="ts">
import { ref } from "vue";
import { dataApi } from "@/api";
import { ElMessage } from "element-plus";

const code = ref("");
const bars = ref<any[]>([]);
const stockInfo = ref<any>(null);
const loading = ref(false);

async function query() {
  if (!code.value.trim()) {
    ElMessage.warning("请输入股票代码");
    return;
  }
  loading.value = true;
  try {
    const [barRes, infoRes] = await Promise.allSettled([
      dataApi.getDailyBars(code.value, { page_size: 100 }),
      dataApi.getStock(code.value).catch(() => null),
    ]);
    if (barRes.status === "fulfilled") bars.value = barRes.value.data.data || [];
    if (infoRes.status === "fulfilled" && infoRes.value) stockInfo.value = infoRes.value.data.data;
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="daily-data">
    <div class="toolbar">
      <el-input v-model="code" placeholder="股票代码 (如 600519.SH)" style="width: 240px" @keyup.enter="query" />
      <el-button type="primary" style="margin-left: 8px" @click="query">查询</el-button>
      <span v-if="stockInfo" style="margin-left: 16px; color: #606266">
        {{ stockInfo.name }} | {{ stockInfo.exchange }} | {{ stockInfo.industry }}
      </span>
    </div>

    <el-table :data="bars" v-loading="loading" stripe max-height="600" style="margin-top: 12px">
      <el-table-column prop="trade_date" label="日期" width="120" />
      <el-table-column prop="open" label="开盘" width="90">
        <template #default="{ row }">{{ row.open?.toFixed(2) }}</template>
      </el-table-column>
      <el-table-column prop="high" label="最高" width="90">
        <template #default="{ row }">{{ row.high?.toFixed(2) }}</template>
      </el-table-column>
      <el-table-column prop="low" label="最低" width="90">
        <template #default="{ row }">{{ row.low?.toFixed(2) }}</template>
      </el-table-column>
      <el-table-column prop="close" label="收盘" width="90">
        <template #default="{ row }">{{ row.close?.toFixed(2) }}</template>
      </el-table-column>
      <el-table-column prop="volume" label="成交量" width="120">
        <template #default="{ row }">{{ (row.volume / 10000).toFixed(0) }}万</template>
      </el-table-column>
      <el-table-column prop="amount" label="成交额" width="140">
        <template #default="{ row }">{{ (row.amount / 100000000).toFixed(2) }}亿</template>
      </el-table-column>
      <template #empty>
        <el-empty description="输入代码查询行情数据" />
      </template>
    </el-table>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
}
</style>
