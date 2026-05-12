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

/* Consistent table row height and vertical centering */
.el-table td.el-table__cell {
  vertical-align: middle;
}
.el-table .cell {
  line-height: 1.4;
}
</style>
