<script setup lang="ts">
import { ref, onUnmounted } from "vue";
import { ElMessage } from "element-plus";
import { dataApi } from "@/api";
import http from "@/api/http";

const syncStatus = ref("idle");
const syncProgress = ref("");
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
    if (res.data?.code === 0) {
      stats.value = res.data.data;
    }
  } catch {}
}

async function startFullSync() {
  syncing.value = true;
  syncProgress.value = "";
  try {
    const res = await http.post("/data/sync/full", { cookie: "" });
    syncStatus.value = "running";
    ElMessage.success("全量同步已启动（TickFlow 批量拉取）");
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
      // Format: "95.0% Generating trade calendar..."
      const m = data.progress?.match(/^(\d+\.?\d*)%/);
      const pct = m ? parseFloat(m[1]) : 0;
      if (data.status === "idle" || data.progress === "" || pct >= 100) {
        syncStatus.value = "done";
        syncing.value = false;
        if (pollingTimer.value) clearInterval(pollingTimer.value);
        ElMessage.success("同步完成");
        fetchStats();
      }
    } catch {}
  }, 3000);
}

onUnmounted(() => {
  if (pollingTimer.value) clearInterval(pollingTimer.value);
});

fetchStats();
</script>

<template>
  <div class="data-sources">
    <h2>数据管理</h2>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card header="TickFlow 数据源">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="类型">批量 K 线 API</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag type="success">已配置</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="数据覆盖">
              全A股日线行情（5400+ 只）
            </el-descriptions-item>
            <el-descriptions-item label="方式">
              批量拉取，无需 Cookie
            </el-descriptions-item>
          </el-descriptions>

          <el-alert
            type="info"
            :closable="false"
            style="margin-top: 12px"
            title="数据同步说明"
            description="首次全量同步约需 2-5 分钟（取决于网络），后续增量同步仅拉取缺失数据。同步期间回测服务不受影响。"
          />
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card header="数据概览">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-statistic title="已入库股票" :value="stats.total_stocks || 0" />
            </el-col>
            <el-col :span="12">
              <el-statistic title="正常交易" :value="stats.active_stocks || 0" />
            </el-col>
          </el-row>

          <div v-if="stats.latest_data_date" style="margin-top: 12px">
            <el-tag type="success">最新数据: {{ stats.latest_data_date }}</el-tag>
          </div>
          <el-empty v-else description="暂无数据" :image-size="80" />
        </el-card>

        <el-card header="同步操作" style="margin-top: 12px">
          <el-button
            type="primary"
            :loading="syncing"
            @click="startFullSync"
            style="width: 100%"
            :disabled="syncing"
          >
            {{ syncing ? "同步中..." : "全量同步" }}
          </el-button>

          <div v-if="syncProgress" style="margin-top: 12px">
            <el-progress
              :percentage="parseFloat(syncProgress) || 0"
              :status="syncStatus === 'done' ? 'success' : undefined"
              :stroke-width="8"
            />
            <el-text type="info" size="small" style="margin-top: 4px; display: block">{{ syncProgress }}</el-text>
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
