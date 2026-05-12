<script setup lang="ts">
import { ref, onMounted } from "vue";
import { dataApi } from "@/api";
import { ElMessage } from "element-plus";

const stocks = ref<any[]>([]);
const loading = ref(false);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const keyword = ref("");
const exchange = ref("");

async function load() {
  loading.value = true;
  try {
    const res = await dataApi.listStocks({ page: page.value, page_size: pageSize.value, keyword: keyword.value, exchange: exchange.value });
    stocks.value = res.data.data || [];
    total.value = res.data.pagination?.total || 0;
  } catch {
    ElMessage.error("加载股票列表失败");
  } finally {
    loading.value = false;
  }
}

function search() {
  page.value = 1;
  load();
}

onMounted(load);
</script>

<template>
  <div class="stock-list">
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索代码/名称" clearable style="width: 240px" @keyup.enter="search" />
      <el-select v-model="exchange" placeholder="交易所" clearable style="width: 120px; margin-left: 8px" @change="search">
        <el-option label="全部" value="" />
        <el-option label="沪市" value="SH" />
        <el-option label="深市" value="SZ" />
        <el-option label="北交所" value="BJ" />
      </el-select>
      <el-button type="primary" @click="search" style="margin-left: 8px">搜索</el-button>
    </div>

    <el-table :data="stocks" v-loading="loading" stripe style="margin-top: 12px">
      <el-table-column prop="code" label="代码" width="120" />
      <el-table-column prop="name" label="名称" width="150" />
      <el-table-column prop="exchange" label="交易所" width="80" />
      <el-table-column prop="sector" label="板块" width="100" />
      <el-table-column prop="industry" label="行业" min-width="150" />
      <el-table-column prop="list_date" label="上市日" width="110" />
      <el-table-column label="ST" width="60">
        <template #default="{ row }">
          <el-tag v-if="row.is_st" type="danger" size="small">ST</el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > pageSize"
      style="margin-top: 16px; justify-content: center"
      v-model:current-page="page"
      :page-size="pageSize"
      :total="total"
      layout="total, prev, pager, next"
      @current-change="load"
    />
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
}
</style>
