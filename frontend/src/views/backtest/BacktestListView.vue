<script setup lang="ts">
import { useRouter } from "vue-router";

const router = useRouter();
</script>

<template>
  <div class="backtest-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>回测任务</span>
          <el-button type="primary" @click="router.push('/backtests/create')">
            新建回测
          </el-button>
        </div>
      </template>
      <el-empty description="暂无回测任务" />
    </el-card>
  </div>
</template>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
