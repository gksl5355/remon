<template>
  <div class="p-10 min-h-screen bg-[#080D17] text-gray-200">

    <!-- HEADER -->
    <div class="flex items-center gap-4 mb-10">
      
      <!-- 국기와 국가코드 -->
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
        <h2 class="text-xl font-semibold text-gray-100">Regulation Dashboard</h2>

        <div class="text-sm text-gray-400 flex flex-wrap gap-x-5">
          <span>수집 시각: <span class="text-gray-300">{{ collectedTime }}</span></span>
        </div>
      </div>

    </div>

      <!-- FILE LIST -->
      <div class="space-y-4 mt-6">

        <div
          v-for="(file, idx) in files"
          :key="idx"
          class="group p-5 rounded-xl border border-gray-700/40 
                bg-gradient-to-br from-[#0D1523]/70 to-[#111a28]/70
                hover:from-[#162033]/80 hover:to-[#1c2a3d]/80
                shadow-sm hover:shadow-md transition-all cursor-pointer flex items-center justify-between"
          @click="goToDetail(file)"
        >

          <div class="flex items-start gap-4 ">

            <!-- FILE NUMBER -->
            <div
              class="w-10 h-10 rounded-full flex items-center justify-center
                    bg-[#182231] border border-gray-600/40 text-gray-300 text-sm font-semibold
                    group-hover:bg-[#223045] group-hover:text-white transition"
            >
              {{ idx + 1 }}
            </div>

            <!-- RIGHT CONTENT -->
            <div class="flex flex-col">

              <!-- ⭐ TITLE + IMPACT IN SAME ROW -->
              <div class="flex items-center gap-2">
                <h3 class="text-lg font-medium text-gray-100 group-hover:text-white transition">
                  {{ file.title }}
                </h3>

                <span
                  class="text-[10px] px-2 py-0.5 rounded-full font-medium"
                  :style="impactBadgeStyle(file.impactLevel)"
                >
                  {{ impactLabel(file.impactLevel) }}
                </span>
              </div>

              <div class="text-xs text-gray-400 flex gap-6 mt-2">
                <!-- <span>공포일: <span class="text-gray-300">{{ file.documentInfo.promulgationDate }}</span></span>
                <span>시행일: <span class="text-gray-300">{{ file.documentInfo.effectiveDate }}</span></span> -->
                <span>수집일자: <span class="text-gray-300">{{ formatDate(file.category) }}</span></span>
              </div>

            </div>

          </div>

          <div class="text-gray-500 group-hover:text-gray-200 transition">
            ➜
          </div>

        </div>

      </div>


    </div>

</template>

<script setup>
import api from "@/services/api.js";
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

const router = useRouter();
const route = useRoute();

const countryCode = route.params.countryCode;
const files = ref([]);
const collectedTime = ref("");

// 국기 URL
const flagUrl = computed(() =>
  new URL(`../assets/flags/${countryCode.toUpperCase()}.png`, import.meta.url).href
);

async function loadFiles() {
  try {
    const response = await api.get(`/regulations/country/${countryCode}`);
    files.value = response.data.files;
    collectedTime.value = response.data.collectedTime || "";
  } catch (error) {
    console.error("Failed to load regulations:", error);
    files.value = [];
    collectedTime.value = "";
  }
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hour = String(date.getHours()).padStart(2, '0');
  const minute = String(date.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day} ${hour}:${minute}`;
}

/* impact style */
const impactLabel = (lvl) =>
  lvl === 1 ? "Low" : lvl === 2 ? "Medium" : "High";

const impactBadgeStyle = (lvl) => {
  if (lvl === 1) return { backgroundColor: "#3A4F7A40", color: "#9FB7D9" };
  if (lvl === 2) return { backgroundColor: "#FDFF7840", color: "#FDFF78" };
  return { backgroundColor: "#FF5C5C40", color: "#FF5C5C" };
};

function goToDetail(file) {
  router.push({
    name: "RegulationDetail",
    params: { countryCode, fileId: file.id }
  });
}

onMounted(loadFiles);
</script>
