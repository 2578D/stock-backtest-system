<script setup lang="ts">
import { useUserStore } from "@/stores/user";

const userStore = useUserStore();
</script>

<template>
  <router-view />
</template>

<style>
html,
body,
#app {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: "Helvetica Neue", Helvetica, "PingFang SC", "Microsoft YaHei",
    sans-serif;
}

/* Global table alignment */
.el-table .cell {
  display: flex;
  align-items: center;
  word-break: keep-all;
  white-space: nowrap;
}
.el-table th .cell {
  white-space: nowrap;
}
/* Allow text columns to wrap if needed */
.el-table .cell-wrap .cell {
  white-space: normal;
  word-break: break-word;
}
</style>
