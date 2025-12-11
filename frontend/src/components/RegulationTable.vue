<template>
  <div
    class="bg-[#0E121A] rounded-2xl p-6 shadow-xl border border-white/5 
           flex flex-col gap-4 h-full"
  >
    <!-- HEADER -->
    <div>
      <h2 class="text-xl text-[#F1F5A8] tracking-widest font-semibold">
        REGULATION FILE
      </h2>
      <p class="text-xs text-gray-400 mt-1">국가 및 제품별 규제 파일 관리</p>
    </div>

    <!-- ACTION BUTTONS -->
    <div class="flex justify-end gap-3">
      <button
        @click="toggleFilter"
        class="text-[#C5FF70] hover:text-white transition text-lg"
        title="필터"
      >
        <i class="ph-funnel-simple"></i>
      </button>

      <button
        @click="openUploadModal"
        class="text-[#C5FF70] hover:text-white transition text-xl"
        title="업로드"
      >
        <i class="ph-plus-circle"></i>
      </button>
    </div>

    <!-- FILE LIST -->
    <div class="flex-1 overflow-y-auto pr-2 space-y-3">
      <div
        v-for="file in filteredFiles"
        :key="file.id"
        class="rounded-xl px-4 py-3 bg-[#0F1A27]/60 hover:bg-[#152233]/70
               border border-white/5 transition cursor-pointer relative flex flex-col"
      >
        <!-- 강조 세로 라인 -->
        <div class="absolute left-0 top-0 bottom-0 w-1 rounded-l-xl bg-[#D9E96E]"></div>

        <!-- 상단 정보 -->
        <div class="flex justify-between items-start">
          <div>
            <p class="text-sm text-white font-medium">{{ file.name }}</p>
            <p class="text-xs text-gray-400 mt-1">{{ file.country }} · {{ file.upload_date }}</p>
          </div>

          <!-- 액션 버튼 -->
          <div class="flex items-center gap-3">
            <button
              @click.stop="openDownloadOptions(file.id)"
              class="text-[#C5FF70] hover:text-white transition"
            >
              <i class="ph-download-simple"></i>
            </button>

            <button
              @click.stop="deleteFile(file.id)"
              class="text-red-400 hover:text-red-300 transition"
            >
              <i class="ph-x-circle"></i>
            </button>
          </div>
        </div>

        <!-- 태그 (옵션) -->
        <div class="flex items-center gap-2 mt-3">
          <span class="px-2 py-1 rounded-full bg-[#1F2B3A] text-[11px] text-gray-300">
            PDF
          </span>
          <span class="px-2 py-1 rounded-full bg-[#344155] text-[11px] text-[#D9E96E]">
            규제 문서
          </span>
        </div>
      </div>

      <!-- EMPTY -->
      <div
        v-if="filteredFiles.length === 0"
        class="text-center text-gray-500 text-sm py-10"
      >
        조건에 맞는 파일이 없습니다.
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

/* ============================================================
   1) world.json 국가 이름이 실제와 달라 매칭이 안되는 버그 해결
      → 지도 안 보이던 원인
============================================================ */
const NAME_FIX = {
  "United States": "United States of America",
  "Russian Federation": "Russia",
  "Indonesia": "Indonesia",
};

/* ============================================================
   2) 활성 국가 데이터
============================================================ */
const activeCountries = {
  "United States of America": {
    code: "US",
    fullName: "United States of America",
    coord: [-100, 40],
    status: "warning",
    last_update: "2025-11-12",
    latest_change: "니코틴 액상 신고 절차 강화",
  },
  Russia: {
    code: "RU",
    fullName: "Russia",
    coord: [100, 60],
    status: "safe",
    last_update: "2025-10-03",
    latest_change: "전자담배 광고 규제 확대",
  },
  Indonesia: {
    code: "ID",
    fullName: "Indonesia",
    coord: [120, -5],
    status: "danger",
    last_update: "2025-08-28",
    latest_change: "니코틴 농도 제한 기준 신설",
  },
};

// 코드로도 접근 가능하게 역변환
const activeCountriesByCode = {};
Object.values(activeCountries).forEach((c) => {
  activeCountriesByCode[c.code] = c;
});

/* ============================================================
   3) 라이트/다크 테마 색상 정의
============================================================ */
const theme = {
  dark: {
    inactive: "#27323F",
    active: "#354556",
    border: "#3B4654",
  },
  light: {
    inactive: "#E6E9EF",
    active: "#CBD4E2",
    border: "#AAB4C5",
  },
};

/* ============================================================
   4) 국가 마커 (Scatter)
============================================================ */
const markerSeriesData = Object.values(activeCountries).map((c) => ({
  name: c.code,
  value: c.coord,
  symbol: "circle",
  symbolSize: 34,
  label: {
    show: true,
    formatter: "{b}",
    color: "#fff",
    fontSize: 13,
    fontWeight: "bold",
  },
  itemStyle: {
    color: "#1B2B3D",
    borderColor:
      c.status === "warning"
        ? "#FACC15"
        : c.status === "danger"
        ? "#EF4444"
        : "#9CA3AF",
    borderWidth: 4,
    shadowBlur: 22,
    shadowColor:
      c.status === "warning"
        ? "rgba(250,204,21,0.4)"
        : c.status === "danger"
        ? "rgba(239,68,68,0.4)"
        : "transparent",
  },
}));

/* ============================================================
   5) 위험국 Ripple 효과
============================================================ */
const dangerRippleSeries = Object.values(activeCountries)
  .filter((c) => c.status === "danger")
  .map((c) => ({
    type: "effectScatter",
    coordinateSystem: "geo",
    rippleEffect: {
      scale: 2.4,
      period: 4,
      brushType: "stroke",
    },
    symbolSize: 45,
    itemStyle: {
      color: "rgba(239,68,68,0.35)",
    },
    data: [{ name: c.code, value: c.coord }],
    zlevel: 9,
  }));

/* ============================================================
   ⭐ 핵심: 지도 Option 생성 (다크/라이트 대응)
============================================================ */
const updateChartOption = () => {
  echarts.registerMap("world", worldJson);

  const current = isDark ? theme.dark : theme.light;

  option.value = {
    backgroundColor: "transparent",

    geo: {
      map: "world",
      roam: true,
      zoom: 1.1,
      label: { show: false },

      itemStyle: {
        areaColor: current.inactive,
        borderColor: current.border,
        borderWidth: 0.7,
      },

      emphasis: {
        label: { show: false },
        itemStyle: { areaColor: current.active },
      },

      // ⭐ 국가별 색상 지정 (여기서 이름 매칭 fix)
      regions: worldJson.features.map((f) => {
        const raw = f.properties.name;
        const key = NAME_FIX[raw] || raw;

        return {
          name: raw, // tooltip, click 이벤트용
          itemStyle: {
            areaColor: activeCountries[key]
              ? current.active
              : current.inactive,
          },
        };
      }),
    },

    series: [
      ...dangerRippleSeries,
      {
        type: "scatter",
        coordinateSystem: "geo",
        data: markerSeriesData,
        zlevel: 10,
      },
    ],

    // ⭐ Tooltip
    tooltip: {
      show: true,
      trigger: "item",
      backgroundColor: isDark
        ? "rgba(20,25,35,0.85)"
        : "rgba(255,255,255,0.9)",
      borderColor: isDark
        ? "rgba(232,198,99,0.45)"
        : "rgba(160,160,160,0.5)",
      borderWidth: 1,
      padding: 12,
      borderRadius: 10,
      textStyle: {
        color: isDark ? "#F1F5F9" : "#1E293B",
        fontSize: 13,
      },
      extraCssText: `
        backdrop-filter: blur(6px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.25);
      `,

      formatter: (params) => {
        const name = params.name;
        const data =
          activeCountries[name] ||
          activeCountries[NAME_FIX[name]] ||
          activeCountriesByCode[name];

        if (!data) return "";

        const statusLabel =
          data.status === "safe"
            ? "변경 없음"
            : data.status === "warning"
            ? "최근 변경"
            : "신규 규제";

        return `
          <div style="display:flex; flex-direction:column; gap:6px;">
            <div style="font-size:15px; font-weight:600;">
              ${data.code} · ${data.fullName}
            </div>

            <div style="font-size:12px; color:${
              isDark ? "#E8C663" : "#8D6B00"
            };">
              <b>${statusLabel}</b>
            </div>

            <div style="font-size:12px;">
              <b>마지막 변경일:</b> ${data.last_update}
            </div>

            <div style="font-size:12px; max-width:220px;">
              <b>변경 내용:</b> ${data.latest_change}
            </div>
          </div>
        `;
      },
    },
  };
};

/* ============================================================
   Mounted
============================================================ */
onMounted(async () => {
  updateChartOption();
  await nextTick();

  const chart = chartRef.value.chart;

  chart.on("click", (params) => {
    const data =
      activeCountries[params.name] ||
      activeCountries[NAME_FIX[params.name]] ||
      activeCountriesByCode[params.name];

    if (data) {
      router.push(`/regulation/${data.code}`).catch(() => {});
    }
  });

  setTimeout(() => chart.resize(), 200);
});

/* ============================================================
   ⭐ 다크/라이트 변경 감지 → 지도 업데이트
============================================================ */
watch(isDark, () => updateChartOption());
</script>
