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

          <div
            class="w-3 h-3 rounded-full border-2 transition-all duration-300"
            :class="[
              item.type === 'no-change'
                ? (isDark ? 'bg-mid-navy border-gray-600' : 'bg-gray-300 border-gray-400')
                : '',
              item.type === 'change'
                ? (isDark ? 'bg-primary-accent border-primary-accent'
                          : 'bg-blue-500 border-blue-400')
                : '',
              item.type === 'new'
                ? (isDark ? 'bg-accent-yellow border-accent-yellow'
                          : 'bg-yellow-400 border-yellow-300')
                : ''
            ]"
          ></div>

          <div
            v-if="i !== timeline.length - 1"
            class="w-[2px] flex-1 mt-1 transition-all duration-300"
            :class="isDark ? 'bg-timeline-line' : 'bg-gray-300'"
          ></div>

        </div>

        <div class="pb-4">
          <div
            class="text-[8px] mb-0.5 transition-all"
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
              v-if="item.type !== 'no-change'"
              class="text-[8px] px-1.5 py-0.5 rounded-full border transition-all"
              :class="[
                item.type === 'change'
                  ? (isDark
                      ? 'bg-primary-accent/10 text-primary-accent border-primary-accent/40'
                      : 'bg-blue-50 text-blue-600 border-blue-300')
                  : '',
                item.type === 'new'
                  ? (isDark
                      ? 'bg-accent-yellow/10 text-accent-yellow border-accent-yellow/40'
                      : 'bg-yellow-50 text-yellow-600 border-yellow-300')
                  : ''
              ]"
            >
              {{ item.type === 'change' ? '최근 변경' : '신규 규제' }}
            </span>
          </div>

          <div
            class="text-xs leading-relaxed transition-all"
            :class="isDark ? 'text-gray-400' : 'text-gray-600'"
          >
            {{ item.description }}
          </div>
        </div>
      </div>
    </div> </div>
</template>

<script setup>
import { inject } from "vue";
const isDark = inject("isDark");

const timeline = [
  { id: 1, date: "US · 2025-12-03", title: "오늘 변경사항 없음", type: "no-change", description: "시스템 모니터링 활성", },
  { id: 2, date: "US · 2025-12-02", title: "전자담배 광고 규제 업데이트", type: "change", description: "디지털 마케팅 제한에 대한 새로운 연방 지침", },
  { id: 3, date: "ID · 2025-12-01", title: "포장 요구사항 신설", type: "new", description: "건강 경고 라벨 크기가 패키지의 90%로 증가", },
  { id: 4, date: "ID · 2025-11-30", title: "흡연 구역 규제 확대", type: "change", description: "금연 구역으로 지정된 추가 공공 장소", },
  { id: 5, date: "RU · 2025-11-28", title: "정기 모니터링 검사 완료", type: "no-change", description: "규제 변경 사항 없음", },
  { id: 6, date: "ID · 2025-12-01", title: "포장 요구사항 신설", type: "new", description: "건강 경고 라벨 크기가 패키지의 90%로 증가", },
  { id: 7, date: "ID · 2025-11-30", title: "흡연 구역 규제 확대", type: "change", description: "금연 구역으로 지정된 추가 공공 장소", },
  { id: 8, date: "RU · 2025-11-28", title: "정기 모니터링 검사 완료", type: "no-change", description: "규제 변경 사항 없음", },
];
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