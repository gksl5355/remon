<template>
  <div class="w-full h-full relative">
    <v-chart
      ref="chartRef"
      class="w-full h-full"
      :option="option"
      autoresize
    />

    <!-- 상태 범례 -->
    <div
      class="absolute right-4 top-1/2 -translate-y-1/2 flex flex-col gap-3 p-4
             rounded-xl text-gray-200 text-sm bg-black/20 backdrop-blur-md"
    >
      <div class="font-semibold mb-1 text-gray-300">상태</div>

      <div class="flex items-center gap-2">
        <span class="w-3 h-3 rounded-full" style="background:#6B7280;"></span>
        <span>변경 없음</span>
      </div>

      <div class="flex items-center gap-2">
        <span class="w-3 h-3 rounded-full" style="background:#E8C663;"></span>
        <span>최근 변경</span>
      </div>

      <div class="flex items-center gap-2">
        <span class="w-3 h-3 rounded-full" style="background:#EF4444;"></span>
        <span>신규 규제</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import worldJson from "@/assets/world.json";
import * as echarts from "echarts";
import { inject, nextTick, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

const chartRef = ref(null);
const option = ref(null);
const router = useRouter();
const isDark = inject("isDark");

// ======================
// 1. 국가 규제 데이터
// ======================
const regulationData = {
  "United States of America": {
    flag: "🇺🇸",
    nameKo: "미국",
    latest_change: "니코틴 액상 신고 절차 강화",
    last_update: "2025-11-12",
    status: "warning",
  },
  Russia: {
    flag: "🇷🇺",
    nameKo: "러시아",
    latest_change: "전자담배 광고 규제 확대",
    last_update: "2025-10-03",
    status: "safe",
  },
  Indonesia: {
    flag: "🇮🇩",
    nameKo: "인도네시아",
    latest_change: "니코틴 농도 제한 기준 신설",
    last_update: "2025-08-28",
    status: "danger",
  },
};

// ======================
// 2. 상태별 색상 팔레트
// ======================
const statusColors = {
  safe: "#6B7280",      // Slate gray
  warning: "#E8C663",   // Gold
  danger: "#EF4444",    // Red
};

// ======================
// 3. 국가 마커 위치
// ======================
const markerData = [
  { name: "US", value: [-100, 40], itemStyle: { color: statusColors.warning } },
  { name: "RU", value: [100, 60], itemStyle: { color: statusColors.safe } },
  { name: "ID", value: [120, -5], itemStyle: { color: statusColors.danger } },
];

// ======================
// 4. 옵션 생성 함수
// ======================
const updateChartOption = () => {
  echarts.registerMap("world", worldJson);

  const activeCountries = Object.keys(regulationData);

  const inactiveColor = "#1B2A41";   // ⭐ 어두운 기본 지도색
  const hoverColor = "#23344D";      // ⭐ 자연스러운 hover 강조

  const regionsData = activeCountries.map((name) => ({
    name,
    itemStyle: {
      areaColor: statusColors[regulationData[name].status],
      borderColor: "#0F172A",
      borderWidth: 1,
    },
    emphasis: {
      itemStyle: {
        areaColor: statusColors[regulationData[name].status],
        shadowBlur: 15,
        shadowColor: "rgba(0,0,0,0.4)",
      },
    },
  }));

  option.value = {
    backgroundColor: "transparent",

    tooltip: {
      trigger: "item",
      triggerOn: "mousemove",
      alwaysShowContent: false,

      backgroundColor: "rgba(15,23,42,0.95)",
      borderColor: "#E8C663",
      borderWidth: 1,
      borderRadius: 10,
      padding: 12,
      textStyle: {
        color: "#F8FAFC",
      },

      formatter: (params) => {
        const key = params.data?.name || params.name;

        // ⭐ 활성 국가만 tooltip 출력, 나머지는 비활성화
        if (!regulationData[key]) return "";

        const info = regulationData[key];

        return `
          <div style="text-align:center;">
            <div style="font-size:22px">${info.flag}</div>
            <div style="font-size:14px; font-weight:bold; margin-top:4px;">
              ${info.nameKo} (${key})
            </div>
            <div style="font-size:12px; margin-top:8px; color:#E8C663;">
              ${info.latest_change}
            </div>
            <div style="font-size:11px; margin-top:4px; color:#9CA3AF;">
              마지막 변경일: ${info.last_update}
            </div>
          </div>
        `;
      }
    },

    geo: {
      map: "world",
      roam: true,
      left: "4%",
      right: "4%",
      top: "4%",
      bottom: "4%",

      // ⭐ 국가 이름 표시 제거
      label: {
        show: false
      },
      emphasis: {
        label: { show: false },
        itemStyle: {
          areaColor: hoverColor,
        }
      },

      itemStyle: {
        areaColor: inactiveColor,
        borderColor: "#0F172A",
        borderWidth: 0.6,
      },

      regions: regionsData,
    },

    series: [
      {
        name: "규제 국가",
        type: "scatter",
        coordinateSystem: "geo",
        symbolSize: 16,
        data: markerData,

        // ⭐ 여기서만 tooltip 허용
        tooltip: {
          show: true,
          formatter: (params) => {
            const key = params.name;

            // 활성국가 아닌 경우 -> tooltip 완전 차단
            if (!regulationData[key]) return "";

            const info = regulationData[key];

            return `
              <div style="text-align:center;">
                <div style="font-size:22px">${info.flag}</div>
                <div style="font-size:14px; font-weight:bold; margin-top:4px;">
                  ${info.nameKo} (${key})
                </div>
                <div style="font-size:12px; margin-top:8px; color:#E8C663;">
                  ${info.latest_change}
                </div>
                <div style="font-size:11px; margin-top:4px; color:#9CA3AF;">
                  마지막 변경일: ${info.last_update}
                </div>
              </div>
            `;
          }
        },

        label: {
          show: true,
          formatter: (p) => p.name,
          color: "#fff",
          fontWeight: "bold",
          fontSize: 11,
        }
      }
    ]

  };
};

// ======================
// 5. Mount + Resize 안정 처리
// ======================
onMounted(async () => {
  updateChartOption();
  await nextTick();

  // ec 인스턴스 안전 획득
  const chart = chartRef.value?.getEchartsInstance?.();
  if (!chart) return;

  chart.on("click", (p) => {
    if (regulationData[p.name]) {
      router.push(`/country/${p.name}`);
    }
  });

  setTimeout(() => chart.resize(), 200);
});

watch(isDark, () => updateChartOption());
</script>

<style scoped>
</style>
