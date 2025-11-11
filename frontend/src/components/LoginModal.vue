<template>
  <!-- 배경: 클릭 시 닫기 -->
  <div
    class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
    @click.self="closeModal"
  >
    <!-- 팝업 상자 -->
    <div class="bg-[#1a1a1a] rounded-xl p-6 w-80 shadow-lg border border-[#333]">
      <h2 class="text-lg font-semibold text-[#D4AF37] mb-4 text-center">
        관리자 로그인
      </h2>

      <!-- 아이디 입력 -->
      <input
        v-model="username"
        ref="usernameInput"
        placeholder="아이디"
        class="w-full mb-2 px-3 py-2 bg-[#111] border border-[#333] rounded-md text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-[#D4AF37]"
        @keyup.enter="focusPassword"
      />

      <!-- 비밀번호 입력 -->
      <input
        v-model="password"
        ref="passwordInput"
        type="password"
        placeholder="비밀번호"
        class="w-full mb-4 px-3 py-2 bg-[#111] border border-[#333] rounded-md text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-[#D4AF37]"
        @keyup.enter="login"
      />

      <!-- 버튼 영역 -->
      <div class="flex justify-end gap-2">
        <button
          class="px-3 py-1 text-sm text-gray-300 hover:text-white"
          @click="closeModal"
        >
          취소
        </button>
        <button
          class="px-3 py-1 text-sm bg-[#D4AF37] text-black rounded-md hover:bg-[#e6c556]"
          @click="login"
          :disabled="loading"
        >
          {{ loading ? "로그인 중..." : "로그인" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import api from "@/services/api"; // ✅ axios 인스턴스
import { nextTick, onMounted, ref } from "vue";

// ✅ 부모에게 보낼 이벤트 정의
const emit = defineEmits(["close", "success"]);

const username = ref("");
const password = ref("");
const loading = ref(false);

const usernameInput = ref(null);
const passwordInput = ref(null);

// ✅ 모달 열리면 아이디 입력창 포커스
onMounted(async () => {
  await nextTick();
  usernameInput.value?.focus();
});

// ✅ Enter 누르면 비밀번호로 이동
const focusPassword = async () => {
  await nextTick();
  passwordInput.value?.focus();
};

// ✅ 로그인 로직 (FastAPI 연동)
const login = async () => {
  if (!username.value || !password.value) {
    alert("아이디와 비밀번호를 모두 입력해주세요.");
    return;
  }

  loading.value = true;

  try {
    const res = await api.post("/auth/login", {
      username: username.value,
      password: password.value,
    });

    // ✅ 토큰 저장
    localStorage.setItem("access_token", res.data.access_token);
    console.log("로그인 성공:", res.data);

    emit("success"); // App.vue 로 알림
  } catch (err) {
    console.error("로그인 실패:", err);
    if (err.response?.status === 401) {
      alert("아이디 또는 비밀번호가 올바르지 않습니다.");
    } else {
      alert("서버 오류가 발생했습니다.");
    }
  } finally {
    loading.value = false;
  }
};

// ✅ 모달 닫기
const closeModal = () => emit("close");
</script>
