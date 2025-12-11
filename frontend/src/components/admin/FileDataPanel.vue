<template>
  <div class="flex flex-col h-full">

    <!-- TITLE -->
    <!-- <h2 class="text-[15px] font-semibold tracking-widest text-gray-300 mb-5">
      FILE DATA MANAGEMENT
    </h2> -->

    <!-- FILE DATA HEADER -->
    <div class="flex items-center justify-between mb-6">

        <div class="flex items-center gap-3">
            <!-- Icon -->
            <div
            class="w-9 h-9 flex items-center justify-center rounded-lg
                    bg-gradient-to-br from-[#2A3953] to-[#1B2535] border border-white/10"
            >
            <svg xmlns="http://www.w3.org/2000/svg" 
                fill="none" viewBox="0 0 24 24" stroke-width="1.5"
                stroke="#AFC7EA" class="w-5 h-5">
                <path stroke-linecap="round" stroke-linejoin="round"
                d="M9 12h6m-6 4h6M9 8h6M5 4h14v16H5V4z"/>
            </svg>
            </div>

            <!-- Title + Subtitle -->
            <div>
            <h2 class="text-[16px] font-semibold tracking-wide text-gray-200 flex items-center gap-2">
                FILE DATA MANAGEMENT
            </h2>
            <p class="text-xs text-gray-500 mt-0.5">
                Regulation PDFs · AI Reports
            </p>
            </div>
        </div>

    </div>


    <!-- =============================== -->
    <!-- FILTER BAR (토글 + 필터 + Add) -->
    <!-- =============================== -->
    <div class="flex flex-wrap items-center gap-4 mb-5">

      <!-- 3-Stage Toggle -->
      <div class="flex items-center bg-[#111A28] border border-gray-700 rounded-full px-1 py-0.5 select-none">

        <!-- All -->
        <div
          @click="view = 'all'"
          :class="[
            'px-4 py-1 text-xs font-medium rounded-full cursor-pointer transition',
            view === 'all'
              ? 'bg-white text-black shadow'
              : 'text-gray-400 hover:text-gray-200'
          ]"
        >
          All
        </div>

        <!-- Regulation -->
        <div
          @click="view = 'reg'"
          :class="[
            'px-4 py-1 text-xs font-medium rounded-full cursor-pointer transition',
            view === 'reg'
              ? 'bg-[#3A4F7A] text-white shadow'
              : 'text-gray-400 hover:text-gray-200'
          ]"
        >
          Regulation
        </div>

        <!-- Report -->
        <div
          @click="view = 'report'"
          :class="[
            'px-4 py-1 text-xs font-medium rounded-full cursor-pointer transition',
            view === 'report'
              ? 'bg-[#88C0D0] text-black shadow'
              : 'text-gray-400 hover:text-gray-200'
          ]"
        >
          AI Report
        </div>
      </div>

      <!-- Divider -->
      <div class="h-6 w-[1px] bg-gray-700/50"></div>

      <!-- Country Filter -->
      <select v-model="filters.country" class="filter-select">
        <option value="">국가 전체</option>
        <option v-for="c in countries" :key="c">{{ c }}</option>
      </select>

      <!-- Product Filter -->
      <select v-model="filters.product" class="filter-select">
        <option value="">제품 전체</option>
        <option v-for="p in products" :key="p">{{ p }}</option>
      </select>

      <!-- Add Button -->
      <button
        class="ml-auto px-3 py-1.5 rounded-md text-xs font-medium border border-white/20
               bg-white/5 text-gray-200 hover:bg-white/10 transition flex items-center gap-1"
        @click="showAddModal = true"
      >
        <span class="text-lg leading-none">+</span> Add
      </button>
    </div>

    <!-- =============================== -->
    <!-- LIST AREA -->
    <!-- =============================== -->
    <div class="flex-1 overflow-y-auto space-y-4 custom-scrollbar">

      <div
        v-for="item in filteredList"
        :key="item.id"
        class="relative group p-4 rounded-lg cursor-pointer transition-all 
               border border-gray-800 bg-[#0F1828]
               hover:bg-[#152033] hover:border-gray-600 hover:shadow-md"
      >

        <!-- Accent Bar -->
        <div
          class="absolute left-0 top-0 h-full w-[3px] rounded-l-lg"
          :style="{ backgroundColor: item.type === 'reg' ? '#3A4F7A' : '#88C0D0' }"
        ></div>

        <!-- Hover Action Buttons -->
        <div
          class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition flex gap-2"
        >
          
          <!-- Edit (AI Report only) -->
          <button
              v-if="item.type === 'report'"
              class="p-1.5 rounded-md bg-white/10 hover:bg-white/20 transition"
              @click.stop="openReportModal(item)"
          >
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-gray-200"
              fill="none" viewBox="0 0 24 24" stroke-width="1.6" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round"
                  d="M16.862 3.487l3.651 3.65-10.06 10.061L6.8 13.55l10.062-10.062zM5 19h14"/>
              </svg>
          </button>

          <!-- Download -->
          <button
            class="p-1.5 rounded-md bg-white/10 hover:bg-white/20 transition"
            @click.stop="downloadItem(item)"
          >
            <svg xmlns="http://www.w3.org/2000/svg"
                class="w-4 h-4 text-gray-200"
                fill="none" viewBox="0 0 24 24" stroke-width="1.6" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round"
                    d="M12 4v12m0 0l-5-5m5 5l5-5" />
            </svg>
          </button>

          <!-- Delete -->
          <button
            class="p-1.5 rounded-md bg-white/10 hover:bg-white/20 transition"
            @click.stop="deleteItem(item.id)"
          >
            <svg xmlns="http://www.w3.org/2000/svg"
                class="w-4 h-4 text-gray-200"
                fill="none" viewBox="0 0 24 24" stroke-width="1.6" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round"
                    d="M6 7h12M10 11v6m4-6v6M9 7V4h6v3m2 0v13H7V7h10z" />
            </svg>
          </button>
        </div>

        <!-- Content -->
        <div class="pl-4">
          <h4 class="text-[14px] font-semibold text-gray-100">
            {{ item.name }}
          </h4>

          <!-- 국가 / 날짜 -->
          <div class="text-[12px] text-gray-400">
            {{ item.country }} · {{ item.date }}
          </div>

        </div>
      </div>

      <div
        v-if="filteredList.length === 0"
        class="py-10 text-center text-gray-500"
      >
        데이터가 없습니다.
      </div>

    </div>

    <!-- Add Modal -->
    <AddModal
      v-if="showAddModal"
      @close="showAddModal = false"
      @save="addFile"
    />

    <ReportModal
      v-if="showReportModal"
      :data="selectedReport"
      @close="showReportModal = false"
      @save="updateReport"
    />
  </div>
</template>

<script setup>
import AddModal from "@/components/admin/AddModal.vue";
import ReportModal from "@/components/admin/ReportModal.vue";
import { computed, ref } from "vue";

const showAddModal = ref(false);
const showReportModal = ref(false);
const selectedReport = ref(null);

/* ------------------ Toggle 상태 ------------------ */
const view = ref("all");

/* ------------------ Filters ------------------ */
const filters = ref({
  country: "",
  product: ""
});

/* ------------------ Dummy Data ------------------ */
const fileList = ref([
  { id: 1, name: "US Regulation Update 2024", type: "reg", country: "US", product: "Heated Tobacco", date: "2024-02-10" },
  { id: 2, name: "RU Heated Tobacco AI Report", type: "report", country: "RU", product: "Heated Tobacco", date: "2024-03-01" },
  { id: 3, name: "ID E-Cigarette Amendment", type: "reg", country: "ID", product: "E-Cigarette", date: "2024-01-23" }
]);

/* ------------------ 목록 필터링 ------------------ */
const filteredList = computed(() =>
  fileList.value.filter(f => {
    if (view.value !== "all" && f.type !== view.value) return false;
    if (filters.value.country && f.country !== filters.value.country) return false;
    if (filters.value.product && f.product !== filters.value.product) return false;
    return true;
  })
);

const countries = ["US", "RU", "ID"];
const products = ["Heated Tobacco", "E-Cigarette", "Cigarette"];

/* ------------------ 파일 추가 ------------------ */
function addFile(data) {
  fileList.value.push({
    id: Date.now(),
    ...data,
    date: new Date().toISOString().split("T")[0]
  });
}

/* ------------------ Delete & Download ------------------ */
function deleteItem(id) {
  fileList.value = fileList.value.filter(f => f.id !== id);
}

function downloadItem(item) {
  alert(`Downloading: ${item.name}`);
}

const dummyReports = {
  2: {
    summary: {
      country: "미국",
      category: "일반 규제",
      regulationSummary: "해당 조항에서 마침표가 콜론으로 변경됨.",
      impact: "Low (0.85)",
      recommendation: "라벨링 검토 프로세스를 수립하세요."
    },
    products: [
      { item: "nicotin", product: "Product-1", current: "0.8", required: "None" },
      { item: "tarr", product: "Product-1", current: "8.0", required: "None" }
    ],
    changeAnalysis: [
      "구두점 변경은 실질적 영향이 매우 적습니다.",
      "제품 성분이나 법적 요건에는 변화 없음."
    ],
    strategy: [
      "라벨링 검토 프로세스 수립",
      "행정 문서 업데이터 사전 준비"
    ],
    impactReason: "구두점 변경은 최소 영향도로 분류되며 운영 비용 또한 거의 없음.",
    references: [{ name: "FDA 원문", url: "https://www.fda.gov/example" }]
  }
};

function openReportModal(item) {
  selectedReport.value = dummyReports[item.id];
  showReportModal.value = true;
}

function updateReport(newData) {
  // 실제로는 서버 저장, 여기서는 console 로그
  console.log("수정된 리포트:", newData);
  selectedReport.value = JSON.parse(JSON.stringify(newData));
}

</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgba(255, 255, 255, 0.15);
  border-radius: 8px;
}

.filter-select {
  background: #111A28;
  border: 1px solid #374155;
  padding: 6px 10px;
  border-radius: 6px;
  color: #d0d8e6;
  font-size: 12px;
}
</style>
