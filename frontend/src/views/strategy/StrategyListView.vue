<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { strategyApi } from "@/api";
import { ElMessage, ElMessageBox } from "element-plus";

const router = useRouter();
const strategies = ref<any[]>([]);
const loading = ref(false);

async function loadStrategies() {
  loading.value = true;
  try {
    const res = await strategyApi.list();
    strategies.value = res.data.data || [];
  } catch (e) {
    ElMessage.error("加载策略失败");
  } finally {
    loading.value = false;
  }
}

function goCreateVisual() {
  router.push("/strategies/create/visual");
}
function goCreateCode() {
  router.push("/strategies/create/code");
}
function goEdit(id: string) {
  router.push(`/strategies/${id}`);
}
function goBacktest(id: string) {
  router.push({ path: "/backtests/create", query: { strategyId: id } });
}

async function handleDelete(id: string, name: string) {
  try {
    await ElMessageBox.confirm(`删除策略「${name}」？`, "确认删除", { type: "warning" });
    await strategyApi.delete(id);
    ElMessage.success("已删除");
    loadStrategies();
  } catch { /* cancelled */ }
}

function typeLabel(t: string) {
  return t === "visual" ? "可视化" : "代码";
}
function typeTag(t: string) {
  return t === "visual" ? "success" : "warning";
}

onMounted(loadStrategies);
</script>

<template>
  <div class="strategy-list">
    <div class="header">
      <h2>策略中心</h2>
      <div class="actions">
        <el-button type="primary" @click="goCreateVisual">可视化创建</el-button>
        <el-button type="success" @click="goCreateCode">代码创建</el-button>
      </div>
    </div>

    <el-table :data="strategies" v-loading="loading" style="margin-top: 16px" stripe>
      <el-table-column prop="name" label="策略名称" min-width="180">
        <template #default="{ row }">
          <el-button type="primary" link @click="goEdit(row.id)">{{ row.name }}</el-button>
        </template>
      </el-table-column>
      <el-table-column prop="type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="typeTag(row.type)" size="small">{{ typeLabel(row.type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="market" label="市场" width="80" />
      <el-table-column prop="period" label="周期" width="80" />
      <el-table-column prop="version" label="版本" width="70" align="center" />
      <el-table-column prop="updated_at" label="更新" width="180">
        <template #default="{ row }">{{ row.updated_at?.slice(0, 10) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="{ row }">
          <div class="action-btns">
            <el-button size="small" @click="goEdit(row.id)">编辑</el-button>
            <el-button size="small" type="primary" @click="goBacktest(row.id)">回测</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row.id, row.name)">删除</el-button>
          </div>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无策略，点击上方按钮创建" />
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
.actions {
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
