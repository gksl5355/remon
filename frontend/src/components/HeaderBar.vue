<template>
  <header
    class="w-full flex flex-col transition-all duration-300 shadow-lg backdrop-blur-xl"
    :class="isDark
      ? 'bg-header-dark-navy text-gray-200'
      : 'bg-white/90 text-gray-900 border-b border-gray-300'
    "
  >
    <!-- 날짜 + 서버 상태 -->
    <div
      class="flex justify-center items-center gap-4 text-[12px] px-6 py-1.5 whitespace-nowrap transition-all"
      :class="isDark ? 'text-gray-400' : 'text-gray-600'"
    >
      <span>{{ formattedDate }} {{ formattedTime }}</span>

      <div class="flex items-center gap-2">
        <span
          class="w-2 h-2 rounded-full animate-pulse"
          :class="healthStatus ? 'bg-green-400' : 'bg-red-500'"
        ></span>
        <span>{{ healthStatus ? '서버 정상 작동 중' : '서버 연결 오류' }}</span>
      </div>
    </div>

    <!-- 본문 헤더 -->
    <div class="flex justify-between items-center px-10 py-3">
      <!-- 로고 -->
      <h1
        @click="router.push('/main')"
        class="text-2xl font-bold tracking-[0.35em] select-none cursor-pointer transition-all"
        :style="isDark
          ? 'color:#FDFF78; text-shadow:0 0 12px rgba(253,255,120,0.7);'
          : 'color:rgb(173 167 9); text-shadow:none;'
        "
      >
        REMON
      </h1>

      <div class="flex items-center gap-3">
        <!-- 언어 선택 -->
        <select
          v-model="language"
          class="rounded-md text-xs px-3 h-8 outline-none border shadow-sm transition-all
                 bg-input-bg border-input-border text-gray-200 hover:border-primary-accent"
          :class="isDark
            ? ''
            : 'bg-gray-100 border-gray-300 text-gray-800 hover:border-gray-400'
          "
        >
          <option value="ko">한국어</option>
          <option value="en">English</option>
        </select>

        <!-- 다크모드 버튼 -->
        <button
          @click="toggleDarkMode"
          class="w-8 h-8 flex items-center justify-center rounded-md shadow-sm transition-all
                 bg-input-bg border border-input-border text-gray-300 hover:border-primary-accent hover:text-primary-accent"
          :class="isDark
            ? ''
            : 'bg-gray-100 border-gray-300 text-gray-700 hover:border-gray-400 hover:text-gray-900'
          "
        >
          <!-- Dark Mode → Moon -->
          <svg v-if="isDark" xmlns="http://www.w3.org/2000/svg" fill="none"
            viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M21 12.79A9 9 0 1111.21 3a7 7 0 0010.08 9.79z" />
          </svg>

          <!-- Light Mode → Sun -->
          <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none"
            viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M12 4.75V3m0 18v-1.75m9-9H19.25M4.75 12H3m15.364-6.364L16.95 6.05M7.05 16.95l-1.414 1.414m12.728 0L16.95 16.95M7.05 7.05L5.636 5.636" />
          </svg>
        </button>

        <!-- 관리자 페이지 -->
        <button
          v-if="role === 'admin' && route.path !== '/admin'"
          @click="goAdminPage"
          class="admin-btn"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="1.6"
          >
            <path stroke-linecap="round" stroke-linejoin="round"
                  d="M12 6.75l7.5 3v3.5c0 4.28-3.44 7.94-7.5 8-4.06-.06-7.5-3.72-7.5-8v-3.5l7.5-3z"/>
            <path stroke-linecap="round" stroke-linejoin="round"
                  d="M9.75 12.75l1.5 1.5 3-3" />
          </svg>
          <span>관리자 페이지</span>
        </button>

        <!-- 로그아웃 -->
        <button
          @click="logout"
          class="px-3 py-1.5 text-xs rounded-md 
                bg-white/5 border border-white/50 
                text-gray-300 shadow-sm 
                hover:border-red-400 hover:text-red-400 
                transition-all backdrop-blur-md"
          :class="isDark
            ? ''
            : 'bg-gray-100 border-gray-300 text-gray-800 hover:border-gray-500'
          "
        >
          로그아웃
        </button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { inject, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();
const isDark = inject("isDark");
const toggleDarkMode = inject("toggleDarkMode");

defineProps({ isLoggedIn: Boolean });

const role = ref(null);
const formattedDate = ref("");
const formattedTime = ref("");
const healthStatus = ref(false);
const language = ref("ko");

// 로그인 역할 로드
onMounted(() => {
  role.value = localStorage.getItem("user_role");
});

// 관리자 페이지 이동
const goAdminPage = () => {
  router.push("/admin");
};

// 로그아웃 기능
const logout = () => {
  localStorage.removeItem("access_token");
  localStorage.removeItem("user_role");
  router.push("/");
};

// 날짜/시간
const updateDateTime = () => {
  const now = new Date();
  formattedDate.value = `${now.getFullYear()}년 ${String(now.getMonth() + 1).padStart(2, '0')}월 ${String(now.getDate()).padStart(2, '0')}일`;

  formattedTime.value = now.toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: 'h23'
  });
};

let timer = null;
onMounted(() => {
  updateDateTime();
  timer = setInterval(updateDateTime, 1000);
});
onUnmounted(() => clearInterval(timer));

// 서버 상태 체크
const checkHealth = async () => {
  try {
    healthStatus.value = true;
  } catch {
    healthStatus.value = false;
  }
};

let healthTimer = null;
onMounted(() => {
  checkHealth();
  healthTimer = setInterval(checkHealth, 10000);
});
onUnmounted(() => clearInterval(healthTimer));
</script>

<style>
  .bg-header-dark-navy { background-color: rgba(4, 14, 27, 0.95); } 
  .border-primary-border { border-color: rgba(136, 192, 208, 0.2); }
  .bg-input-bg { background-color: rgba(255, 255, 255, 0.05); } 
  .border-input-border { border-color: rgba(255, 255, 255, 0.1); } 
  .hover\:border-primary-accent:hover { border-color: #88C0D0; } 
  .hover\:text-primary-accent:hover { color: #88C0D0; }

  /* 공통 스타일 */
  .admin-btn {
    display: flex;
    align-items: center;
    gap: 6px;

    padding: 6px 12px;
    font-size: 12px;
    border-radius: 8px;

    transition: all 0.25s ease;
    backdrop-filter: blur(10px);
  }

  /* 🌙 다크모드 */
  .dark .admin-btn {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid #fdff7866;
    color: #feffbcb8;

    box-shadow:
      0 0 4px rgba(180, 183, 28, 0.412),
      0 0 8px rgba(253, 255, 120, 0.08) inset;
  }

  .dark .admin-btn:hover {
    border-color: #fdff7863;
    color: #FDFF78;

    box-shadow:
      0 0 14px rgba(253, 255, 120, 0.4),
      0 0 8px rgba(253, 255, 120, 0.3) inset,
      0 0 20px rgba(253, 255, 120, 0.2);
  }

  /* ☀ 라이트모드 */
  html:not(.dark) .admin-btn {
    background: rgba(255, 255, 255, 0.9);
    border: 1px solid rgba(190, 170, 40, 0.45);
    color: #6f5e0d;

    box-shadow:
      0 1px 2px rgba(140, 120, 20, 0.14),
      0 0 4px rgba(200, 178, 58, 0.12) inset;
  }

  html:not(.dark) .admin-btn:hover {
    border-color: rgba(198, 176, 45, 0.9);
    color: #b89e2b;

    box-shadow:
      0 0 10px rgba(200, 178, 58, 0.28),
      0 0 6px rgba(200, 178, 58, 0.22) inset;
  }

</style>
