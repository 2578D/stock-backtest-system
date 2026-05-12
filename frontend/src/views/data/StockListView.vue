<script setup lang="ts">
// Stock list view placeholder
</script>

<template>
  <div class="stock-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>股票列表</span>
          <el-button type="primary">同步数据</el-button>
        </div>
      </template>
      <el-empty description="暂未同步数据，请先配置数据源并执行同步" />
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
