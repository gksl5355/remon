<template>
  <div
    class="bg-[#111]/90 backdrop-blur-lg rounded-2xl shadow-[0_0_25px_rgba(0,0,0,0.4)]
           flex flex-col overflow-hidden h-[calc(100vh-180px)]"
  >
    <!-- 🔹 헤더 (sticky) -->
    <div
      class="sticky top-0 z-10 bg-[#111]/95 backdrop-blur-lg border-b border-[#2b2b2b] px-6 py-4 flex items-center justify-between"
    >
      <div>
        <h2 class="text-xl tracking-widest text-[#E8C663] uppercase">
          Regulation Updates
        </h2>
        <p class="text-xs text-gray-500 mt-1">변동된 규제 목록</p>
      </div>

      <div class="text-right">
        <p class="text-[#D4AF37] text-sm mb-1">오늘 변경된 규제</p>
        <p class="text-2xl text-white font-light">{{ todayCount }} 개</p>
      </div>
    </div>

    <!-- 🔹 내용 영역 -->
    <div v-if="loading" class="flex-1 flex items-center justify-center text-gray-400">
      <p>데이터를 불러오는 중...</p>
    </div>

    <div
      v-else
      class="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-thin scrollbar-thumb-[#444] scrollbar-track-transparent"
    >
      <div
        v-if="regulations.length > 0"
        v-for="r in regulations"
        :key="r.id"
        class="border border-[#2b2b2b] rounded-lg px-4 py-3 hover:bg-[#1a1a1a]/70 cursor-pointer transition"
        @click="$emit('select-regulation', r)"
      >
        <div class="flex items-center gap-3 mb-1">
          <span
            class="text-xs px-2.5 py-0.5 rounded-full font-semibold tracking-tight text-white"
            :class="badgeClass(r.impact)"
          >
            {{ r.impact }}
          </span>
          <p class="text-sm text-gray-200 font-light tracking-wide">
            {{ r.country }} · {{ r.category }}
          </p>
        </div>
        <p class="text-gray-400 text-[13px] leading-snug">{{ r.summary }}</p>
      </div>

      <div v-else class="text-center text-gray-500 text-sm py-10">
        현재 등록된 규제 데이터가 없습니다.
      </div>
    </div>
  </div>
</template>

<script setup>
import api from "@/services/api"; // ✅ axios 인스턴스 import
import { onMounted, ref } from "vue";

const regulations = ref([]);
const todayCount = ref(0);
const loading = ref(false);

const fetchRegulations = async () => {
  loading.value = true;
  try {
    const res = await api.get("/regulations"); // ✅ baseURL 자동 적용
    regulations.value = res.data.regulations || [];
    todayCount.value = res.data.today_count || regulations.value.length;
  } catch (err) {
    console.error("❌ 규제 목록 불러오기 실패:", err);
  } finally {
    loading.value = false;
  }
};

onMounted(fetchRegulations);

function badgeClass(level) {
  return {
    긴급: "bg-[#D94C3D]",
    높음: "bg-[#D4AF37]/90 text-black font-bold",
    보통: "bg-[#444]/80 text-gray-200",
  }[level];
}
</script>

<style scoped>
@reference "tailwindcss";

.scrollbar-thin::-webkit-scrollbar {
  width: 6px;
}
.scrollbar-thin::-webkit-scrollbar-thumb {
  background-color: rgba(255, 255, 255, 0.15);
  border-radius: 6px;
}
.scrollbar-thin::-webkit-scrollbar-thumb:hover {
  background-color: rgba(255, 255, 255, 0.3);
}
</style>
