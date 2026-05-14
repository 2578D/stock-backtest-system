<script setup lang="ts">
import { ref, onUnmounted, computed } from "vue";
import { ElMessage } from "element-plus";
import { dataApi } from "@/api";

const syncStatus = ref("idle");
const syncProgress = ref("");
const syncMode = ref<"full" | "incremental">("full");
const syncing = ref(false);
const pollingTimer = ref<ReturnType<typeof setInterval> | null>(null);

const stats = ref({
  total_stocks: 0,
  active_stocks: 0,
  latest_data_date: "",
});

// Data freshness: green=今日, yellow=昨日, red=更旧
const freshnessTag = computed(() => {
  if (!stats.value.latest_data_date) return { type: "danger" as const, text: "无数据" };
  const today = new Date().toISOString().slice(0, 10);
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  if (stats.value.latest_data_date >= today) return { type: "success" as const, text: "今日已更新" };
  if (stats.value.latest_data_date >= yesterday) return { type: "warning" as const, text: "昨日数据" };
  return { type: "danger" as const, text: `最新: ${stats.value.latest_data_date}` };
});

async function fetchStats() {
  try {
    const res = await dataApi.getSyncStats();
    if (res.data?.code === 0) {
      stats.value = res.data.data;
    }
  } catch {}
}

async function doSync(mode: "full" | "incremental") {
  syncing.value = true;
  syncMode.value = mode;
  syncProgress.value = "";
  try {
    const fn = mode === "full" ? dataApi.triggerFullSync : dataApi.triggerIncrementalSync;
    await fn();
    syncStatus.value = "running";
    ElMessage.success(mode === "full" ? "全量同步已启动" : "增量同步已启动");
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
      const res = await dataApi.getSyncStatus();
      const data = res.data.data;
      syncProgress.value = data.progress || "";
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
            title="自动增量同步"
            description="每天收盘后（15:30）自动拉取最新行情数据。每整点检查一次，周末/收盘前自动跳过。"
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

          <div style="margin-top: 12px; display: flex; align-items: center; gap: 8px">
            <span style="font-size: 13px; color: #606266">数据新鲜度：</span>
            <el-tag :type="freshnessTag.type" size="large">{{ freshnessTag.text }}</el-tag>
          </div>
          <div v-if="stats.latest_data_date" style="margin-top: 8px">
            <el-tag type="success">最新数据: {{ stats.latest_data_date }}</el-tag>
          </div>
          <el-empty v-else description="暂无数据" :image-size="80" />
        </el-card>

        <el-card header="同步操作" style="margin-top: 12px">
          <el-button
            type="primary"
            :loading="syncing && syncMode === 'full'"
            @click="doSync('full')"
            style="width: 100%"
            :disabled="syncing"
          >
            {{ syncing && syncMode === 'full' ? "同步中..." : "全量同步" }}
          </el-button>
          <el-button
            style="width: 100%; margin-top: 8px"
            :loading="syncing && syncMode === 'incremental'"
            @click="doSync('incremental')"
            :disabled="syncing"
          >
            {{ syncing && syncMode === 'incremental' ? "同步中..." : "增量同步（最近几天）" }}
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
