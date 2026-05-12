<script setup lang="ts">
// Dashboard — data overview cards
</script>

<template>
  <div class="dashboard">
    <h2>仪表盘</h2>
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="A股总数" :value="0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="日线覆盖天数" :value="0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="策略总数" :value="0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="回测完成任务" :value="0" />
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 20px">
      <h3>最近同步</h3>
      <el-empty description="暂无同步记录" />
    </el-card>
  </div>
</template>

<style scoped>
.dashboard h2 {
  margin-bottom: 20px;
}
</style>
