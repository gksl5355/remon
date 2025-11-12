<template>
  <div
    class="bg-[#111] border border-[#2b2b2b] rounded-2xl p-6 shadow-md flex flex-col h-[480px] relative"
  >
    <!-- 🔹 제목 영역 -->
    <div class="flex justify-between items-center mb-5 relative">
      <div>
        <h2 class="text-lg text-[#D4AF37] tracking-wide font-medium">
          REGULATION FILE
        </h2>
        <p class="text-xs text-gray-500 mt-1">국가 및 제품별 규제 파일 관리</p>
      </div>

      <!-- 🔹 버튼 -->
      <div class="flex items-center gap-3">
        <!-- 필터 버튼 -->
        <button
          class="text-[#E8C663] hover:text-[#FFD56A] transition"
          @click.stop="toggleFilter"
          title="필터 열기"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none"
            viewBox="0 0 24 24" stroke-width="1.6" stroke="currentColor"
            class="w-5 h-5">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M3 4.5h18m-9 7.5h9m-6 7.5h6" />
          </svg>
        </button>

        <!-- 업로드 버튼 -->
        <button
          class="text-[#E8C663] hover:text-[#FFD56A] transition"
          @click="openUploadModal"
          title="파일 업로드"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none"
            viewBox="0 0 24 24" stroke-width="1.6" stroke="currentColor"
            class="w-5 h-5">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>

      <!-- 🔸 필터 팝업 -->
      <transition name="fade">
        <div v-if="showFilter" ref="filterPopup"
          class="absolute right-0 top-10 bg-[#1b1b1b] border border-[#333] rounded-lg p-4 text-xs w-[260px] z-50 shadow-xl">
          <h3 class="text-[#D4AF37] font-semibold mb-2">필터 설정</h3>

          <div class="flex flex-col mb-3">
            <label class="text-[#a99d7b] mb-1">국가 선택</label>
            <select v-model="filterCountry"
              class="bg-[#111] text-gray-200 border border-[#333] rounded-md px-2 py-1 focus:outline-none focus:border-[#D4AF37]">
              <option value="">전체</option>
              <option v-for="c in countries" :key="c">{{ c }}</option>
            </select>
          </div>

          <div class="flex flex-col mb-3">
            <label class="text-[#a99d7b] mb-1">파일명 검색</label>
            <input v-model="filterName" type="text" placeholder="예: Tobacco_Label"
              class="bg-[#111] text-gray-200 border border-[#333] rounded-md px-2 py-1 focus:outline-none focus:border-[#D4AF37]" />
          </div>

          <div class="flex justify-end gap-2 mt-3">
            <button
              class="px-2 py-1 bg-[#D4AF37] text-black rounded-md text-[11px] hover:bg-[#f0d86b]"
              @click="applyFilter">적용</button>
            <button
              class="px-2 py-1 bg-[#444] text-gray-300 rounded-md text-[11px] hover:bg-[#555]"
              @click="resetFilter">해제</button>
          </div>
        </div>
      </transition>
    </div>

    <!-- 🔹 테이블 -->
    <div class="flex-1 overflow-y-auto border-t border-[#222]">
      <table class="w-full text-xs border-collapse">
        <thead
          class="bg-[#111]/95 sticky top-0 z-[40] text-gray-400 border-b border-[#333]">
          <tr>
            <th class="py-2 text-left w-[10%] font-normal">국가</th>
            <th class="py-2 text-left font-normal">파일명</th>
            <th class="py-2 text-left w-[20%] font-normal">업로드일자</th>
            <th class="py-2 text-center w-[15%] font-normal">관리</th>
          </tr>
        </thead>

        <tbody>
          <tr
            v-for="file in filteredFiles"
            :key="file.id"
            class="border-b border-[#1e1e1e] hover:bg-[#1c1c1c] transition"
          >
            <td class="py-2 pl-2">{{ file.country }}</td>
            <td class="py-2 truncate max-w-[280px]">{{ file.name }}</td>
            <td class="py-2">{{ file.upload_date }}</td>
            <td class="py-2 text-center flex justify-center gap-4">
              <!-- 다운로드 버튼 -->
              <button
                class="text-[#E8C663] hover:text-[#FFD56A] transition"
                title="다운로드"
                @click="openDownloadOptions(file.id)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none"
                  viewBox="0 0 24 24" stroke-width="1.6" stroke="currentColor"
                  class="w-4 h-4">
                  <path stroke-linecap="round" stroke-linejoin="round"
                    d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-9-9v9m0 0l3.75-3.75M12 16.5L8.25 12.75" />
                </svg>
              </button>

              <!-- 삭제 버튼 -->
              <button
                class="text-red-400 hover:text-red-300 transition"
                title="삭제"
                @click="deleteFile(file.id)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none"
                  viewBox="0 0 24 24" stroke-width="1.6" stroke="currentColor"
                  class="w-4 h-4">
                  <path stroke-linecap="round" stroke-linejoin="round"
                    d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </td>
          </tr>

          <tr v-if="filteredFiles.length === 0">
            <td colspan="4" class="text-center text-gray-500 py-4">
              조건에 맞는 파일이 없습니다.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 🪟 업로드 모달 -->
    <transition name="fade">
      <div
        v-if="showUploadModal"
        class="fixed inset-0 bg-black/60 flex items-center justify-center z-[100]"
        @click.self="closeUploadModal"
      >
        <div
          class="bg-[#1b1b1b] border border-[#333] rounded-2xl p-6 w-[400px] text-sm shadow-2xl"
        >
          <h3 class="text-[#E8C663] font-semibold mb-4">새 파일 업로드</h3>

          <div class="flex flex-col gap-3">
            <div>
              <label class="block text-xs text-gray-400 mb-1">국가</label>
              <select
                v-model="uploadCountry"
                class="w-full bg-[#111] text-gray-200 border border-[#333] rounded-md px-3 py-2 focus:outline-none focus:border-[#E8C663]"
              >
                <option disabled value="">국가 선택</option>
                <option v-for="c in countries" :key="c">{{ c }}</option>
              </select>
            </div>

            <div>
              <label class="block text-xs text-gray-400 mb-1">파일</label>
              <input
                type="file"
                @change="onFileChange"
                class="w-full bg-[#111] text-gray-200 border border-[#333] rounded-md px-2 py-2 focus:outline-none focus:border-[#E8C663]"
              />
            </div>
          </div>

          <div class="flex justify-end gap-2 mt-5">
            <button
              class="px-3 py-1 bg-[#E8C663] text-black rounded-md text-xs hover:bg-[#f0d86b]"
              @click="uploadFile"
            >
              업로드
            </button>
            <button
              class="px-3 py-1 bg-[#444] text-gray-300 rounded-md text-xs hover:bg-[#555]"
              @click="closeUploadModal"
            >
              취소
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 🪟 다운로드 선택 모달 -->
    <transition name="fade">
      <div
        v-if="showDownloadOptions"
        class="fixed inset-0 bg-black/60 flex items-center justify-center z-[100]"
        @click.self="closeDownloadOptions"
      >
        <div
          class="bg-[#1b1b1b] border border-[#333] rounded-2xl p-6 w-[320px] text-sm shadow-2xl text-center"
        >
          <h3 class="text-[#E8C663] font-semibold mb-4">다운로드 선택</h3>
          <p class="text-gray-400 mb-4">다운로드할 파일 종류를 선택하세요.</p>

          <div class="flex flex-col gap-3">
            <button
              class="px-3 py-2 bg-[#E8C663] text-black rounded-md text-xs hover:bg-[#f0d86b]"
              @click="downloadFile('pdf')"
            >
              원문 다운로드
            </button>
            <button
              class="px-3 py-2 bg-[#655835] text-white rounded-md text-xs hover:bg-[#aaa]"
              @click="downloadFile('translated')"
            >
              번역본 다운로드
            </button>
          </div>

          <button
            class="mt-5 text-gray-400 text-xs hover:text-gray-200"
            @click="closeDownloadOptions"
          >
            닫기
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import api from "@/services/api.js";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

const files = ref([]);
const filterCountry = ref("");
const filterName = ref("");
const countries = ["KR", "US", "JP", "CN", "EU"];
const showFilter = ref(false);
const showUploadModal = ref(false);
const showDownloadOptions = ref(false);
const selectedFileId = ref(null);
const uploadFileObj = ref(null);
const uploadCountry = ref("");
const filterPopup = ref(null);

// ✅ 실시간 필터링
const filteredFiles = computed(() =>
  files.value.filter((f) => {
    const byCountry = filterCountry.value
      ? f.country === filterCountry.value
      : true;
    const byName = filterName.value
      ? f.name.toLowerCase().includes(filterName.value.toLowerCase())
      : true;
    return byCountry && byName;
  })
);

// ✅ 파일 목록
const fetchFiles = async () => {
  try {
    const res = await api.get("/admin/regulations");
    files.value = res.data;
  } catch (err) {
    console.error("❌ 파일 목록 불러오기 실패:", err);
  }
};

// ✅ 다운로드 옵션 열기
const openDownloadOptions = (id) => {
  selectedFileId.value = id;
  showDownloadOptions.value = true;
};
const closeDownloadOptions = () => {
  showDownloadOptions.value = false;
  selectedFileId.value = null;
};

// ✅ 다운로드 실행
const downloadFile = (type) => {
  const id = selectedFileId.value;
  if (!id) return;
  const url =
    type === "translated"
      ? `http://localhost:8000/api/admin/regulations/${id}/download/translated`
      : `http://localhost:8000/api/admin/regulations/${id}/download/pdf`;
  window.open(url, "_blank");
  closeDownloadOptions();
};

// ✅ 파일 삭제
const deleteFile = async (id) => {
  if (!confirm("이 파일을 삭제하시겠습니까?")) return;
  try {
    await api.delete(`/admin/regulations/${id}`);
    await fetchFiles();
  } catch (err) {
    console.error("❌ 파일 삭제 실패:", err);
  }
};

// ✅ 업로드 관련
const onFileChange = (e) => (uploadFileObj.value = e.target.files[0]);
const openUploadModal = () => (showUploadModal.value = true);
const closeUploadModal = () => {
  showUploadModal.value = false;
  uploadFileObj.value = null;
  uploadCountry.value = "";
};
const uploadFile = async () => {
  if (!uploadFileObj.value || !uploadCountry.value) {
    alert("파일과 국가를 모두 선택하세요.");
    return;
  }
  const formData = new FormData();
  formData.append("file", uploadFileObj.value);
  formData.append("country", uploadCountry.value);

  try {
    await api.post("/admin/regulations/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    closeUploadModal();
    await fetchFiles();
  } catch (err) {
    console.error("❌ 파일 업로드 실패:", err);
  }
};

// ✅ 필터
const toggleFilter = () => (showFilter.value = !showFilter.value);
const applyFilter = () => (showFilter.value = false);
const resetFilter = () => {
  filterCountry.value = "";
  filterName.value = "";
  showFilter.value = false;
};

// ✅ 외부 클릭 시 필터 닫기
const handleClickOutside = (e) => {
  if (
    showFilter.value &&
    filterPopup.value &&
    !filterPopup.value.contains(e.target) &&
    !e.target.closest("button")
  ) {
    showFilter.value = false;
  }
};

onMounted(() => {
  document.addEventListener("click", handleClickOutside);
  fetchFiles();
});
onBeforeUnmount(() => document.removeEventListener("click", handleClickOutside));
</script>

<style scoped>
@reference "tailwindcss";
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
