<template>
  <div
    class="bg-[#111] border border-[#2b2b2b] rounded-2xl p-6 shadow-md flex flex-col h-[480px] relative"
  >
    <!-- 🔹 제목 -->
    <div class="flex justify-between items-center mb-5 relative">
      <div>
        <h2 class="text-lg text-[#D4AF37] tracking-wide font-medium">
          SUMMARY REPORTS
        </h2>
        <p class="text-xs text-gray-500 mt-1">국가 및 제품별 요약 리포트 관리</p>
      </div>

      <!-- 🔹 버튼 -->
      <div class="flex items-center gap-3">
        <!-- 필터 버튼 -->
        <button
          class="text-[#E8C663] hover:text-[#FFD56A]"
          @click.stop="toggleFilter"
          title="필터 열기"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none"
            viewBox="0 0 24 24" stroke-width="1.6" stroke="currentColor" class="w-5 h-5">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M3 4.5h18m-9 7.5h9m-6 7.5h6" />
          </svg>
        </button>
      </div>

      <!-- 🔸 필터 팝업 -->
      <transition name="fade">
        <div
          v-if="showFilter"
          ref="filterPopup"
          class="absolute right-0 top-10 bg-[#1b1b1b] border border-[#333] rounded-lg p-4 text-xs w-[260px] z-50 shadow-xl"
        >
          <h3 class="text-[#D4AF37] font-semibold mb-2">필터 설정</h3>

          <div class="flex flex-col mb-3">
            <label class="text-[#a99d7b] mb-1">국가 선택</label>
            <select
              v-model="filterCountry"
              class="bg-[#111] text-gray-200 border border-[#333] rounded-md px-2 py-1 focus:outline-none focus:border-[#D4AF37]"
            >
              <option value="">전체</option>
              <option v-for="c in countries" :key="c">{{ c }}</option>
            </select>
          </div>

          <div class="flex flex-col mb-3">
            <label class="text-[#a99d7b] mb-1">리포트 제목</label>
            <input
              v-model="filterTitle"
              type="text"
              placeholder="예: 니코틴 라벨"
              class="bg-[#111] text-gray-200 border border-[#333] rounded-md px-2 py-1 focus:outline-none focus:border-[#D4AF37]"
            />
          </div>

          <div class="flex justify-end mt-4 gap-2">
            <button
              class="px-2 py-1 bg-[#D4AF37] text-black rounded-md text-[11px] hover:bg-[#f0d86b]"
              @click="applyFilter"
            >적용</button>
            <button
              class="px-2 py-1 bg-[#444] text-gray-300 rounded-md text-[11px] hover:bg-[#555]"
              @click="resetFilter"
            >해제</button>
          </div>
        </div>
      </transition>
    </div>

    <!-- 🔹 테이블 -->
    <div class="flex-1 overflow-y-auto border-t border-[#222]">
      <table class="w-full text-xs border-collapse">
        <thead class="bg-[#111]/95 sticky top-0 z-[40] text-gray-400 border-b border-[#333]">
          <tr>
            <th class="py-2 text-left w-[10%] font-normal">국가</th>
            <th class="py-2 text-left font-normal">제목</th>
            <th class="py-2 text-left w-[20%] font-normal">업데이트</th>
            <th class="py-2 text-center w-[20%] font-normal">관리</th>
          </tr>
        </thead>

        <tbody>
          <tr
            v-for="report in filteredReports"
            :key="report.id"
            class="border-b border-[#1e1e1e] hover:bg-[#1c1c1c] transition"
          >
            <td class="py-2 pl-2">{{ report.country }}</td>
            <td class="py-2 truncate max-w-[280px]">{{ report.title }}</td>
            <td class="py-2">{{ report.last_updated }}</td>
            <td class="py-2 text-center flex justify-center gap-4">
              <!-- 보기 -->
              <button
                class="text-[#E8C663] hover:text-[#FFD56A]"
                title="리포트 보기"
                @click="openReport(report)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none"
                  viewBox="0 0 24 24" stroke-width="1.6" stroke="currentColor" class="w-4 h-4">
                  <path stroke-linecap="round" stroke-linejoin="round"
                    d="M2.036 12.322a1.012 1.012 0 010-.644C3.423 7.51 7.355 4.5 12 4.5s8.577 3.01 9.964 7.178c.07.21.07.436 0 .644C20.577 16.49 16.645 19.5 12 19.5s-8.577-3.01-9.964-7.178z" />
                  <path stroke-linecap="round" stroke-linejoin="round"
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </button>

              <!-- 다운로드 -->
              <button
                class="text-[#E8C663] hover:text-[#FFD56A]"
                title="다운로드"
                @click="downloadReport(report.id)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none"
                  viewBox="0 0 24 24" stroke-width="1.6" stroke="currentColor" class="w-4 h-4">
                  <path stroke-linecap="round" stroke-linejoin="round"
                    d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-9-9v9m0 0l3.75-3.75M12 16.5L8.25 12.75" />
                </svg>
              </button>

              <!-- 삭제 -->
              <button
                class="text-red-400 hover:text-red-300"
                title="삭제"
                @click="deleteReport(report.id)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none"
                  viewBox="0 0 24 24" stroke-width="1.6" stroke="currentColor" class="w-4 h-4">
                  <path stroke-linecap="round" stroke-linejoin="round"
                    d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </td>
          </tr>

          <tr v-if="filteredReports.length === 0">
            <td colspan="4" class="text-center text-gray-500 py-4">
              조건에 맞는 리포트가 없습니다.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ✨ 리포트 팝업 -->
    <transition name="fade">
      <div
        v-if="showModal"
        class="fixed inset-0 bg-black/60 flex items-center justify-center z-[100]"
        @click.self="closeModal"
      >
        <div
          class="bg-[#111]/95 border border-[#2e2e2e] rounded-2xl w-[800px] h-[80vh] shadow-[0_0_25px_rgba(0,0,0,0.4)] flex flex-col overflow-hidden"
        >
          <!-- Header -->
          <div class="bg-[#111] border-b border-[#2e2e2e] px-6 py-4 flex items-center justify-between">
            <div>
              <h2 class="text-lg tracking-widest text-[#E8C663] uppercase">
                {{ selectedReport.title }}
              </h2>
              <p class="text-xs text-gray-500 mt-1">
                {{ selectedReport.country }} / {{ selectedReport.last_updated }}
              </p>
            </div>

            <div class="flex items-center gap-3">
              <button
                v-if="!isEditing"
                class="px-3 py-1.5 text-xs bg-[#2f2f2f] text-[#E8C663] rounded-md border border-[#3a3a3a] hover:border-[#E8C663]"
                @click="isEditing = true"
              >
                수정
              </button>
              <button
                v-else
                class="px-3 py-1.5 text-xs bg-[#E8C663] text-[#111] rounded-md font-semibold hover:bg-[#FFD56A]"
                @click="saveChanges"
              >
                저장
              </button>
              <button
                class="px-3 py-1.5 text-xs bg-[#2f2f2f] text-gray-400 rounded-md border border-[#3a3a3a] hover:text-white"
                @click="closeModal"
              >
                닫기
              </button>
            </div>
          </div>

          <!-- 본문 -->
          <div class="flex-1 overflow-y-auto p-6 space-y-6 text-[13px] leading-relaxed text-gray-300 scrollbar-thin scrollbar-thumb-[#2e2e2e] scrollbar-track-transparent">
            <section
              v-for="(section, key) in sections"
              :key="key"
              class="bg-[#151515]/70 rounded-lg border border-[#2e2e2e] p-5"
            >
              <h3 class="text-sm font-semibold text-[#E8C663] mb-3 border-b border-[#2e2e2e] pb-1.5">
                {{ section.title }}
              </h3>

              <!-- paragraph -->
              <div v-if="section.type === 'paragraph'">
                <p
                  v-for="(line, i) in section.content"
                  :key="i"
                  :contenteditable="isEditing"
                  class="editable-line"
                  @input="updateParagraph(key, i, $event)"
                >
                  {{ line }}
                </p>
              </div>

              <!-- table -->
              <div v-else-if="section.type === 'table'" class="overflow-x-auto">
                <table class="w-full border-collapse text-gray-300 text-xs">
                  <thead>
                    <tr class="bg-[#1b1b1b] border-b border-[#333]">
                      <th v-for="h in section.headers" :key="h" class="px-2 py-1 text-left font-semibold">
                        {{ h }}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="(row, r) in section.rows"
                      :key="r"
                      class="editable-line hover:bg-[#222] transition rounded-md"
                      :contenteditable="false"
                    >
                      <td
                        v-for="(cell, c) in row"
                        :key="c"
                        class="px-2 py-1"
                        :contenteditable="isEditing"
                        @input="updateTable(key, r, c, $event)"
                      >
                        {{ cell }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <!-- list -->
              <ul v-else-if="section.type === 'list'" class="list-disc ml-4">
                <li
                  v-for="(item, i) in section.content"
                  :key="i"
                  class="editable-line"
                  :contenteditable="isEditing"
                  @input="updateList(key, i, $event)"
                >
                  {{ item }}
                </li>
              </ul>

              <!-- links -->
              <div v-else-if="section.type === 'links'" class="space-y-2">
                <div v-for="(link, i) in section.content" :key="i">
                  <template v-if="!isEditing">
                    <a :href="link.url" target="_blank" class="text-blue-400 hover:underline">
                      {{ link.text }}
                    </a>
                  </template>
                  <template v-else>
                    <input
                      v-model="sections[key].content[i].text"
                      class="editable-line bg-[#111] border border-[#333] rounded-md text-gray-200 px-2 py-1 w-full text-xs"
                    />
                    <input
                      v-model="sections[key].content[i].url"
                      class="editable-line bg-[#111] border border-[#333] rounded-md text-gray-400 px-2 py-1 w-full text-xs mt-1"
                    />
                  </template>
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import api from "@/services/api.js";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

const reports = ref([]);
const sections = ref({});
const selectedReport = ref({});
const showFilter = ref(false);
const showModal = ref(false);
const isEditing = ref(false);
const filterCountry = ref("");
const filterTitle = ref("");
const countries = ["KR", "US", "JP", "CN", "EU"];

// ✅ 데이터 불러오기
const fetchReports = async () => {
  try {
    const res = await api.get("/admin/summary");
    reports.value = Object.entries(res.data).map(([id, v]) => ({
      id,
      title: v.title,
      last_updated: v.last_updated,
      country: v.title.includes("EU") ? "EU" : v.title.includes("USA") ? "US" : "KR",
      sections: v.sections,
    }));
  } catch (err) {
    console.error("❌ 리포트 목록 불러오기 실패:", err);
  }
};

// ✅ 보기 / 수정 / 닫기 / 저장
const openReport = (report) => {
  selectedReport.value = report;
  sections.value = JSON.parse(JSON.stringify(report.sections));
  showModal.value = true;
  isEditing.value = false;
};
const saveChanges = () => {
  Object.assign(selectedReport.value.sections, sections.value);
  isEditing.value = false;
  alert("리포트 수정이 저장되었습니다.");
};
const closeModal = () => {
  showModal.value = false;
  isEditing.value = false;
};

// ✅ 삭제
const deleteReport = (id) => {
  if (confirm("이 리포트를 삭제하시겠습니까?"))
    reports.value = reports.value.filter((r) => r.id !== id);
};

// ✅ 다운로드
const downloadReport = (id) => {
  window.open(`http://localhost:8000/api/admin/summary/${id}/download/pdf`, "_blank");
};

// ✅ 필터
const filteredReports = computed(() =>
  reports.value.filter((r) => {
    const matchC = filterCountry.value ? r.country === filterCountry.value : true;
    const matchT = filterTitle.value
      ? r.title.toLowerCase().includes(filterTitle.value.toLowerCase())
      : true;
    return matchC && matchT;
  })
);
const toggleFilter = () => (showFilter.value = !showFilter.value);
const applyFilter = () => (showFilter.value = false);
const resetFilter = () => {
  filterCountry.value = "";
  filterTitle.value = "";
  showFilter.value = false;
};

// ✅ contenteditable 업데이트
const updateParagraph = (key, idx, e) =>
  (sections.value[key].content[idx] = e.target.innerText);
const updateList = (key, idx, e) =>
  (sections.value[key].content[idx] = e.target.innerText);

// ✅ 외부 클릭 시 필터 닫기
const handleClickOutside = (e) => {
  if (showFilter.value && !e.target.closest(".absolute")) showFilter.value = false;
};

onMounted(() => {
  document.addEventListener("click", handleClickOutside);
  fetchReports();
});
onBeforeUnmount(() => document.removeEventListener("click", handleClickOutside));
</script>

<style scoped>
@reference "tailwindcss";

/* ✨ 편집 가능한 영역 스타일 */
.editable-line[contenteditable="true"],
tbody tr[contenteditable="true"] {
  background-color: rgba(232, 198, 99, 0.08);
  border-radius: 4px;
  box-shadow: 0 0 0 1px rgba(232, 198, 99, 0.15) inset;
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}
.editable-line[contenteditable="true"]:focus,
tbody tr[contenteditable="true"]:focus {
  background-color: rgba(232, 198, 99, 0.18);
  box-shadow: 0 0 6px rgba(232, 198, 99, 0.25);
}
.editable-line[contenteditable="true"]:hover,
tbody tr[contenteditable="true"]:hover {
  background-color: rgba(232, 198, 99, 0.13);
}

/* Fade transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
