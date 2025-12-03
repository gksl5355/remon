<template>
  <div
    class="bg-[#111]/90 rounded-2xl shadow-[0_0_25px_rgba(0,0,0,0.4)]
           h-full flex flex-col overflow-hidden font-sans text-[13px]"
  >
    <!-- 🔹 헤더 -->
    <div
      class="sticky top-0 z-20 bg-[#111] border-b border-[#2e2e2e]
             px-6 py-4 flex items-center justify-between shadow-[0_4px_12px_rgba(0,0,0,0.3)]"
    >
      <div>
        <h2 class="text-xl tracking-widest text-[#E8C663] uppercase">
          Summary Report
        </h2>
        <p class="text-xs text-gray-500 mt-1 font-normal">
          규제별 요약 리포트
        </p>
      </div>

      <!-- 🔹 다운로드 버튼 (규제 선택 시만 표시) -->
      <div v-if="selectedRegulation">
        <button
          @click="downloadReport"
          class="flex items-center gap-1 px-3 py-1.5 rounded-md text-[12px]
                 text-[#E8C663] border border-[#E8C663]/30 hover:bg-[#E8C663]
                 hover:text-[#111] transition duration-200"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none"
               viewBox="0 0 24 24" stroke-width="1.6"
               stroke="currentColor" class="w-4 h-4">
            <path stroke-linecap="round" stroke-linejoin="round"
                  d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M7.5 10.5l4.5 4.5m0 0l4.5-4.5m-4.5 4.5V3" />
          </svg>
          <span>Download</span>
        </button>
      </div>
    </div>

    <!-- 🔹 로딩 상태 -->
    <div v-if="loading" class="flex-1 flex items-center justify-center text-gray-500">
      <p>리포트를 불러오는 중...</p>
    </div>

    <!-- 🔹 본문 -->
    <div
      v-else-if="reportData"
      class="flex-1 overflow-y-auto p-6 space-y-6 text-[13px] leading-relaxed text-gray-300"
    >
      <!-- 제목 -->
      <div class="pb-3 border-b border-[#333] mb-4">
        <h2 class="text-lg font-semibold text-[#a7af53] mb-1">
          {{ reportData.title }}
        </h2>
        <p class="text-xs text-gray-500">최종 수정일: {{ reportData.last_updated }}</p>
      </div>

      <!-- 섹션 반복 -->
      <div
        v-for="(section, key) in reportData.sections"
        :key="key"
        class="report-section rounded-xl border border-[#2a2a2a]
               p-5 transition-all duration-200 hover:bg-[#181818]/80
               shadow-[inset_0_0_12px_rgba(0,0,0,0.3)]"
        :class="sectionClass(section.type)"
      >
        <div class="flex items-center gap-2 mb-3">
          <!-- <div class="w-1 h-5 rounded bg-[#a7ab82]/90"></div> -->
          <h3 class="text-sm font-semibold text-[#a7ab82]">
            {{ section.title }}
          </h3>
        </div>

        <div v-html="renderSection(section)"></div>
      </div>
    </div>

    <!-- 🔹 기본 메시지 -->
    <div v-else class="flex-1 flex items-center justify-center text-gray-500">
      <p>좌측에서 규제를 선택하면 요약 리포트가 표시됩니다.</p>
    </div>
  </div>
</template>

<script setup>
import api from "@/services/api";
import { ref, watch } from "vue";

const props = defineProps({
  selectedRegulation: Object,
});

const reportData = ref(null);
const loading = ref(false);

// ✅ 규제 선택 시 자동 호출
watch(
  () => props.selectedRegulation,
  async (reg) => {
    if (!reg) {
      reportData.value = null;
      return;
    }
    loading.value = true;
    try {
      const res = await api.get(`/reports/${reg.id}`);
      reportData.value = res.data;
    } catch (err) {
      console.error("리포트 불러오기 실패:", err);
    } finally {
      loading.value = false;
    }
  }
);

// ✅ 다운로드 기능
const downloadReport = async () => {
  if (!props.selectedRegulation) return;
  const id = props.selectedRegulation.id;

  try {
    const res = await api.get(`/reports/${id}/download`, { responseType: "blob" });
    const blob = new Blob([res.data], { type: "application/pdf" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${reportData.value.title}.pdf`;
    link.click();
  } catch (err) {
    console.error("리포트 다운로드 실패:", err);
    alert("리포트 다운로드 중 오류가 발생했습니다.");
  }
};

// ✅ 섹션 렌더링
const renderSection = (section) => {
  if (section.type === "paragraph") {
    return section.content.map((line) => `<p class='mb-1.5'>${line}</p>`).join("");
  }
  if (section.type === "list") {
    return `<ul class='list-disc list-inside space-y-1.5'>
      ${section.content.map((item) => `<li>${item}</li>`).join("")}
    </ul>`;
  }
  if (section.type === "table") {
    const headers = section.headers.map((h) => `<th>${h}</th>`).join("");
    const rows = section.rows
      .map(
        (r) =>
          `<tr class='hover:bg-[#222]/70 transition'><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td></tr>`
      )
      .join("");
    return `
      <div class='overflow-x-auto'>
        <table class='min-w-full border border-[#333] rounded-md text-[12px]'>
          <thead class='bg-[#222] text-[#a7ab82]'>
            <tr>${headers}</tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }
  if (section.type === "links") {
    return section.content
      .map(
        (link) =>
<<<<<<< HEAD
          `<a href="${link.url}" target="_blank" class="text-[#9ecbff] underline hover:text-[#cbe4ff] transition">${link.text}</a><br/>`
=======
          `<a href="${link.url}" target="_blank" class="text-[#9ecbff] underline hover:text-[#cbe4ff] transition">${link.title}</a><br/>`
>>>>>>> origin/main
      )
      .join("");
  }
  return "";
};

// ✅ 섹션별 배경 강조
const sectionClass = (type) => {
  return {
    paragraph: "bg-[#141414]",
    list: "bg-[#161616]",
    table: "bg-[#121212]",
    links: "bg-[#101010]",
  }[type];
};
</script>

<style scoped>
@reference "tailwindcss";

table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  border: 1px solid #333;
  padding: 6px 8px;
  text-align: left;
}
th {
  font-weight: 600;
}
</style>
