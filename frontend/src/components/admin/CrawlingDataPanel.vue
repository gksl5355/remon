<template>
  <div class="flex flex-col h-full">

    <!-- =============================== -->
    <!-- HEADER -->
    <!-- =============================== -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">

        <!-- Icon -->
        <div
          class="w-9 h-9 flex items-center justify-center rounded-lg
                 bg-gradient-to-br from-[#2A3953] to-[#1B2535] border border-white/10"
        >
          <svg xmlns="http://www.w3.org/2000/svg" 
               fill="none" viewBox="0 0 24 24" stroke-width="1.5"
               stroke="#88d0b3" class="w-5 h-5">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M12 6v6m0 0l3 3m-3-3l-3 3m8-9h2a2 2 0 012 2v8a2 2 0 01-2 2h-2m-8-12H6a2 2 0 00-2 2v8a2 2 0 002 2h2"/>
          </svg>
        </div>

        <!-- Title -->
        <div>
          <h2 class="text-[16px] font-semibold tracking-wide text-gray-200">
            CRAWLING DATA MANAGEMENT
          </h2>
          <p class="text-xs text-gray-500 mt-0.5">
            Automated Scraping Jobs · Keywords
          </p>
        </div>

      </div>
    </div>


    <!-- =============================== -->
    <!-- FILTER BAR -->
    <!-- =============================== -->
    <div class="flex flex-wrap items-center gap-4 mb-5">

      <!-- Toggle -->
      <div class="flex items-center bg-[#111A28] border border-gray-700 rounded-full px-1 py-0.5 select-none">
        <div @click="view = 'all'" :class="toggleClass(view === 'all', 'all')">All</div>
        <div @click="view = 'reg'" :class="toggleClass(view === 'reg', 'reg')">Regulation</div>
        <div @click="view = 'news'" :class="toggleClass(view === 'news', 'news')">News</div>
      </div>

      <!-- Country Filter -->
      <select v-model="filterCountry" class="filter-select">
        <option value="">국가 전체</option>
        <option v-for="c in countries" :key="c">{{ c }}</option>
      </select>

      <!-- Add Button -->
      <button
        class="ml-auto px-3 py-1.5 rounded-md text-xs font-medium border border-white/20
               bg-white/5 text-gray-200 hover:bg-white/10 transition flex items-center gap-1"
        @click="openAddModal"
      >
        <span class="text-lg leading-none">+</span> Add
      </button>

    </div>


    <!-- =============================== -->
    <!-- LIST -->
    <!-- =============================== -->
    <div class="flex-1 overflow-y-auto space-y-4 custom-scrollbar">

      <div
        v-for="item in filteredList"
        :key="item.id"
        class="group relative p-4 rounded-lg cursor-pointer transition-all 
               border border-gray-800 bg-[#0F1828]
               hover:bg-[#152033] hover:border-gray-600 hover:shadow-md"
      >

        <!-- State bar -->
        <div
          class="absolute left-0 top-0 h-full w-[3px] rounded-l-lg"
          :style="{ backgroundColor: statusColor(item.type) }"
        />

        <!-- Hover actions -->
        <div class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition flex gap-2">

          <!-- Edit -->
          <button
            class="p-1.5 rounded-md bg-white/10 hover:bg-white/20 transition"
            @click.stop="editCrawling(item)"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-gray-200"
              fill="none" viewBox="0 0 24 24" stroke-width="1.6" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round"
                  d="M16.862 3.487l3.651 3.65-10.06 10.061L6.8 13.55l10.062-10.062zM5 19h14"/>
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
            {{ item.title }}
          </h4>

          <!-- Keywords -->
          <div class="flex flex-wrap gap-2 mt-3">
            <span
              v-for="k in item.keywords"
              :key="k"
              class="px-2 py-0.5 text-[11px] rounded-md bg-white/10 border border-white/10 text-gray-200"
            >
              #{{ k }}
            </span>
          </div>
        </div>

      </div>

      <div v-if="filteredList.length === 0" class="py-10 text-center text-gray-500">
        데이터가 없습니다.
      </div>

    </div>


    <!-- Add/Edit Modal -->
    <AddCrawlingModal
      v-if="showAddModal"
      :mode="editingItem ? 'edit' : 'add'"
      :initialData="editingItem"
      @close="closeModal"
      @save="saveCrawling"
    />

  </div>
</template>


<script setup>
import AddCrawlingModal from "@/components/admin/AddCrawlingModal.vue";
import { computed, ref } from "vue";

/* ================================
   SAMPLE DATA (확장된 구조)
================================ */
const crawlList = ref([
  {
    id: 1,
    title: "US Regulation Crawler",
    type: "reg",
    typeLabel: "Regulation",
    country: "US",
    keywords: ["CFR Title 27 Part 40", "tobacco", "manufacture"],

    domain: "govinfo.gov",
    format: "pdf",
    date: "2024-12-01",
    targetUrl: ""
  },
  {
    id: 2,
    title: "RU Regulation Crawler",
    type: "reg",
    typeLabel: "Regulation",
    country: "RU",
    keywords: ["packaging", "label"],

    domain: "www.gov.ru/reg",
    format: "",
    date: "",
    targetUrl: ""
  },
  {
    id: 3,
    title: "ID News Crawler",
    type: "news",
    typeLabel: "News",
    country: "ID",
    keywords: ["nicotine", "requirement"],

    domain: "www.idnews.id",
    format: "html",
    date: "",
    targetUrl: "https://idnews.id/latest"
  }
]);

const countries = ["US", "RU", "ID"];
const view = ref("all");
const filterCountry = ref("");

/* ===============================
   FILTERED LIST
=============================== */
const filteredList = computed(() =>
  crawlList.value.filter(i => {
    if (view.value !== "all" && i.type !== view.value) return false;
    if (filterCountry.value && i.country !== filterCountry.value) return false;
    return true;
  })
);

/* ===============================
   MODALS
=============================== */
const showAddModal = ref(false);
const editingItem = ref(null);

function openAddModal() {
  editingItem.value = null;      // ADD MODE INITIALIZE
  showAddModal.value = true;
}

function editCrawling(item) {
  editingItem.value = { ...item }; // COPY FOR EDIT MODE
  showAddModal.value = true;
}

/* ===============================
   SAVE CRAWLING
=============================== */
function saveCrawling(data) {
  const typeLabel = data.type === "reg" ? "Regulation" : "News";
  data.title = `${data.country} ${typeLabel} Crawler`;

  if (editingItem.value) {
    const idx = crawlList.value.findIndex(i => i.id === data.id);
    if (idx !== -1) {
      crawlList.value[idx] = { ...crawlList.value[idx], ...data };
    }
  } else {
    const newItem = {
      id: Date.now(),
      title: data.title,
      type: data.type,
      typeLabel,
      country: data.country,
      keywords: [...data.keywords],
      domain: data.domain,
      format: data.format,
      date: data.date,
      targetUrl: data.targetUrl,
    };

    crawlList.value.push(newItem);
  }

  closeModal();
}

function deleteItem(id) {
  crawlList.value = crawlList.value.filter(i => i.id !== id);
}

function closeModal() {
  showAddModal.value = false;
  editingItem.value = null;
}

/* ===============================
   UI HELPERS
=============================== */
const statusColor = type => (type === "news" ? "#88d0b3" : "#3A4F7A");

const toggleClass = (active, type) => {
  let color =
    type === "reg"
      ? "bg-[#3A4F7A] text-white"
      : type === "news"
      ? "bg-[#88d0b3] text-black"
      : "bg-gray-200 text-black";

  return [
    "px-4 py-1 text-xs font-medium rounded-full cursor-pointer transition",
    active ? color + " shadow" : "text-gray-400 hover:text-gray-200"
  ];
};
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
