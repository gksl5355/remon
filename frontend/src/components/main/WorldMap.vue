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
      class="absolute left-4 top-6/7 -translate-y-1/2 
            w-40 rounded-lg backdrop-blur-md shadow p-3 text-[11px] space-y-3 transition-all"
      :class="isDark ? 'bg-black/40 border border-white/10 text-gray-200' 
                     : 'bg-white/70 border border-gray-300 text-gray-700'"
    >
      <!-- 변경 여부 -->
      <div>
        <div class="text-[10px] mb-1" :class="isDark ? 'text-gray-400' : 'text-gray-500'">
          변경 여부
        </div>
        <div class="flex items-center gap-1.5">
          <span
            class="w-2.5 h-2.5 rounded-full border"
            :class="isDark ? 'bg-gray-500 border-gray-300' : 'bg-gray-300 border-gray-400'"
          ></span>
          <span>없음</span>
        </div>
      </div>

      <!-- 영향도 -->
      <div>
        <div class="text-[10px] mb-1" :class="isDark ? 'text-gray-400' : 'text-gray-500'">
          영향도 (변경 시)
        </div>

        <div class="flex items-center gap-2">
          <span class="flex items-center gap-1.5">
            <span class="w-2.5 h-2.5 rounded-full" :style="{ background: '#3A4F7A' }"></span>
            <span>Low</span>
          </span>

          <span class="flex items-center gap-1.5">
            <span class="w-2.5 h-2.5 rounded-full" :style="{ background: '#FDFF78' }"></span>
            <span>Medium</span>
          </span>

          <span class="flex items-center gap-1.5">
            <span class="w-2.5 h-2.5 rounded-full" :style="{ background: '#FF5C5C' }"></span>
            <span>High</span>
          </span>
        </div>
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

/* ===============================================
  1) world.json 국가명 통합 처리
================================================ */
const NAME_FIX = {
  "United States": "United States of America",
  "Russian Federation": "Russia",
  "Republic of Korea": "South Korea",
  Indonesia: "Indonesia",
};

/* ===============================================
  2) 영향도 색상
================================================ */
const impactColor = {
  High: "#EF4444",
  Medium: "#FACC15",
  Low: "#60A5FA",
};

/* ===============================================
  3) 더미 국가 데이터 
================================================ */
const activeCountries = {
  "United States of America": {
    code: "US",
    fullName: "United States of America",
    coord: [-98, 39],
    last_update: "2025-11-12",
    update_count: 3,
    impacts: ["High", "Medium"],
  },
  Russia: {
    code: "RU",
    fullName: "Russia",
    coord: [100, 62],
    last_update: "2025-10-03",
    update_count: 1,
    impacts: ["Low"],
  },
  Indonesia: {
    code: "ID",
    fullName: "Indonesia",
    coord: [118, -2],
    last_update: "2025-08-28",
    update_count: 2,
    impacts: ["Medium"],
  },
};

const activeCountriesByCode = {};
Object.values(activeCountries).forEach((c) => {
  activeCountriesByCode[c.code] = c;
});

/* ===============================================
  4) status 계산 (4단계)
================================================ */
function computeStatus(impacts) {
  if (!impacts || impacts.length === 0) return "none";
  if (impacts.includes("High")) return "high";
  if (impacts.includes("Medium")) return "medium";
  return "low";
}

Object.values(activeCountries).forEach((c) => {
  c.status = computeStatus(c.impacts);
});

/* ===============================================
  5) 테마 색상
================================================ */
const theme = {
  dark: {
    inactive: "#27323F",
    active: "#3A4656",
    border: "#3B4654",

    tooltipBg: "rgba(17, 23, 34, 0.92)",
    tooltipBorder: "#4B5563",
    tooltipText: "#E2E8F0",
    tooltipHighlight: "#FACC15",
  },
  light: {
    inactive: "#E6E9EF",
    active: "#CBD4E2",
    border: "#AAB4C5",

    tooltipBg: "rgba(255, 255, 255, 0.94)",
    tooltipBorder: "#CBD5E1",
    tooltipText: "#1E293B",
    tooltipHighlight: "#F59E0B",
  },
};

/* ===============================================
  6) Status → Marker Color 규칙
================================================ */
function getMarkerStyle(status) {
  switch (status) {
    case "none":
      return {
        border: "#6B7280",
        fill: "#1E293B",
        glow: "transparent",
      };
    case "low":
      return {
        border: "#3A4F7A",
        fill: "#1B2638",
        glow: "rgba(58,79,122,0.35)",
      };
    case "medium":
      return {
        border: "#FACC15",
        fill: "#3A2F0F",
        glow: "rgba(250,204,21,0.45)",
      };
    case "high":
      return {
        border: "#EF4444",
        fill: "#3B0E0E",
        glow: "rgba(239,68,68,0.45)",
      };
  }
}

/* ===============================================
  7) Marker Series
================================================ */
const markerSeriesData = Object.values(activeCountries).map((c) => {
  const s = getMarkerStyle(c.status);

  return {
    name: c.code,
    value: c.coord,
    symbol: "circle",
    symbolSize: 36,
    label: {
      show: true,
      formatter: "{b}",
      color: "#ffffff",
      fontSize: 12,
      fontWeight: 600,
    },
    itemStyle: {
      color: s.fill,
      borderColor: s.border,
      borderWidth: 4,
      shadowColor: s.glow,
      shadowBlur: c.status === "none" ? 6 : 22,
    },
  };
});

/* ===============================================
  8) High만 Ripple Effect
================================================ */
const dangerRippleSeries = Object.values(activeCountries)
  .filter((c) => c.status === "high")
  .map((c) => ({
    type: "effectScatter",
    coordinateSystem: "geo",
    rippleEffect: {
      scale: 2.8,
      period: 4,
      brushType: "stroke",
    },
    symbolSize: 48,
    itemStyle: { color: "rgba(239,68,68,0.25)" },
    data: [{ name: c.code, value: c.coord }],
    zlevel: 9,
  }));

/* ===============================================
  9) ECharts Option
================================================ */
const updateChartOption = () => {
  if (!chartRef.value) return;

  echarts.registerMap("world", worldJson);
  const current = isDark.value ? theme.dark : theme.light;

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

      regions: worldJson.features.map((f) => {
        const raw = f.properties.name;
        const key = NAME_FIX[raw] || raw;

        return {
          name: raw,
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

    /* Tooltip */
    tooltip: {
      show: true,
      trigger: "item",
      backgroundColor: current.tooltipBg,
      borderColor: current.tooltipBorder,
      borderWidth: 1,
      padding: 12,
      borderRadius: 12,
      textStyle: {
        color: current.tooltipText,
        fontSize: 13,
      },
      extraCssText: `
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.35);
      `,
      formatter: (params) => {
        const data =
          activeCountries[params.name] ||
          activeCountries[NAME_FIX[params.name]] ||
          activeCountriesByCode[params.name];

        if (!data) return "";

        const impactsHTML = data.impacts
          .map(
            (lvl) => `
            <span style="
              display:inline-block;
              padding:3px 10px;
              border-radius:8px;
              font-size:11px;
              font-weight:600;
              margin-right:6px;
              background:${impactColor[lvl]}33;
              color:${impactColor[lvl]};
              border:1px solid ${impactColor[lvl]}55;
            ">
              ${lvl}
            </span>`
          )
          .join("");

        return `
          <div style="
            display:flex;
            flex-direction:column;
            gap:10px;
            max-width:260px;
            line-height:1.5;
          ">

            <!-- 헤더 -->
            <div style="font-size:15px; font-weight:700; color:${current.tooltipText};">
              ${data.code} · ${data.fullName}
            </div>

            <div style="height:1px; background:${current.tooltipBorder}55"></div>

            <!-- 업데이트 시간 -->
            <div style="font-size:12px; color:${current.tooltipText};">
              <b>업데이트 시각:</b> ${data.last_update}
            </div>

            <!-- 파일 개수 -->
            <div style="font-size:12px; color:${current.tooltipText};">
              <b>업데이트된 파일:</b> ${data.update_count}개
            </div>

            <!-- 영향도 -->
            <div style="font-size:12px; color:${current.tooltipText};">
              <b>영향도:</b>
              <div style="margin-top:4px; display:flex; flex-wrap:wrap;">
                ${impactsHTML}
              </div>
            </div>

          </div>
        `;
      }
    },
  };

  nextTick(() => {
    chartRef.value?.chart?.setOption(option.value, {
      notMerge: true,
      lazyUpdate: false,
    });
  });
};

/* ===============================================
  10) Mounted
================================================ */
onMounted(() => {
  updateChartOption();

  const chart = chartRef.value.chart;
  chart.on("click", (params) => {
    const data =
      activeCountries[params.name] ||
      activeCountries[NAME_FIX[params.name]] ||
      activeCountriesByCode[params.name];

    if (data) {
      router.push({
        name: "FileList",
        params: { countryCode: data.code },
      });
    }
  });
});

/* ===============================================
  11) Dark/Light mode 감지
================================================ */
watch(isDark, () => updateChartOption());
</script>
