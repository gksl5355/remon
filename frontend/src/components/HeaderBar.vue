<template>
  <header
    class="w-full flex flex-col transition-all duration-300 shadow-lg border-b border-white/10"
    :class="'bg-[#0F172A]/95 text-gray-200 backdrop-blur-xl'"
  >
    <!-- 상단: 날짜 + 서버 상태 -->
    <div
      class="flex justify-center items-center gap-4 text-[12px] px-6 py-1.5 whitespace-nowrap"
      :class="'text-gray-400'"
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

    <!-- 하단: 로고 + 기능들 -->
    <div class="flex justify-between items-center px-6 py-3">
      <!-- 로고 -->
      <h1
        class="text-2xl font-bold tracking-[0.35em] select-none"
        style="color: #F2CB05;"
      >
        REMON
      </h1>

      <div class="flex items-center gap-3">
        
        <!-- 언어 선택 -->
        <select
          v-model="language"
          class="rounded-md text-xs px-3 h-8 outline-none border shadow-sm transition-all bg-[#1E293B] border-[#334155] text-gray-200"
        >
          <option value="ko">한국어</option>
          <option value="en">English</option>
        </select>

        <!-- 다크모드 토글 -->
        <button
          @click="toggleDarkMode"
          class="w-8 h-8 flex items-center justify-center rounded-md shadow-sm transition-all
                 bg-[#1E293B] border border-[#334155] text-gray-300 hover:bg-[#334155]"
        >
          <svg v-if="isDark" xmlns="http://www.w3.org/2000/svg" fill="none"
            viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M21 12.79A9 9 0 1111.21 3a7 7 0 0010.08 9.79z" />
          </svg>

          <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none"
            viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M12 4.75V3m0 18v-1.75m9-9H19.25M4.75 12H3m15.364-6.364L16.95 6.05M7.05 16.95l-1.414 1.414m12.728 0L16.95 16.95M7.05 7.05L5.636 5.636" />
          </svg>
        </button>

        <!-- 로그인 버튼 -->
        <button
          @click="!isLoggedIn ? $emit('open-login') : $emit('logout')"
          class="px-4 py-1.5 rounded-full text-xs border shadow-sm transition-all
                 bg-yellow-500/90 border-yellow-400 text-black font-semibold hover:bg-yellow-400"
        >
          {{ isLoggedIn ? '로그아웃' : '로그인' }}
        </button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { inject, onMounted, onUnmounted, ref } from "vue";

const isDark = inject("isDark");
const toggleDarkMode = inject("toggleDarkMode");

defineProps({ isLoggedIn: Boolean });

const formattedDate = ref("");
const formattedTime = ref("");

const updateDateTime = () => {
  const now = new Date();
  formattedDate.value = now.toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).replace(/\./g, '').replace(' ', '년 ').replace(' ', '월 ').replace(' ', '일');

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

// health check
const healthStatus = ref(false);
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

const language = ref("ko");
</script>
