<template>
  <div class="space-y-6">

    <div
      v-for="(item, i) in timeline"
      :key="item.id"
      class="relative flex gap-4"
    >
      <!-- 점 + 세로 라인 -->
      <div class="flex flex-col items-center">
        <!-- 점 -->
        <div
          class="w-4 h-4 rounded-full"
          :class="{
            'bg-gray-400': item.type === 'no-change',
            'bg-yellow-400': item.type === 'change',
            'bg-red-500': item.type === 'new',
          }"
        ></div>

        <!-- 세로 라인 -->
        <div
          v-if="i !== timeline.length - 1"
          class="w-[2px] flex-1 mt-1"
          :class="isDark ? 'bg-gray-700' : 'bg-gray-300'"
        ></div>
      </div>

      <!-- 내용 -->
      <div>
        <div class="text-xs text-gray-400 mb-1">{{ item.date }}</div>

        <div class="flex items-center gap-2 mb-1">
          <span class="text-base font-semibold text-gray-100">{{ item.title }}</span>

          <span
            v-if="item.type !== 'no-change'"
            class="text-[10px] px-2 py-0.5 rounded-full border"
            :class="{
              'bg-yellow-500/10 text-yellow-400 border-yellow-500/40': item.type === 'change',
              'bg-red-500/10 text-red-400 border-red-500/40': item.type === 'new',
            }"
          >
            {{ item.type === 'change' ? '최근 변경' : '신규 규제' }}
          </span>
        </div>

        <div class="text-sm text-gray-400 leading-relaxed">
          {{ item.description }}
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { inject } from "vue";

const isDark = inject("isDark");

const timeline = [
  {
    id: 1,
    date: "US · 2025-12-03",
    title: "오늘 변경사항 없음",
    type: "no-change",
    description: "시스템 모니터링 활성",
  },
  {
    id: 2,
    date: "US · 2025-12-02",
    title: "전자담배 광고 규제 업데이트",
    type: "change",
    description: "디지털 마케팅 제한에 대한 새로운 연방 지침",
  },
  {
    id: 3,
    date: "ID · 2025-12-01",
    title: "포장 요구사항 신설",
    type: "new",
    description: "건강 경고 라벨 크기가 패키지의 90%로 증가",
  },
  {
    id: 4,
    date: "ID · 2025-11-30",
    title: "흡연 구역 규제 확대",
    type: "change",
    description: "금연 구역으로 지정된 추가 공공 장소",
  },
  {
    id: 5,
    date: "RU · 2025-11-28",
    title: "정기 모니터링 검사 완료",
    type: "no-change",
    description: "규제 변경 사항 없음",
  },
];
</script>
