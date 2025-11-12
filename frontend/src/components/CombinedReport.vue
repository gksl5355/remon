<template>
  <div
    class="bg-[#111]/90 rounded-2xl p-6 shadow-[0_0_25px_rgba(0,0,0,0.4)]
           h-full max-h-full overflow-y-auto font-sans"
  >
    <!-- Header -->
    <div class="flex items-center justify-between mb-5 border-b border-[#2a2a2a] pb-3">
      <div>
        <h2 class="text-xl tracking-widest text-[#E8C663] uppercase">
          Combined Report
        </h2>
        <p class="text-xs text-gray-500 mt-1">기간별 종합 리포트 다운로드</p>
      </div>
    </div>

    <!-- 설명 -->
    <p class="text-gray-400 text-[13px] mb-5 leading-snug">
      입력한 기간 동안 생성된 요약 리포트를 종합하여 하나의 리포트로 다운로드할 수 있습니다.
    </p>

    <!-- 기간 선택 + 버튼 -->
    <div class="flex items-center gap-3 justify-end text-sm">
      <label class="text-gray-400">기간:</label>

      <!-- 시작일 -->
      <div class="relative flex items-center">
        <input type="date" v-model="startDate" class="date-input pr-8" />
        <!-- 캘린더 아이콘 -->
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          stroke-width="1.6"
          stroke="#aa9865"
          class="w-4 h-4 absolute right-2 pointer-events-none"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"
          />
        </svg>
      </div>

      <span class="text-gray-400">~</span>

      <!-- 종료일 -->
      <div class="relative flex items-center">
        <input type="date" v-model="endDate" class="date-input pr-8" />
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          stroke-width="1.6"
          stroke="#aa9865"
          class="w-4 h-4 absolute right-2 pointer-events-none"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"
          />
        </svg>
      </div>

      <!-- 다운로드 버튼 -->
      <button class="report-btn flex items-center gap-2" @click="downloadReport">
        <svg
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
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M7.5 10.5l4.5 4.5m0 0l4.5-4.5m-4.5 4.5V3"
          />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import api from "@/services/api";
import { ref } from "vue";

const startDate = ref("");
const endDate = ref("");

const downloadReport = async () => {
  if (!startDate.value || !endDate.value) {
    alert("기간을 모두 입력해주세요.");
    return;
  }

  try {
    const res = await api.get("/reports/combined/download", {
      params: {
        start_date: startDate.value,
        end_date: endDate.value,
      },
      responseType: "blob",
    });

    const blob = new Blob([res.data], { type: "application/pdf" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `Combined_Report_${startDate.value}_${endDate.value}.pdf`;
    link.click();
  } catch (err) {
    console.error("다운로드 오류:", err);
    if (err.response?.status === 404)
      alert("해당 기간에는 리포트가 없습니다.");
    else alert("서버 오류가 발생했습니다.");
  }
};
</script>


<style scoped>
@reference "tailwindcss";

.date-input {
  @apply bg-[#1b1b1b] border border-[#2b2b2b] rounded-md px-3 py-1.5 text-[13px] text-gray-300
         focus:ring-1 focus:ring-[#E8C663] focus:outline-none transition w-[145px];
  appearance: none;
}

.report-btn {
  @apply font-medium text-[13px] px-4 py-1.5 rounded-md transition-all duration-200 ease-out transform active:scale-95;
  color: #E8C663;
  cursor: pointer;
}
.report-btn:hover {
  border-color: #E8C663;
  color: #2f2f2f;
  background: #E8C663;
  box-shadow: 0 0 8px rgba(232, 198, 99, 0.3);
}
</style>
