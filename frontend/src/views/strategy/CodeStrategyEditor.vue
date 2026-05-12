<script setup lang="ts">
// Code strategy editor placeholder
import { ref } from "vue";

const strategyName = ref("");
const codeContent = ref(`class MyStrategy:
    """自定义策略"""

    def on_init(self, context):
        pass

    def on_bar(self, bar, context):
        # 在这里编写你的策略逻辑
        pass

    def on_order(self, order, context):
        pass

    def on_stop(self, context):
        pass
`);
</script>

<template>
  <div class="code-editor">
    <h2>代码策略编辑器</h2>
    <p class="subtitle">Python 策略代码编写 — 当前为占位版本，正式版将集成 CodeMirror 6</p>

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
            <el-form-item label="策略名称">
              <el-input v-model="strategyName" placeholder="输入策略名称" />
            </el-form-item>
          </el-form>
        </el-card>
        <el-card header="模板" style="margin-top: 12px">
          <el-button style="width: 100%; margin-bottom: 6px" size="small">
            均线策略模板
          </el-button>
          <el-button style="width: 100%; margin-bottom: 6px" size="small">
            MACD 策略模板
          </el-button>
          <el-button style="width: 100%; margin-bottom: 6px" size="small">
            RSI 策略模板
          </el-button>
        </el-card>
        <el-card header="操作" style="margin-top: 12px">
          <el-button style="width: 100%; margin-bottom: 8px">
            语法检查
          </el-button>
          <el-button type="primary" style="width: 100%; margin-bottom: 8px">
            保存策略
          </el-button>
          <el-button type="success" style="width: 100%">
            立即回测
          </el-button>
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
