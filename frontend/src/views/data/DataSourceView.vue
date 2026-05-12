<script setup lang="ts">
import { ref } from "vue";
import { ElMessage } from "element-plus";
import http from "@/api/http";

const cookie = ref("");
const syncStatus = ref("idle");
const syncProgress = ref("");
const syncTaskId = ref("");
const syncing = ref(false);
const pollingTimer = ref<ReturnType<typeof setInterval> | null>(null);

const stats = ref({
  total_stocks: 0,
  active_stocks: 0,
  latest_data_date: "",
});

async function fetchStats() {
  try {
    const res = await http.get("/data/sync/stats");
    stats.value = res.data.data;
  } catch {}
}

async function startFullSync() {
  syncing.value = true;
  try {
    const res = await http.post("/data/sync/full", {
      cookie: cookie.value ? `ct=${cookie.value}` : "",
    });
    syncTaskId.value = res.data.data.task_id;
    syncStatus.value = "running";
    ElMessage.success("全量同步已启动");
    startPolling();
  } catch {
    ElMessage.error("启动同步失败");
    syncing.value = false;
  }
}

function startPolling() {
  if (pollingTimer.value) clearInterval(pollingTimer.value);
  pollingTimer.value = setInterval(async () => {
    try {
      const res = await http.get("/data/sync/status");
      const data = res.data.data;
      syncProgress.value = data.progress || "";
      if (data.status === "idle" || data.progress?.startsWith("complete")) {
        syncStatus.value = "done";
        syncing.value = false;
        if (pollingTimer.value) clearInterval(pollingTimer.value);
        ElMessage.success("全量同步完成");
        fetchStats();
      }
    } catch {}
  }, 3000);
}

fetchStats();
</script>

<template>
  <div class="data-sources">
    <h2>数据源配置</h2>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card header="efinance (东方财富)">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="类型">API 采集适配器</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag type="success">已配置</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="数据覆盖">
              日线行情、股票基础信息
            </el-descriptions-item>
            <el-descriptions-item label="限流">
              需 ct Cookie 验证
            </el-descriptions-item>
          </el-descriptions>

          <el-alert
            type="warning"
            :closable="false"
            style="margin-top: 12px"
            title="Cookie 获取方式"
            description="1. 登录东方财富官网 → 2. 打开开发者工具 → 3. Application → Cookies → 找到 ct 的值 → 复制到下方"
          />

          <el-form style="margin-top: 12px">
            <el-form-item label="ct Cookie">
              <el-input
                v-model="cookie"
                placeholder="粘贴 ct= 后面的 cookie 值（不含 ct= 前缀）"
                type="textarea"
                :rows="2"
              />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card header="同步状态">
          <el-statistic
            v-if="stats.total_stocks > 0"
            title="已入库股票"
            :value="stats.total_stocks"
          />
          <el-empty v-else description="暂无数据" :image-size="80" />

          <div v-if="stats.latest_data_date" style="margin-top: 8px">
            <el-tag type="info">最新数据: {{ stats.latest_data_date }}</el-tag>
          </div>
        </el-card>

        <el-card header="同步操作" style="margin-top: 12px">
          <el-button
            type="primary"
            :loading="syncing"
            @click="startFullSync"
            style="width: 100%"
          >
            {{ syncing ? "同步中..." : "全量同步" }}
          </el-button>

          <div v-if="syncProgress" style="margin-top: 12px">
            <el-progress
              v-if="syncProgress.includes(':')"
              :percentage="Number(syncProgress.split(':')[1]) || 0"
              :status="syncStatus === 'done' ? 'success' : undefined"
            />
            <el-text type="info" size="small">{{ syncProgress }}</el-text>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.data-sources h2 {
  margin-bottom: 16px;
}
</style>
