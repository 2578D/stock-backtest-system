<script setup lang="ts">
// Stock picker view placeholder
import { ref } from "vue";

const pickMode = ref("strategy");
const excludeST = ref(true);
const excludeSuspend = ref(true);
</script>

<template>
  <div class="stock-picker">
    <h2>策略选股器</h2>

    <el-card>
      <el-radio-group v-model="pickMode" style="margin-bottom: 16px">
        <el-radio-button value="strategy">按策略选股</el-radio-button>
        <el-radio-button value="indicator">按指标组合选股</el-radio-button>
        <el-radio-button value="hybrid">混合模式</el-radio-button>
      </el-radio-group>

      <el-row :gutter="16">
        <el-col :span="8">
          <el-card shadow="never" header="筛选条件">
            <el-form label-position="top" size="small">
              <el-form-item label="选股范围">
                <el-radio-group>
                  <el-radio value="all">全市场</el-radio>
                  <el-radio value="main">沪深主板</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item label="风险过滤">
                <el-checkbox v-model="excludeST">排除 ST</el-checkbox>
                <el-checkbox v-model="excludeSuspend">排除停牌</el-checkbox>
              </el-form-item>
            </el-form>
            <el-button type="primary" style="width: 100%">
              开始选股
            </el-button>
          </el-card>
        </el-col>
        <el-col :span="16">
          <el-card shadow="never" header="选股结果">
            <el-empty description="点击「开始选股」扫描全市场" />
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<style scoped>
.stock-picker h2 {
  margin-bottom: 16px;
}
</style>
