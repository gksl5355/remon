<template>
  <!-- <div class="space-y-4 transition-all duration-300"> -->
  <div class="w-full h-full flex flex-col min-h-0 space-y-4 transition-all duration-300">

    <div
      class="timeline-header-container sticky top-0 z-20 backdrop-blur-md pb-3 transition-all"
      :class="isDark ? 'bg-[#0b0f14]/90' : 'bg-gray-100'"
    >
      <div class="timeline-header-wrapper flex items-center pt-3">
        <h2
          class="timeline-header text-xl font-bold tracking-[0.35em] relative pb-1"
          :class="isDark ? 'text-white' : 'text-gray-900'"
        >
          TIME LINE

          <span
            class="absolute left-0 bottom-0 w-full h-[2px]"
            :class="isDark
              ? 'bg-gradient-to-r from-[#FDFF78] to-[#88C0D0]'
              : 'bg-gradient-to-r from-[#2c2c54] to-[#8888b4]'
            "
          ></span>
        </h2>

      </div>
    </div>

    <div class="timeline-scroll-container flex-1 min-h-0 overflow-y-auto pr-1">
      <div
        v-for="(item, i) in timeline"
        :key="item.id"
        class="relative flex gap-4 transition-all duration-300"
        :class="isDark ? 'text-gray-200' : 'text-gray-800'"
      >
        <div class="flex flex-col items-center">

          <!-- DOT -->
          <div
            class="relative rounded-full border transition-all duration-300"
            :class="dotWrapperClass(item)"
          >
            <!-- inner dot -->
            <div
              class="w-full h-full rounded-full"
              :class="dotInnerClass(item)"
            />

            <!-- pulse (parse) effect -->
            <span
              v-if="isParsing(item)"
              class="absolute inset-0 rounded-full animate-ping opacity-40"
              :class="dotPingClass(item)"
            />
          </div>

          <!-- LINE -->
          <div
            v-if="i !== timeline.length - 1"
            class="w-[2px] flex-1 mt-1 transition-all duration-300"
            :class="lineClass(item)"
          />
        </div>

        <div class="pb-4">
          <div
            class="text-[13px] mb-0.5 transition-all"
            :class="isDark ? 'text-gray-500' : 'text-gray-500'"
          >
            {{ item.date }}
          </div>

          <div class="flex items-center gap-2 mb-1">
            <span
              class="text-sm font-semibold transition-all"
              :class="isDark ? 'text-gray-100' : 'text-gray-900'"
            >
              {{ item.title }}
            </span>

            <span
              v-if="item.status === 'crawling' || item.status === 'reporting'"
              class="text-[8px] px-1.5 py-0.5 rounded-full border animate-pulse"
              :class="statusBadgeClass(item)"
            >
              {{ statusText(item.status) }}
            </span>
          </div>

          <div
            class="text-[11px] leading-relaxed transition-all"
            :class="isDark ? 'text-gray-400' : 'text-gray-600'"
          >
            {{ item.description }}
          </div>
        </div>
      </div>
    </div> </div>
</template>

<script setup>
import { inject, onMounted, ref } from "vue";
import api from "@/services/api.js";

const isDark = inject("isDark");

const timeline = ref([]);

const fetchTimeline = async () => {
  try {
    const response = await api.get('/main/timeline');  
    timeline.value = response.data;
  } catch (error) {
    console.error('Failed to load timeline:', error);
    timeline.value = [];
  }
};

onMounted(fetchTimeline);

/* =========================
   STATUS TEXT
========================= */
const statusText = (status) => {
  if (status === "crawling") return "진행 중";
  if (status === "reporting") return "AI 생성 중";
  return "";
};

/* =========================
   STATUS BADGE
========================= */
const statusBadgeClass = (item) => {
  if (item.status === "crawling")
    return "bg-emerald-400/10 text-emerald-300 border-emerald-400/40";

  if (item.status === "reporting")
    return "bg-sky-400/10 text-sky-300 border-sky-400/40";

  return "";
};

const isParsing = (item) =>
  item.status === "crawling" || item.status === "reporting";

/* =========================
   DOT SIZE + BORDER
========================= */
const dotWrapperClass = (item) => {
  if (item.status === "crawling")
    return "w-3 h-3 border-emerald-400";

  if (item.status === "reporting")
    return "w-3 h-3 border-sky-400";

  if (item.status === "done" && item.type !== "no-change")
    return "w-3 h-3 border-yellow-400/50";

  // done + no-change
  return "w-3 h-3 border-gray-400/40";
};

/* =========================
   DOT COLOR
========================= */
const dotInnerClass = (item) => {
  if (item.status === "crawling")
    return "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.6)]";

  if (item.status === "reporting")
    return "bg-sky-400 shadow-[0_0_10px_rgba(56,189,248,0.6)]";

  if (item.status === "done" && item.type !== "no-change")
    return "bg-yellow-400/40";

  // done + no-change
  return "bg-gray-400/30";
};

/* =========================
   PULSE COLOR
========================= */
const dotPingClass = (item) => {
  if (item.status === "crawling") return "bg-emerald-400";
  if (item.status === "reporting") return "bg-sky-400";
  return "";
};

/* =========================
   LINE STYLE
========================= */
const lineClass = (item) => {
  if (item.status === "crawling") {
    return isDark.value
      ? "bg-gradient-to-b from-emerald-400/70 via-emerald-400/30 to-transparent"
      : "bg-gradient-to-b from-emerald-500/70 via-emerald-500/30 to-transparent";
  }

  if (item.status === "reporting") {
    return isDark.value
      ? "bg-gradient-to-b from-sky-400/60 via-sky-400/25 to-transparent"
      : "bg-gradient-to-b from-sky-500/60 via-sky-500/25 to-transparent";
  }

  if (item.status === "done" && item.type !== "no-change") {
    return isDark.value
      ? "bg-gradient-to-b from-yellow-400/35 to-transparent"
      : "bg-gradient-to-b from-yellow-500/35 to-transparent";
  }

  return isDark.value
    ? "bg-timeline-line opacity-20"
    : "bg-gray-300/30";
};
</script>

<style scoped>
.timeline-header {
  padding-bottom: 2px;
  border-bottom: 2px solid transparent;
  background-position: 0 100%;
  background-repeat: no-repeat;
  background-size: 100% 2px;
  letter-spacing: 0.35em;
}

/* Dark mode underline */
:global(.dark) .timeline-header {
  color: #E5E7EB;
  background-image: linear-gradient(
    to right,
    #fdff78,
    #88c0d0
  );
}

/* Light mode underline */
:global(.light) .timeline-header {
  color: #1f2937;
  background-image: linear-gradient(
    to right,
    #2c2c54,
    #8888b4
  );
}

/* ================================= */
/* ⭐ MODIFIED: Scrolbar Styles for .timeline-scroll-container */
/* ================================= */
/* 기본 설정 (공통) */
.timeline-scroll-container::-webkit-scrollbar {
  width: 8px;
}
.timeline-scroll-container::-webkit-scrollbar-button {
  display: none;
}
.timeline-scroll-container::-webkit-scrollbar-corner {
  background: transparent;
}

/* ☀ Light Mode = html:not(.dark) */
html:not(.dark) .timeline-scroll-container::-webkit-scrollbar-track {
  background: #f0f0f0;
  border-radius: 4px;
}
html:not(.dark) .timeline-scroll-container::-webkit-scrollbar-thumb {
  background: #c0c0c0;
  border-radius: 4px;
}

/* 🌙 Dark Mode = html.dark */
html.dark .timeline-scroll-container::-webkit-scrollbar-track {
  background: #111827; 
}
html.dark .timeline-scroll-container::-webkit-scrollbar-thumb {
  background: #374151; 
  border-radius: 4px;
}

/* 기존 색상 유지 */
.bg-mid-navy { background-color: #0A192F; }
.bg-timeline-line { background-color: #1A3445; }
.text-primary-accent { color: #88C0D0; }
.bg-primary-accent { background-color: #88C0D0; }
.border-primary-accent { border-color: #88C0D0; }
.text-accent-yellow { color: #FDFF78; }
.bg-accent-yellow { background-color: #FDFF78; }
.border-accent-yellow { border-color: #FDFF78; }

</style>