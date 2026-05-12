<script setup lang="ts">
// Strategy list placeholder
import { useRouter } from "vue-router";

const router = useRouter();

function goCreateVisual() {
  router.push("/strategies/create/visual");
}
function goCreateCode() {
  router.push("/strategies/create/code");
}
</script>

<template>
  <div class="strategy-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>策略中心</span>
          <div class="actions">
            <el-button type="primary" @click="goCreateVisual">
              可视化创建
            </el-button>
            <el-button type="success" @click="goCreateCode">
              代码创建
            </el-button>
          </div>
        </div>
      </template>
      <el-empty description="暂无策略，点击上方按钮创建" />
    </el-card>
  </div>
</template>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.actions {
  display: flex;
  gap: 8px;
}
</style>
