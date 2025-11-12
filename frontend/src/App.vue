<template>
  <div class="min-h-screen bg-[#0d0d0d] text-gray-200">
    <!-- 헤더 -->
    <HeaderBar
      :is-logged-in="isLoggedIn"
      @open-login="showLogin = true"
      @logout="handleLogout"
    />

    <!-- 로그인 모달 -->
    <LoginModal
      v-if="showLogin"
      @close="showLogin = false"
      @success="handleLoginSuccess"
    />

    <!-- 페이지 라우팅 -->
    <router-view />
  </div>
</template>

<script setup>
import HeaderBar from "@/components/HeaderBar.vue";
import LoginModal from "@/components/LoginModal.vue";
import { ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const showLogin = ref(false);
const isLoggedIn = ref(false);

// ✅ 로그인 성공 시 → 상태 true + 관리자 페이지로 이동
const handleLoginSuccess = () => {
  isLoggedIn.value = true;
  showLogin.value = false;
  router.push("/admin");
};

// ✅ 로그아웃 시 → 상태 false + 메인페이지로 이동
const handleLogout = () => {
  localStorage.removeItem("access_token");
  console.log('로그아웃 성공')
  isLoggedIn.value = false;
  router.push("/");
};
</script>
