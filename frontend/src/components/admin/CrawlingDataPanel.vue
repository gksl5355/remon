<script setup>
import AddCrawlingModal from "@/components/admin/AddCrawlingModal.vue";
import { computed, ref, onMounted } from "vue";
import axios from 'axios';

/* API 설정 */
const API_BASE_URL = `http://localhost:8081/api/crawl`;

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

const localApi = {
  getTargets: () => apiClient.get('/targets'),
  addTarget: (data) => apiClient.post('/targets', data),
  updateTarget: (id, data) => apiClient.patch(`/targets/${id}`, data),
  deleteTarget: (id) => apiClient.delete(`/targets/${id}`),
  updateStatus: (id, enabled) => apiClient.patch(`/targets/${id}/status`, null, { params: { enabled } }),
  runBatchCrawling: () => apiClient.post('/run-batch/versioning')
};

/* STATE */
const crawlList = ref([]);
const loading = ref(false);
const errorMsg = ref(null);

const countries = ["US", "RU", "ID"];
const view = ref("all");
const filterCountry = ref("");

/* 데이터 로딩 */
const fetchTargets = async () => {
  loading.value = true;
  errorMsg.value = null;
  try {
    const response = await localApi.getTargets();
    if (Array.isArray(response.data)) {
      crawlList.value = response.data;
    } else {
      crawlList.value = [];
    }
  } catch (error) {
    console.error("데이터 로딩 실패:", error);
    errorMsg.value = "서버 연결 실패";
  } finally {
    loading.value = false;
  }
};

onMounted(() => { fetchTargets(); });

/* 필터링 및 정렬 */
const filteredList = computed(() => {
  if (!crawlList.value) return [];
  
  // 1. 필터링
  const list = crawlList.value.filter(i => {
    const itemType = i.type || i.category; 
    if (view.value !== "all") {
      if (view.value === "reg" && itemType !== "regulation" && itemType !== "reg") return false;
      if (view.value === "news" && itemType !== "news") return false;
    }
    
    // [수정] 국가 필터: Country 이름이 아니라 Code(US, KR 등)로 비교
    if (filterCountry.value && i.code !== filterCountry.value) return false;
    
    return true;
  });

  // 2. 정렬 (활성화된 것이 위로 오게)
  return list.sort((a, b) => Number(b.enabled) - Number(a.enabled));
});

/* 모달 */
const showAddModal = ref(false);
const editingItem = ref(null);

function openAddModal() {
  editingItem.value = null;
  showAddModal.value = true;
}

function editCrawling(item) {
  const safeItem = JSON.parse(JSON.stringify(item));
  
  safeItem.domain = item.domain || item.targetDomain || "";
  safeItem.format = item.format || item.documentFormat || "";
  safeItem.date = item.date || item.baseDate || "";
  
  if (!safeItem.type && safeItem.category) {
    safeItem.type = safeItem.category === 'regulation' ? 'reg' : 'news';
  }

  editingItem.value = safeItem;
  showAddModal.value = true;
}

function closeModal() {
  showAddModal.value = false;
  editingItem.value = null;
}

/* 액션 */
async function saveCrawling(data) {
  try {
    if (data.type === 'reg') data.category = 'regulation';
    if (data.type === 'news') data.category = 'news';

    if (editingItem.value) {
      await localApi.updateTarget(data.id, data);
      alert("수정되었습니다.");
    } else {
      await localApi.addTarget(data);
      alert("추가되었습니다.");
    }
    await fetchTargets();
    closeModal();
  } catch (error) {
    alert("저장 실패");
  }
}

async function deleteItem(id) {
  if (!confirm("삭제하시겠습니까?")) return;
  try {
    await localApi.deleteTarget(id);
    await fetchTargets();
  } catch (error) {
    alert("삭제 실패");
  }
}

async function handleStatusToggle(item) {
  try {
    const newStatus = !item.enabled;
    await localApi.updateStatus(item.id, newStatus);
    item.enabled = newStatus;
  } catch (e) {
    console.error(e);
  }
}

async function runCrawl() {
  if (!confirm("크롤링을 시작하시겠습니까?")) return;
  try {
    await localApi.runBatchCrawling();
    alert("🚀 크롤링 시작! 백엔드 로그 확인");
  } catch (error) {
    alert("요청 실패");
  }
}

const statusColor = type => (type === "news" ? "#88d0b3" : "#3A4F7A");
const toggleClass = (active, type) => {
  const isReg = type === "reg" || type === "regulation";
  let color = isReg ? "bg-[#3A4F7A] text-white" : type === "news" ? "bg-[#88d0b3] text-black" : "bg-gray-200 text-black";
  return ["px-4 py-1 text-xs font-medium rounded-full cursor-pointer transition", active ? color + " shadow" : "text-gray-400 hover:text-gray-200"];
};
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 flex items-center justify-center rounded-lg bg-gradient-to-br from-[#2A3953] to-[#1B2535] border border-white/10">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="#88d0b3" class="w-5 h-5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6m0 0l3 3m-3-3l-3 3m8-9h2a2 2 0 012 2v8a2 2 0 01-2 2h-2m-8-12H6a2 2 0 00-2 2v8a2 2 0 002 2h2"/>
          </svg>
        </div>
        <div>
          <h2 class="text-[16px] font-semibold tracking-wide text-gray-200">CRAWLING DATA MANAGEMENT</h2>
          <p class="text-xs text-gray-500 mt-0.5">Automated Scraping Jobs · Keywords</p>
        </div>
      </div>
      <!-- <button @click="runCrawl" class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-bold transition shadow-lg">🚀 Run Crawler</button> -->
    </div>

    <!-- Filter Bar -->
    <div class="flex flex-wrap items-center gap-4 mb-5">
      <div class="flex items-center bg-[#111A28] border border-gray-700 rounded-full px-1 py-0.5 select-none">
        <div @click="view = 'all'" :class="toggleClass(view === 'all', 'all')">All</div>
        <div @click="view = 'reg'" :class="toggleClass(view === 'reg', 'reg')">Regulation</div>
        <div @click="view = 'news'" :class="toggleClass(view === 'news', 'news')">News</div>
      </div>
      
      <!-- 국가 필터 (Select) -->
      <select v-model="filterCountry" class="filter-select text-gray-300 w-32 cursor-pointer">
        <option value="">국가 전체</option>
        <option v-for="c in countries" :key="c" :value="c">{{ c }}</option>
      </select>

      <button class="ml-auto px-3 py-1.5 rounded-md text-xs font-medium border border-white/20 bg-white/5 text-gray-200 hover:bg-white/10 transition flex items-center gap-1" @click="openAddModal">
        <span class="text-lg leading-none">+</span> Add
      </button>
    </div>

    <!-- LIST AREA -->
    <div class="flex-1 overflow-y-auto space-y-4 custom-scrollbar">
      <div v-if="errorMsg" class="p-4 bg-red-900/50 border border-red-500/50 rounded text-red-200 text-sm text-center mb-4">{{ errorMsg }}</div>
      <div v-if="loading" class="py-10 text-center text-gray-500">데이터를 불러오는 중입니다...</div>
      <div v-if="!loading && !errorMsg && filteredList.length === 0" class="py-10 text-center text-gray-500">등록된 타겟이 없습니다.</div>

      <div v-for="item in filteredList" :key="item.id" class="group relative p-4 rounded-lg cursor-pointer transition-all border border-gray-800 bg-[#0F1828] hover:bg-[#152033] hover:border-gray-600 hover:shadow-md">
        <div class="absolute left-0 top-0 h-full w-[3px] rounded-l-lg" :style="{ backgroundColor: statusColor(item.type || item.category) }" />

        <div class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition flex gap-2">
          <button class="p-1.5 rounded-md bg-white/10 hover:bg-white/20 transition" @click.stop="editCrawling(item)">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-gray-200" fill="none" viewBox="0 0 24 24" stroke-width="1.6" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M16.862 3.487l3.651 3.65-10.06 10.061L6.8 13.55l10.062-10.062zM5 19h14"/></svg>
          </button>
          <button class="p-1.5 rounded-md bg-white/10 hover:bg-white/20 transition" @click.stop="deleteItem(item.id)">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-gray-200" fill="none" viewBox="0 0 24 24" stroke-width="1.6" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 7h12M10 11v6m4-6v6M9 7V4h6v3m2 0v13H7V7h10z" /></svg>
          </button>
        </div>

        <div class="pl-4">
          <div class="flex items-center gap-3">
            <div 
              @click.stop="handleStatusToggle(item)"
              class="relative w-5 h-5 rounded border border-gray-600 flex items-center justify-center cursor-pointer hover:border-gray-400"
              :class="item.enabled ? 'bg-green-600 border-green-600' : 'bg-transparent'"
            >
              <svg v-if="item.enabled" xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 text-white" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
              </svg>
            </div>

            <h4 class="text-[14px] font-semibold flex items-center gap-2" :class="item.enabled ? 'text-gray-100' : 'text-gray-500 line-through'">
              {{ item.title || item.country + ' Crawler' }} 
              <span v-if="item.domain || item.targetDomain" class="text-xs font-normal text-gray-500 no-underline">
                ({{ item.domain || item.targetDomain }})
              </span>
            </h4>
          </div>
          
          <div class="text-xs text-gray-500 mt-1 ml-8">
             <span class="text-blue-300 font-medium">{{ item.country }}</span>
             <span v-if="item.code && item.code !== item.country"> ({{ item.code }})</span>
             <span class="mx-1">|</span>
             {{ item.typeLabel || item.category }} 
             <span v-if="item.date || item.baseDate"> | After: {{ item.date || item.baseDate }}</span>
             <span v-if="item.format || item.documentFormat"> | {{ item.format || item.documentFormat }}</span>
          </div>

          <div class="flex flex-wrap gap-2 mt-3 ml-8">
            <span v-for="k in item.keywords" :key="k" class="px-2 py-0.5 text-[11px] rounded-md bg-white/10 border border-white/10 text-gray-200">
              #{{ k }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <AddCrawlingModal
      v-if="showAddModal"
      :mode="editingItem ? 'edit' : 'add'"
      :initialData="editingItem"
      @close="closeModal"
      @save="saveCrawling"
    />
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background-color: rgba(255, 255, 255, 0.15); border-radius: 8px; }
.filter-select { background: #111A28; border: 1px solid #374155; padding: 6px 10px; border-radius: 6px; color: #d0d8e6; font-size: 12px; outline: none; }
.filter-select:focus { border-color: #5b6b85; }
</style>