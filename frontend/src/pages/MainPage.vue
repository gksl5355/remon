<template>
  <div class="w-full min-h-screen flex gap-6 p-6 bg-[#0F172A] text-gray-100">

    <!-- 왼쪽 -->
    <div class="flex flex-col flex-[3] gap-6 min-h-0">
      
      <!-- 글로벌 모니터링 -->
      <div class="flex-[2] bg-slate-800/70 p-6 rounded-2xl shadow-md backdrop-blur flex flex-col">
        <div class="text-lg font-semibold mb-3">글로벌 모니터링</div>
        <WorldMap class="flex-1" />
      </div>

      <!-- 대시보드 -->
      <div class="flex-[1] bg-slate-800/70 p-6 rounded-2xl shadow-md backdrop-blur">
        <div class="text-lg font-semibold mb-3">AI 종합 대시보드</div>
      </div>
    </div>

    <!-- 오른쪽 타임라인 -->
    <div class="flex-[1] min-h-0">
      <div class="h-full bg-slate-800/70 p-6 rounded-2xl shadow-md backdrop-blur flex flex-col">
        <div class="text-xl font-bold mb-4">규제 타임라인</div>

        <!-- 타임라인 영역 확보 -->
        <div class="flex-1 min-h-[350px] overflow-y-auto pr-2">
          <Timeline />
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import Timeline from "@/components/main/Timeline.vue";
import WorldMap from "@/components/main/WorldMap.vue";
</script>
