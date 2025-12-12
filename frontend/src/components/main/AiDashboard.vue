<template>
  <div
    class="w-full h-full flex flex-col gap-4 overflow-hidden transition-all duration-300"
    :class="isDark ? 'bg-transparent text-gray-200' : 'bg-white/70 text-gray-800'"
  >
    <div class="flex flex-1 gap-4 min-h-0 overflow-hidden">

      <!-- =============================== -->
      <!--      LEFT : REGULATION CHART    -->
      <!-- =============================== -->
      <div class="flex-[2] min-w-0 p-4 overflow-visible">

        <!-- Country Filter -->
        <div class="w-full flex justify-between items-center mb-2 px-1">

          <div class="h-5"></div>

          <div
            class="rounded-full px-2 py-1 flex gap-1 backdrop-blur-md border transition-all"
            :class="isDark
              ? 'bg-white/10 border-white/10'
              : 'bg-white border border-gray-300 shadow-sm'
            "
          >
            <button
              v-for="code in countryList"
              :key="code"
              @click="selectedCountry = code"
              :class="[
                'px-3 py-1 text-xs rounded-full transition-all',
                selectedCountry === code
                  ? (isDark
                      ? 'bg-[#FDFF78] text-black font-semibold shadow'
                      : 'bg-[#2C2C54] text-white font-semibold shadow')
                  : (isDark
                      ? 'text-gray-200 hover:bg-white/5'
                      : 'text-gray-600 hover:bg-gray-200')
              ]"
            >
              {{ code }}
            </button>
          </div>
        </div>

        <!-- Chart Box -->
        <div
          class="w-full h-[20vh] transition-all duration-300 rounded-xl"
          :class="isDark
            ? 'bg-transparent'
            : 'bg-white border border-gray-200 shadow-[0_4px_18px_rgba(0,0,0,0.06)] p-2'
          "
        >
          <v-chart :option="regulationOption" autoresize class="w-full h-full" />
        </div>
      </div>

      <!-- =============================== -->
      <!--          RIGHT : SUMMARY        -->
      <!-- =============================== -->
      <div
        class="flex-[1] summary-card p-6 space-y-4 overflow-hidden h-[25vh] transition-all duration-300"
        :class="isDark
          ? 'bg-white/5 border-white/15 text-gray-200'
          : 'bg-white border border-gray-200 shadow-[0_4px_18px_rgba(0,0,0,0.06)] text-gray-900 rounded-xl'
        "
      >

        <!-- Title + Button -->
        <div class="flex items-center justify-between">
          <h3
            class="text-base font-semibold tracking-wide transition-all"
            :class="isDark ? 'text-[#FDFF78]' : 'text-gray-900'"
          >
            AI SUMMARY
          </h3>

          <button
            @click="handleUpdateClick"
            class="update-btn text-[11px] px-3 py-1 rounded-md border transition flex items-center gap-1"
            :class="[
              isDark
                ? 'bg-white/10 border-white/20 hover:bg-white/20 text-gray-200'
                : 'bg-gray-100 border-gray-300 hover:bg-gray-200 text-gray-800',
              isUpdating ? 'opacity-70 scale-95 pointer-events-none' : ''
            ]"
            :disabled="isUpdating"
          >
            <span v-if="!isUpdating && !updateDone">Update</span>
            <span v-if="isUpdating" class="loader"></span>

            <span v-if="updateDone && !isUpdating">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                stroke="#FDFF78" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </span>
          </button>
        </div>

        <!-- Updated Time -->
        <div
          class="border-t pt-3"
          :class="isDark ? 'border-white/10' : 'border-gray-300'"
        >
          <p :class="isDark ? 'text-gray-400' : 'text-gray-600'" class="text-xs">
            업데이트: {{ lastUpdated }}
          </p>
        </div>

        <!-- Summary Content -->
        <div class="space-y-2 text-sm leading-relaxed">
          <p>{{ text }}</p>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue";
import VChart from "vue-echarts";

const isDark = inject("isDark");

/* ------------------------------
      SUMMARY (타이핑 효과)
------------------------------ */
const summaryList = [
  { text: "최근 7일간 규제 변화는 중간 수준을 유지하고 있습니다. 대부분의 지역에서 변동 강도는 안정적이며 큰 변동은 확인되지 않았습니다." },
  { text: "지난 주 대비 규제 변경 추세가 감소했습니다. 주요 요인은 특정 국가의 규제 완화 조치입니다." }
];

const summaryIndex = ref(0);
const lastUpdated = ref(formatDate());
const text = ref("");

function formatDate() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")} ` +
         `${String(now.getHours()).padStart(2,"0")}:${String(now.getMinutes()).padStart(2,"0")}`;
}

async function typeText(target, full, speed = 22) {
  target.value = "";
  for (let i = 0; i < full.length; i++) {
    target.value += full[i];
    await new Promise((r) => setTimeout(r, speed));
  }
}

async function updateSummary() {
  summaryIndex.value = summaryIndex.value === 0 ? 1 : 0;
  lastUpdated.value = formatDate();
  await typeText(text, summaryList[summaryIndex.value].text);
}

onMounted(() => typeText(text, summaryList[0].text));

const isUpdating = ref(false);
const updateDone = ref(false);

async function handleUpdateClick() {
  if (isUpdating.value) return;
  isUpdating.value = true;
  updateDone.value = false;

  await updateSummary();

  isUpdating.value = false;
  updateDone.value = true;
  setTimeout(() => (updateDone.value = false), 1000);
}

/* ------------------------------
          CHART DATA
------------------------------ */
const countryList = ["US", "ID", "RU"];
const selectedCountry = ref("US");

const weeklyData = {
  US: { dates: ["12/1","12/2","12/3","12/4","12/5","12/6","12/7"], changed: [5,7,6,10,8,9,7], impactLevel: [1,1,2,2,3,3,2], productCount: [2,3,2,4,3,5,4] },
  ID: { dates: ["12/1","12/2","12/3","12/4","12/5","12/6","12/7"], changed: [8,6,9,11,12,10,9], impactLevel: [1,2,2,2,3,3,2], productCount: [3,2,3,5,4,4,3] },
  RU: { dates: ["12/1","12/2","12/3","12/4","12/5","12/6","12/7"], changed: [1,2,2,3,1,2,1], impactLevel: [1,1,1,1,2,1,2], productCount: [1,1,1,2,1,1,1] }
};

/* ------------------------------
          COLOR LOGIC
------------------------------ */
const impactToColor = (level, isDark) => {
  if (isDark) {
    return level === 1 ? "#3A4F7A" : level === 2 ? "#FDFF78" : "#FF5C5C";
  } else {
    return level === 1 ? "#4A5BB1" : level === 2 ? "#F3D24F" : "#E56363";
  }
};

/* ------------------------------
          ECHART OPTION
------------------------------ */
const regulationOption = computed(() => {
  const d = weeklyData[selectedCountry.value];

  const maxVal = Math.max(...d.changed, ...d.productCount);
  const dynamicMax = Math.ceil(maxVal * 1.2) + 1;

  return {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" },

    legend: {
      top: 0,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: isDark.value ? "#C8D0E0" : "#4B5563", fontSize: 11 },
    },

    grid: { left: 35, right: 18, top: 35, bottom: 5 },

    xAxis: {
      type: "category",
      data: d.dates,
      axisLabel: { color: isDark.value ? "#C8D0E0" : "#6B7280", fontSize: 10 },
      axisLine: { lineStyle: { color: isDark.value ? "rgba(255,255,255,0.12)" : "#D1D5DB" } }
    },

    yAxis: {
      type: "value",
      max: dynamicMax,
      axisLabel: { color: isDark.value ? "#C8D0E0" : "#6B7280", fontSize: 10 },
      splitLine: { lineStyle: { color: isDark.value ? "rgba(255,255,255,0.1)" : "#E5E7EB" } }
    },

    series: [
      {
        name: "변경 규제 수",
        type: "bar",
        barWidth: 14,
        itemStyle: {
          borderRadius: [6, 6, 0, 0],
          color: (params) => {
            const topColor = impactToColor(d.impactLevel[params.dataIndex], isDark.value);
            return {
              type: "linear",
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: topColor },
                { offset: 1, color: isDark.value ? "#1C2438" : "#E5E7EB" }
              ]
            };
          }
        },
        data: d.changed
      },
      {
        name: "영향받은 제품 수",
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: 4,
        itemStyle: { color: isDark.value ? "#4DE0FF" : "#009DDC" },
        lineStyle: { color: isDark.value ? "#4DE0FF" : "#009DDC", width: 2 },
        data: d.productCount
      }
    ]
  };
});
</script>

<style scoped>
.summary-card {
  border-left: 4px solid #FDFF78;
}

html:not(.dark) .summary-card {
  border-left: 4px solid #2C2C54;
}

.update-btn {
  transform: scale(1);
  transition: transform .15s ease, background .2s ease;
}
.update-btn:active {
  transform: scale(.92);
}

.loader {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #FDFF78;
  border-radius: 50%;
  animation: spin .6s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
