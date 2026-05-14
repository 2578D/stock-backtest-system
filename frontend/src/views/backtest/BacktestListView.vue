<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { backtestApi } from "@/api";
import { ElMessage } from "element-plus";

const router = useRouter();
const backtests = ref<any[]>([]);
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    const res = await backtestApi.list({});
    backtests.value = res.data.data || [];
  } catch {
    ElMessage.error("加载回测列表失败");
  } finally {
    loading.value = false;
  }
}

function statusTag(s: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = { pending: "info", running: "warning", completed: "success", failed: "danger" };
  return map[s] || "info";
}
function statusLabel(s: string) {
  const map: Record<string, string> = { pending: "等待中", running: "运行中", completed: "已完成", failed: "失败" };
  return map[s] || s;
}

onMounted(load);
</script>

<template>
  <div class="backtest-list">
    <div class="header">
      <h2>回测中心</h2>
      <div class="header-btns">
        <el-button @click="router.push('/backtests/compare')">回测对比</el-button>
        <el-button type="primary" @click="router.push('/backtests/create')">新建回测</el-button>
      </div>
    </div>

    <el-table :data="backtests" v-loading="loading" stripe style="margin-top: 16px">
      <el-table-column prop="name" label="名称" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <el-button v-if="row.status === 'completed'" type="primary" link @click="router.push(`/backtests/${row.id}`)">
            {{ row.name }}
          </el-button>
          <span v-else>{{ row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="progress" label="进度" width="100">
        <template #default="{ row }">
          <el-progress v-if="row.status === 'running'" :percentage="row.progress || 0" :stroke-width="6" />
          <span v-else-if="row.status === 'completed'">100%</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="initial_capital" label="初始资金" width="120">
        <template #default="{ row }">¥{{ row.initial_capital?.toLocaleString() }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <div class="action-btns">
            <el-button v-if="row.status === 'completed'" size="small" type="primary" @click="router.push(`/backtests/${row.id}`)">
              查看
            </el-button>
            <el-button v-else size="small" disabled>
              {{ row.status === "running" ? "运行中" : "等待" }}
            </el-button>
          </div>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无回测任务，创建第一个吧" />
      </template>
    </el-table>
  </div>
</template>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header h2 {
  margin: 0;
}
.header-btns {
  display: flex;
  gap: 8px;
}
.action-btns {
  display: inline-flex;
  gap: 6px;
  flex-wrap: nowrap;
  white-space: nowrap;
}
</style>
