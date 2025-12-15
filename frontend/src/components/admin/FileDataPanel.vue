<template>
  <div class="flex flex-col h-full">

    <!-- FILE DATA HEADER -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">

        <!-- ICON -->
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

        <!-- Title -->
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

    <!-- FILTER BAR -->
    <div class="flex flex-wrap items-center gap-4 mb-5">

      <!-- 3-Stage Toggle -->
      <div class="flex items-center bg-[#111A28] border border-gray-700 rounded-full px-1 py-0.5 select-none">

        <!-- All -->
        <div
          @click="view = 'all'"
          :class="toggleClass('all')"
        >
          All
        </div>

        <!-- Regulation -->
        <div
          @click="view = 'reg'"
          :class="toggleClass('reg')"
        >
          Regulation
        </div>

        <!-- Report -->
        <div
          @click="view = 'report'"
          :class="toggleClass('report')"
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

      <!-- DATE FILTER (한 줄 고정) -->
      <div class="flex items-center gap-2 flex-nowrap">

        <!-- DATE 버튼 -->
        <button
          @click="toggleDateFilter"
          class="flex items-center gap-2
                px-3 py-1.5 rounded-full
                bg-white/5 border border-white/10
                text-xs text-gray-300
                hover:bg-white/10 transition
                whitespace-nowrap"
        >
          <!-- calendar icon -->
          <svg xmlns="http://www.w3.org/2000/svg"
              class="w-4 h-4"
              fill="none" viewBox="0 0 24 24"
              stroke-width="1.5" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round"
                  d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7
                    a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
          </svg>
          날짜
        </button>

        <!-- 날짜 입력 (DATE 눌렀을 때만) -->
        <div
          v-if="showDateFilter"
          class="flex items-center gap-2 flex-nowrap"
        >
          <input
            type="date"
            v-model="filters.startDate"
            class="date-input"
          />

          <span class="text-gray-500/60 text-sm">–</span>

          <input
            type="date"
            v-model="filters.endDate"
            class="date-input"
          />
        </div>

      </div>

      <!-- Add Button -->
      <button
        class="ml-auto px-3 py-1.5 rounded-md text-xs font-medium border border-white/20
               bg-white/5 text-gray-200 hover:bg-white/10 transition flex items-center gap-1"
        @click="showAddModal = true"
      >
        <span class="text-lg leading-none">+</span> Add
      </button>
    </div>

    <!-- LIST AREA -->
    <div class="flex-1 overflow-y-auto space-y-4 custom-scrollbar">

      <div
        v-for="item in filteredList"
        :key="item.id"
        class="relative group p-4 rounded-lg cursor-pointer transition-all 
               border border-gray-800 bg-[#0F1828]
               hover:bg-[#152033] hover:border-gray-600 hover:shadow-md"
      >

        <!-- Left Accent Bar -->
        <div
          class="absolute left-0 top-0 h-full w-[3px] rounded-l-lg"
          :style="{ backgroundColor: item.type === 'reg' ? '#3A4F7A' : '#88C0D0' }"
        ></div>

        <!-- Hover Action Buttons -->
        <div class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition flex gap-2">

          <!-- Edit (Report only) -->
          <button
            v-if="item.type === 'report'"
            class="p-1.5 rounded-md bg-white/10 hover:bg-white/20 transition"
            @click.stop="openReportModal(item)"
          >
            <svg xmlns="http://www.w3.org/2000/svg"
                 class="w-4 h-4 text-gray-200"
                 fill="none" viewBox="0 0 24 24"
                 stroke-width="1.6" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round"
                    d="M16.862 3.487l3.651 3.65-10.06 10.061L6.8 13.55l10.062-10.062zM5 19h14"/>
            </svg>
          </button>

          <!-- Download -->
          <button
            class="p-1.5 rounded-md bg-white/10 hover:bg-white/20 transition"
            @click.stop="handleDownload(item)"
          >
            <svg xmlns="http://www.w3.org/2000/svg"
                 class="w-4 h-4 text-gray-200"
                 fill="none" viewBox="0 0 24 24" stroke-width="1.6"
                 stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round"
                    d="M12 4v12m0 0l-5-5m5 5l5-5"/>
            </svg>
          </button>

          <!-- Delete -->
          <button
            class="p-1.5 rounded-md bg-white/10 hover:bg-white/20 transition"
            @click.stop="deleteItem(item)"
          >
            <svg xmlns="http://www.w3.org/2000/svg"
                 class="w-4 h-4 text-gray-200"
                 fill="none" viewBox="0 0 24 24"
                 stroke-width="1.6"
                 stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round"
                    d="M6 7h12M10 11v6m4-6v6M9 7V4h6v3m2 0v13H7V7h10z"/>
            </svg>
          </button>
        </div>

        <!-- Content -->
        <div class="pl-4">
          <h4 class="text-[14px] font-semibold text-gray-100">
            {{ item.name }}
          </h4>

          <div class="text-[12px] text-gray-400">
            {{ item.country }} · {{ item.date }}
          </div>
        </div>
      </div>

      <div v-if="filteredList.length === 0"
           class="py-10 text-center text-gray-500">
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
      @close="showReportModal = false"
    />

    <!-- Download Popup -->
    <DownloadPopup
      v-if="showDownloadPopup"
      :item="popupTargetItem"
      @close="showDownloadPopup = false"
    />

    <!-- Translation Progress -->
    <TranslationProgressModal
      v-if="showTranslationProgress"
      :progress="translationProgress"
    />
  </div>
</template>

<script setup>
import api from "@/services/api";
import { computed, onMounted, ref } from "vue";

import AddModal from "@/components/admin/AddModal.vue";
import DownloadPopup from "@/components/admin/DownloadPopup.vue";
import ReportModal from "@/components/admin/ReportModal.vue";
import TranslationProgressModal from "@/components/admin/TranslationProgressModal.vue";

/* ---------- State ---------- */
const showAddModal = ref(false);
const showReportModal = ref(false);
const showDownloadPopup = ref(false);

const popupTargetItem = ref(null);

const view = ref("all");

const filters = ref({
  country: "",
  startDate: "",
  endDate: ""
});

const countries = ["US", "RU", "ID"];
const fileList = ref([]);
const showDateFilter = ref(false);

const toggleDateFilter = () => {
  // 이미 열려 있으면 → 닫으면서 초기화
  if (showDateFilter.value) {
    filters.value.startDate = "";
    filters.value.endDate = "";
  }

  showDateFilter.value = !showDateFilter.value;
};

/* ---------- Filtering ---------- */
const filteredList = computed(() =>
  fileList.value.filter(f => {
    // 타입 필터
    if (view.value !== "all" && f.type !== view.value) return false;

    // 국가 필터
    if (filters.value.country && f.country !== filters.value.country) return false;

    // 날짜 필터
    if (filters.value.startDate) {
      if (new Date(f.date) < new Date(filters.value.startDate)) return false;
    }

    if (filters.value.endDate) {
      if (new Date(f.date) > new Date(filters.value.endDate)) return false;
    }

    return true;
  })
);


/* ---------- Toggle Class ---------- */
const TOGGLE_COLOR = {
  all: {
    active: "bg-gray-200 text-black shadow",
    inactive: "text-gray-400 hover:text-gray-200"
  },
  reg: {
    active: "bg-[#3A4F7A] text-white shadow",
    inactive: "text-gray-400 hover:text-gray-200"
  },
  report: {
    active: "bg-[#88C0D0] text-black shadow",
    inactive: "text-gray-400 hover:text-gray-200"
  }
};

const toggleClass = (type) => {
  const isActive = view.value === type;
  const color = TOGGLE_COLOR[type];

  return [
    "px-4 py-1 text-xs font-medium rounded-full cursor-pointer transition-all duration-200",
    isActive ? color.active : color.inactive
  ];
};

/* ---------- Load File List ---------- */
onMounted(async () => {
  try {
    const res = await api.get("/admin/s3/list");
    const data = res.data;

    if (data.status === "success") {
      fileList.value = data.files.map(f => {
        const parts = f.s3_key.split("/");
        const folder = parts[3];
        const country = parts[4];
        const filename = parts[5] || "unknown";

        return {
          id: f.id,
          name: filename,
          country,
          type: folder === "regulation" ? "reg" : "report",
          s3_key: f.s3_key,
          size: f.size,
          date: f.date
        };
      });
    }
  } catch (e) {
    console.error("파일 목록 로드 실패:", e);
  }
});

/* ---------- Add ---------- */
function addFile(data) {
  fileList.value.push({
    id: Date.now(),
    name: data.name,
    type: data.type,
    country: data.country,
    s3_key: data.s3_key,
    date: data.date
  });
}

/* ---------- Delete ---------- */
async function deleteItem(item) {
  if (!confirm("정말 삭제하시겠습니까?")) return;

  try {
    await api.delete("/admin/s3/delete", {
      params: { s3_key: item.s3_key }
    });

    fileList.value = fileList.value.filter(f => f.s3_key !== item.s3_key);
  } catch (err) {
    console.error("삭제 실패:", err);
  }
}

/* ---------- Download ---------- */
async function downloadOriginal() {
  const res = await api.post("/admin/s3/download-url", {
    key: popupTargetItem.value.s3_key
  });

  if (res.data.url) window.open(res.data.url, "_blank");

  showDownloadPopup.value = false;
}

/* ---------- Download Translated ---------- */
const showTranslationProgress = ref(false);
const translationProgress = ref(0);

function handleDownload(item) {
  popupTargetItem.value = item;

  if (item.type === "reg") {
    showDownloadPopup.value = true;
  } else if (item.type === "report") {
    downloadOriginal();
  }
}

/* ---------- Dummy Report Modal ---------- */
function openReportModal(item) {
  showReportModal.value = true;
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

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.18s ease;
}
.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(-6px);
}
.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-6px);
}

.date-input {
  appearance: none;
  -webkit-appearance: none;

  width: 105px;
  height: 30px;
  padding: 6px 10px;

  border: none;
  border-radius: 9999px;

  background: rgba(255,255,255,0.06);
  color: #ffffff;
  font-size: 11px;
  text-align: center;
}

.date-input::placeholder {
  color: rgba(255,255,255,0.6);
}

.date-input::-webkit-calendar-picker-indicator {
  filter: invert(1);
  opacity: 0.9;
  cursor: pointer;
}

</style>
