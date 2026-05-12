<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useUserStore } from "@/stores/user";
import { ElMessage } from "element-plus";

const router = useRouter();
const userStore = useUserStore();

const isRegister = ref(false);
const form = ref({
  email: "",
  username: "",
  password: "",
  confirmPassword: "",
});
const loading = ref(false);

async function handleSubmit() {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning("请填写完整信息");
    return;
  }
  if (isRegister.value) {
    if (!form.value.email) {
      ElMessage.warning("请输入邮箱");
      return;
    }
    if (form.value.password !== form.value.confirmPassword) {
      ElMessage.warning("两次密码不一致");
      return;
    }
  }

  loading.value = true;
  try {
    if (isRegister.value) {
      await userStore.register(form.value.email, form.value.username, form.value.password);
    } else {
      await userStore.login(form.value.username, form.value.password);
    }
    ElMessage.success(isRegister.value ? "注册成功" : "登录成功");
    router.push("/dashboard");
  } catch (e: any) {
    // Error handled by interceptor
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-container">
    <el-card class="login-card">
      <h2>{{ isRegister ? "注册" : "登录" }}</h2>
      <el-form @submit.prevent="handleSubmit" label-position="top">
        <el-form-item v-if="isRegister" label="邮箱">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>
        <el-form-item v-if="isRegister" label="确认密码">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="请再次输入密码"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            native-type="submit"
            :loading="loading"
            style="width: 100%"
          >
            {{ isRegister ? "注册" : "登录" }}
          </el-button>
        </el-form-item>
      </el-form>
      <div class="toggle-link">
        <el-button type="primary" link @click="isRegister = !isRegister">
          {{ isRegister ? "已有账号？去登录" : "没有账号？去注册" }}
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
}

.login-card {
  width: 400px;
}

.login-card h2 {
  text-align: center;
  margin-bottom: 24px;
}

.toggle-link {
  text-align: center;
  margin-top: 12px;
}
</style>
