<template>
  <div class="p-10 min-h-screen bg-[#080D17] text-gray-200">

    <!-- =============================== -->
    <!-- HEADER -->
    <!-- =============================== -->
    <div class="flex items-center gap-4 mb-4 relative">

      <!-- 국기 + 국가 코드 -->
      <div class="relative w-28 h-14 flex items-center justify-center overflow-hidden">
        <div
          class="absolute inset-0"
          :style="{
            backgroundImage: `
              linear-gradient(to right, rgba(8, 13, 23, 0), rgba(8, 13, 23, 1)),
              url(${flagUrl})
            `,
            backgroundSize: 'cover',
            backgroundPosition: 'center'
          }"
        ></div>
        <span class="relative text-3xl font-bold text-white">{{ countryCode }}</span>
      </div>

      <div class="h-12 w-[2px] bg-gray-600/40"></div>

      <!-- 문서 정보 -->
      <div class="flex flex-col gap-1">
        <h2 class="text-xl font-semibold text-gray-100">{{ selectedFileTitle }}</h2>

        <div class="text-sm text-gray-400 flex flex-wrap gap-x-5">
          <span>공포일: <span class="text-gray-300">{{ documentInfo.promulgationDate }}</span></span>
          <span>시행일: <span class="text-gray-300">{{ documentInfo.effectiveDate }}</span></span>
          <span>수집 시각: <span class="text-gray-300">{{ documentInfo.collectionTime }}</span></span>
        </div>
      </div>

      <!-- HEADER RIGHT: FILE TOGGLE -->
        <div class="ml-auto relative">
            <button
                @click="toggleFileList"
                class="px-4 py-1.5 text-sm rounded-lg flex items-center gap-2
                    bg-white/5 border border-white/10 text-gray-200
                    hover:bg-white/10 hover:border-white/20
                    shadow-sm transition-all backdrop-blur-md
                    hover:shadow-[0_0_12px_rgba(255,255,255,0.12)]"
            >
                <span class="tracking-wide">Files ({{ files.length }})</span>

                <svg
                :class="['transition-transform duration-200', isFileOpen ? 'rotate-180' : 'rotate-0']"
                xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
                fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                >
                <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
            </button>
        </div>

    </div>

    <!-- =============================== -->
    <!-- ▼ FILE LIST PANEL (HEADER 아래) -->
    <!-- =============================== -->
    <transition name="fade">
      <div
        v-if="isFileOpen"
        class="p-5 mb-8 rounded-xl bg-[#0D1523]/60 border border-gray-700/40 shadow-lg"
      >
        <h3 class="text-sm font-semibold tracking-widest text-gray-300 mb-4">
          UPDATED REGULATION FILE LIST
        </h3>

        <div class="space-y-3">

          <div
            v-for="(file, idx) in files"
            :key="file.id"
            class="group p-4 rounded-lg border border-gray-700/40
                    bg-gradient-to-br from-[#0D1523]/70 to-[#111a28]/70
                    hover:from-[#162033]/80 hover:to-[#1c2a3d]/80
                    shadow-sm hover:shadow-md transition-all cursor-pointer
                    flex justify-between items-center relative"
            @click="goToFile(file.id)"
            >

            <!-- LEFT IMPACT BAR -->

            <div class="flex items-start gap-4 ml-2">
                <div
                class="w-9 h-9 rounded-full flex items-center justify-center
                        bg-[#182231] border border-gray-600/40 text-gray-300 text-sm font-semibold
                        group-hover:bg-[#223045] group-hover:text-white transition"
                >
                {{ idx + 1 }}
                </div>

                <div class="flex flex-col">
                <div class="flex items-center gap-2">
                    <h4 class="text-gray-100 group-hover:text-white transition font-medium">
                    {{ file.title }}
                    </h4>

                    <!-- IMPACT BADGE -->
                    <span
                    class="text-[10px] px-2 py-0.5 rounded-full font-medium"
                    :style="impactBadgeStyle(file.impactLevel)"
                    >
                    {{ impactLabel(file.impactLevel) }}
                    </span>
                </div>

                <div class="text-xs text-gray-400 flex gap-6 mt-1">
                    <span>공포일: <span class="text-gray-300">{{ file.documentInfo.promulgationDate }}</span></span>
                    <span>시행일: <span class="text-gray-300">{{ file.documentInfo.effectiveDate }}</span></span>
                </div>
                </div>
            </div>
                <!-- <div class="text-gray-500 group-hover:text-gray-200 transition">➜</div> -->
            </div>

        </div>
      </div>
    </transition>

  <div class="w-full border-b border-white/10 mb-8"></div>

    <!-- =============================== -->
    <!-- MAIN CONTENT -->
    <!-- =============================== -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-8">

      <!-- LEFT -->
      <div
        class="lg:col-span-4 p-6 rounded-xl bg-[#0D1523]/60 
               border border-gray-700/40 shadow-lg flex flex-col h-[70vh]"
      >
        <h3 class="text-l font-semibold tracking-widest text-gray-300 mb-4">
          REGULATION ITEMS
        </h3>

        <!-- FILTER -->
        <div class="flex items-center gap-4 mb-6">
          <button
            @click="setFilter('all')"
            :class="[
              'px-3 py-1 text-[11px] rounded-md font-medium transition border',
              filter === 'all'
                ? 'bg-[#1b2535] text-white border-gray-500 shadow-sm'
                : 'bg-[#111a28] text-gray-400 border-gray-700 hover:text-gray-200'
            ]"
          >
            전체
          </button>

          <div class="flex items-center gap-2 ml-1 text-[11px] text-gray-300">
            <span :class="filter === 'noChange' ? 'text-[#3A4F7A]' : 'text-gray-400'">
              변경 없음
            </span>

            <div
              class="w-10 h-4 bg-gray-700/40 rounded-full flex items-center cursor-pointer relative transition border border-gray-600"
              @click="toggleChangeFilter"
            >
              <div
                class="absolute top-[1px] w-3 h-3 rounded-full transition-all"
                :style="{
                  left: filter === 'changed' ? '1.2rem' : '0.2rem',
                  backgroundColor: filter === 'changed' ? '#FDFF78' : '#3A4F7A'
                }"
              ></div>
            </div>

            <span :class="filter === 'changed' ? 'text-[#FDFF78]' : 'text-gray-400'">
              변경 있음
            </span>
          </div>
        </div>

        <!-- LIST -->
        <div class="flex-1 overflow-y-auto space-y-4 custom-scrollbar">
          <div
              v-for="item in filteredArticles"
              :key="item.id"
              @click="selectArticle(item)"
              :class="betterItemClass(item)"
          >
              <!-- 왼쪽 색상바 -->
              <div
                class="absolute left-0 top-0 h-full w-[3px] rounded-l-lg"
                :style="{ backgroundColor: leftBarColor(item) }"
              ></div>

              <div class="pl-4 flex flex-col">

                <!-- 제목 -->
                <h4 class="text-[14px] font-semibold text-gray-100 leading-tight">
                    {{ item.title }}
                </h4>

                <!-- 신뢰도 텍스트 -->
                <div class="mt-2">
                  <span
                    class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border backdrop-blur-md"
                    :class="confidenceBadgeClass(item.reviewLevel)"
                  >
                    신뢰도 · {{ reviewLevelText(item.reviewLevel) }}
                  </span>
                </div>
              </div> <!-- ← pl-4 flex flex-col 닫기 -->

          </div> <!-- ← v-for 아이템 닫기 -->
        </div> <!-- ← LIST 컨테이너 닫기 -->
      </div> 
      
      <!-- RIGHT -->
      <AiReportPanel
        class="lg:col-span-8"
        :selectedArticle="selectedArticle"
        :aiReports="aiReports"
        :countryCode="countryCode"
      />

    </div>

  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AiReportPanel from "../components/regulation/AiReportPanel.vue";

const route = useRoute();
const router = useRouter();

const countryCode = ref(route.params.countryCode?.toUpperCase() ?? "US");
const fileId = ref(Number(route.params.fileId));  // ⭐ ref로 변경

const isFileOpen = ref(false);
const toggleFileList = () => (isFileOpen.value = !isFileOpen.value);

const documentInfo = ref({});
const articles = ref([]);
const aiReports = ref({});
const files = ref([]);

const selectedFileTitle = ref("");  // ⭐ 현재 파일 제목 표시용

const flagUrl = computed(() =>
  new URL(`../assets/flags/${countryCode.value}.png`, import.meta.url).href
);

async function loadData() {
  const module = await import(`@/data/regulations/${countryCode.value}.json`);
  const data = module.default;

  files.value = data.files;

  const selectedFile = files.value.find(f => f.id === fileId.value);

  if (selectedFile) {
    selectedFileTitle.value = selectedFile.title;  // ⭐ header에 파일명 반영
    documentInfo.value = selectedFile.documentInfo;
    articles.value = selectedFile.articles;
    aiReports.value = selectedFile.aiReports;
  }
}

loadData();

const impactLabel = (lvl) =>
  lvl === 1 ? "Low" : lvl === 2 ? "Medium" : "High";

const impactBadgeStyle = (lvl) => {
  if (lvl === 1) return { backgroundColor: "#3A4F7A40", color: "#9FB7D9" };
  if (lvl === 2) return { backgroundColor: "#FDFF7840", color: "#FDFF78" };
  return { backgroundColor: "#FF5C5C40", color: "#FF5C5C" };
};

/* ⭐ 파일 변경 감지 */
watch(
  () => route.params.fileId,
  (newId) => {
    fileId.value = Number(newId);
    loadData();
  }
);

/* ⭐ 국가 변경 감지 */
watch(
  () => route.params.countryCode,
  (newCode) => {
    if (!newCode) return;
    countryCode.value = newCode.toUpperCase();
    loadData();
  }
);

function goToFile(id) {
  router.push({
    name: "RegulationDetail",
    params: { countryCode: countryCode.value, fileId: id }
  });
  isFileOpen.value = false;
}

/* 필터 로직 동일 */
const filter = ref("all");
const setFilter = (v) => (filter.value = v);
const toggleChangeFilter = () =>
  (filter.value = filter.value === "changed" ? "noChange" : "changed");

const filteredArticles = computed(() => {
  if (filter.value === "changed") return articles.value.filter(a => a.hasChange);
  if (filter.value === "noChange") return articles.value.filter(a => !a.hasChange);
  return articles.value;
});

const selectedArticle = ref(null);
const selectArticle = (item) => (selectedArticle.value = item);

// Left bar + level guide 색상
const reviewToColor = (lvl) => {
  if (lvl === 3) return "#C084FC";   // 높음 High
  if (lvl === 2) return "#5DE2C0";   // 보통 Mid
  return "#a7b7b2";                  // 낮음 Low (업데이트)
};

const leftBarColor = (item) => {
  return item.hasChange ? "#FDFF78" : "#3A4F7A";
};

// 카드 하단에 표시할 한국어 문구
const reviewLevelText = (lvl) => {
  if (lvl === 3) return "높음";
  if (lvl === 2) return "보통";
  return "낮음";
};

const betterItemClass = (item) => [
  "relative p-4 rounded-lg cursor-pointer transition-all border border-gray-800 bg-[#0F1828]",
  "hover:bg-[#152033] hover:border-gray-600 hover:shadow-md",
  selectedArticle.value?.id === item.id ? "bg-[#152033] border-gray-600 shadow-md" : ""
];

const confidenceBadgeClass = (level) => {
  switch (level) {
    case 3:
      return "bg-green-400/10 text-green-300 border-green-400/30";
    case 2:
      return "bg-yellow-400/10 text-yellow-300 border-yellow-400/30";
    case 1:
      return "bg-red-400/10 text-red-300 border-red-400/30";
    default:
      return "bg-gray-400/10 text-gray-300 border-gray-400/30";
  }
}
</script>

<style>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgba(255, 255, 255, 0.15);
  border-radius: 8px;
}
</style>
