<template>
  <header
    class="w-full bg-black/90 backdrop-blur-md border-b border-[#2b2b2b]/70 shadow-sm"
  >
    <!-- 🔹 상단 바 -->
    <div
      class="flex justify-center items-center gap-4 text-[12px] text-gray-400 px-8 py-1 border-b border-[#2b2b2b]/60"
    >
      <span>{{ formattedDate }} · {{ formattedTime }}</span>

      <!-- 🟢 실제 헬스체크 상태 -->
      <div class="flex items-center gap-2">
        <span
          class="w-2 h-2 rounded-full"
          :class="healthStatus ? 'bg-green-500 animate-pulse' : 'bg-red-500'"
        ></span>
        <span>
          {{ healthStatus ? "서버 정상 작동 중" : "서버 연결 오류" }}
        </span>
      </div>
    </div>

    <!-- 🔹 하단 바 -->
    <div class="flex justify-between items-center px-8 py-3">
      <!-- 좌측 로고 -->
      <div class="flex items-center gap-4">
        <h1
          class="text-2xl font-semibold tracking-[0.35em] text-[#D4AF37] select-none"
        >
          REMON
        </h1>
        <span
          v-if="isAdminPage"
          class="text-[#D4AF37] text-sm tracking-widest font-medium opacity-80"
        >
          ADMIN DASHBOARD
        </span>
      </div>

      <!-- 우측 컨트롤 -->
      <div class="flex items-center gap-2">
        <!-- 언어 -->
        <select
          v-model="language"
          class="flex items-center bg-[#111] border border-[#2b2b2b]/70 rounded-md text-xs text-gray-300 px-3 h-8 hover:border-[#D4AF37]/70 focus:outline-none focus:ring-1 focus:ring-[#D4AF37] transition"
        >
          <option value="ko" class="bg-[#1b1b1b] text-gray-200">한국어</option>
          <option value="en" class="bg-[#1b1b1b] text-gray-200">English</option>
        </select>

        <!-- 다크모드 -->
        <button
          @click="toggleDarkMode"
          class="flex items-center justify-center w-8 h-8 bg-[#111] border border-[#2b2b2b]/70 rounded-md text-[#D4AF37] hover:border-[#D4AF37]/70 hover:bg-[#1a1a1a] transition"
          title="테마 전환"
        >
          <svg
            v-if="isDark"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke-width="1.6"
            stroke="currentColor"
            class="w-4 h-4"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 3v1m0 16v1m9-9h1M3 12H2m15.364-7.364l.707.707M6.343 17.657l-.707.707m12.728 0l.707-.707M6.343 6.343l-.707-.707M12 5a7 7 0 100 14 7 7 0 000-14z"
            />
          </svg>

          <svg
            v-else
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke-width="1.6"
            stroke="currentColor"
            class="w-4 h-4"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M21 12.79A9 9 0 1111.21 3a7 7 0 0010.08 9.79z"
            />
          </svg>
        </button>

        <!-- 로그인 / 로그아웃 버튼 -->
        <button
          v-if="!isLoggedIn"
          class="border border-[#E8C663]/70 px-4 py-1.5 rounded-full text-xs text-gray-200 hover:bg-[#D4AF37] hover:text-black transition"
          @click="$emit('open-login')"
        >
          로그인
        </button>

        <button
          v-else
          class="border border-[#E8C663]/70 px-4 py-1.5 rounded-full text-xs text-gray-200 hover:bg-[#D4AF37]/90 hover:text-black transition"
          @click="$emit('logout')"
        >
          로그아웃
        </button>
      </div>
    </div>
  </header>
</template>

<script setup>
import api from "@/services/api.js"; // ✅ axios 인스턴스 사용
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute } from "vue-router";

defineProps({
  isLoggedIn: {
    type: Boolean,
    default: false,
  },
});

const route = useRoute();
const isAdminPage = computed(() => route.name === "AdminPage");

// ---------------------------------------
// ✅ 날짜·시간 표시
// ---------------------------------------
const formattedDate = ref("");
const formattedTime = ref("");

const updateDateTime = () => {
  const now = new Date();
  formattedDate.value = now.toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  formattedTime.value = now.toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
  });
};

let timer = null;
onMounted(() => {
  updateDateTime();
  timer = setInterval(updateDateTime, 1000);
});
onUnmounted(() => clearInterval(timer));

// ---------------------------------------
// ✅ 헬스체크 (실제 서버 확인)
// ---------------------------------------
const healthStatus = ref(false);

const checkHealth = async () => {
  try {
    const res = await api.get("/health", { timeout: 2000 }); // 2초 내 응답 없으면 실패
    // FastAPI에서 { "status": "ok" } 형태로 내려온 경우만 정상
    if (res.status === 200 && res.data?.status === "ok") {
      healthStatus.value = true;
    } else {
      healthStatus.value = false;
    }
  } catch (err) {
    console.warn("🚨 서버 헬스체크 실패:", err.message);
    healthStatus.value = false;
  }
};

// 10초마다 헬스체크
let healthTimer = null;
onMounted(() => {
  checkHealth();
  healthTimer = setInterval(checkHealth, 10000);
});
onUnmounted(() => clearInterval(healthTimer));

// ---------------------------------------
// ✅ 언어 & 다크모드
// ---------------------------------------
const language = ref("ko");
const isDark = ref(true);
const toggleDarkMode = () => {
  isDark.value = !isDark.value;
  document.documentElement.classList.toggle("dark", isDark.value);
};
</script>
