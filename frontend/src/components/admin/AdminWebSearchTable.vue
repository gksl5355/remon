<template>
  <div
    class="bg-[#111] border border-[#2b2b2b] rounded-2xl p-6 shadow-md flex flex-col h-[480px]"
  >
    <!-- 🔹 헤더 -->
    <div class="flex justify-between items-end mb-5 flex-shrink-0 relative">
      <div>
        <h2 class="text-lg text-[#D4AF37] tracking-wide">WEB SEARCH</h2>
        <p class="text-xs text-gray-500 mt-1">웹서치 데이터 관리</p>
      </div>

      <!-- URL 추가 버튼 -->
      <button
        class="text-[#E8C663] hover:text-[#FFD56A] transition"
        @click="openPopup"
        title="URL 추가"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          stroke-width="1.6"
          stroke="currentColor"
          class="w-5 h-5"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M12 4v16m8-8H4"
          />
        </svg>
      </button>
    </div>

    <!-- 🔹 테이블 -->
    <div class="flex-1 overflow-y-auto border-t border-[#222] scrollbar-thin">
      <table class="w-full text-xs border-collapse">
        <thead
          class="bg-[#111]/95 sticky top-0 z-[40] text-gray-400 border-b border-[#333]"
        >
          <tr>
            <th class="py-2 text-left">제목</th>
            <th class="py-2 text-left w-1/6">국가</th>
            <th class="py-2 text-left w-1/6">등록일</th>
            <th class="py-2 text-left w-1/3">URL</th>
            <th class="py-2 text-center w-1/12">관리</th>
          </tr>
        </thead>

        <tbody>
          <tr
            v-for="item in websearchList"
            :key="item.id"
            class="border-b border-[#1e1e1e] hover:bg-[#1c1c1c] transition"
          >
            <td class="py-2">{{ item.title }}</td>
            <td class="py-2">{{ item.country }}</td>
            <td class="py-2">{{ item.date }}</td>
            <td class="py-2 text-blue-400 truncate max-w-[250px]">
              <a
                :href="item.url"
                target="_blank"
                class="hover:underline"
              >{{ item.url }}</a>
            </td>
            <td class="py-2 text-center">
              <button
                class="text-red-400 hover:text-red-300 transition"
                @click="deleteItem(item.id)"
              >
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
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </td>
          </tr>

          <tr v-if="websearchList.length === 0">
            <td colspan="5" class="text-center text-gray-500 py-4">
              등록된 데이터가 없습니다.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 🪟 URL 등록 팝업 -->
    <transition name="fade">
      <div
        v-if="showPopup"
        class="fixed inset-0 bg-black/60 flex items-center justify-center z-[100]"
        @click.self="closePopup"
      >
        <div
          class="bg-[#1b1b1b] border border-[#333] rounded-2xl p-6 w-[400px] text-sm shadow-2xl"
        >
          <h3 class="text-[#E8C663] font-semibold mb-4">새 URL 등록</h3>

          <div class="flex flex-col gap-3">
            <div>
              <label class="block text-xs text-gray-400 mb-1">제목</label>
              <input
                v-model="newTitle"
                type="text"
                placeholder="제목 입력"
                class="w-full bg-[#111] text-gray-200 border border-[#333] rounded-md px-3 py-2 focus:outline-none focus:border-[#E8C663]"
              />
            </div>

            <div>
              <label class="block text-xs text-gray-400 mb-1">국가</label>
              <select
                v-model="newCountry"
                class="w-full bg-[#111] text-gray-200 border border-[#333] rounded-md px-3 py-2 focus:outline-none focus:border-[#E8C663]"
              >
                <option disabled value="">국가 선택</option>
                <option v-for="c in countries" :key="c">{{ c }}</option>
              </select>
            </div>

            <div>
              <label class="block text-xs text-gray-400 mb-1">URL</label>
              <input
                v-model="newUrl"
                type="text"
                placeholder="https://example.com"
                class="w-full bg-[#111] text-gray-200 border border-[#333] rounded-md px-3 py-2 focus:outline-none focus:border-[#E8C663]"
              />
            </div>
          </div>

          <div class="flex justify-end gap-2 mt-5">
            <button
              class="px-3 py-1 bg-[#E8C663] text-black rounded-md text-xs hover:bg-[#f0d86b]"
              @click="addItem"
            >
              등록
            </button>
            <button
              class="px-3 py-1 bg-[#444] text-gray-300 rounded-md text-xs hover:bg-[#555]"
              @click="closePopup"
            >
              취소
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import api from "@/services/api.js"; // ✅ axios 인스턴스 사용
import { onMounted, ref } from "vue";

const showPopup = ref(false);
const countries = ["KR", "US", "JP", "CN", "EU"];
const websearchList = ref([]);

const newTitle = ref("");
const newCountry = ref("");
const newUrl = ref("");

// ✅ 웹서치 목록 조회
const fetchWebSearch = async () => {
  try {
    const res = await api.get("/admin/websearch");
    websearchList.value = res.data;
  } catch (err) {
    console.error("❌ 웹서치 데이터 불러오기 실패:", err);
  }
};

onMounted(fetchWebSearch);

// ✅ 팝업 열기 / 닫기
const openPopup = () => (showPopup.value = true);
const closePopup = () => {
  showPopup.value = false;
  newTitle.value = "";
  newCountry.value = "";
  newUrl.value = "";
};

// ✅ 항목 등록
const addItem = async () => {
  if (!newTitle.value || !newCountry.value || !newUrl.value) {
    alert("모든 필드를 입력하세요.");
    return;
  }

  // ✅ URL 유효성 검사 (http:// 또는 https:// 로 시작해야 함)
  const urlPattern = /^(https?:\/\/)[\w.-]+(\.[\w.-]+)+[/#?]?.*$/;
  if (!urlPattern.test(newUrl.value)) {
    alert("올바른 URL 형식이 아닙니다.\n예: https://example.com");
    return;
  }

  try {
    await api.post("/admin/websearch", {
      title: newTitle.value,
      country: newCountry.value,
      url: newUrl.value,
    });
    closePopup();
    await fetchWebSearch();
  } catch (err) {
    console.error("❌ 등록 실패:", err);
  }
};

// ✅ 항목 삭제
const deleteItem = async (id) => {
  if (!confirm("이 데이터를 삭제하시겠습니까?")) return;

  try {
    await api.delete(`/admin/websearch/${id}`);
    await fetchWebSearch();
  } catch (err) {
    console.error("❌ 삭제 실패:", err);
  }
};
</script>

<style scoped>
.scrollbar-thin::-webkit-scrollbar {
  width: 6px;
}
.scrollbar-thin::-webkit-scrollbar-thumb {
  background-color: #333;
  border-radius: 10px;
}
.scrollbar-thin::-webkit-scrollbar-track {
  background: transparent;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
