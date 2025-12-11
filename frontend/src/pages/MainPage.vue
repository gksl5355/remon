<template>
  <div
    class="w-full h-full flex flex-col gap-4 p-6 overflow-hidden transition-all duration-300"
    :class="isDark ? 'bg-[#040e1b] text-gray-200' : 'bg-gray-100 text-gray-800'"
  >

    <!-- ============================== -->
    <!--   TOP SECTION (MAP + TIMELINE) -->
    <!-- ============================== -->

    <div class="flex-[6] flex gap-4 min-h-0 overflow-hidden">

      <!-- LEFT : WORLD MAP -->
      <div class="flex-[3] min-h-0 p-4">
        <WorldMap class="w-full h-full" />
      </div>

      <!-- RIGHT : TIMELINE -->
      <div class="flex-[1] min-h-0 p-4">
        <Timeline class="w-full pr-2" />
      </div>

    </div>

    <!-- ============================== -->
    <!--   BOTTOM SECTION (AI Dashboard)  -->
    <!-- ============================== -->
    <div
      class="flex-none card-style overflow-visible h-[35vh] py-6 pr-3"
      :class="isDark
        ? 'bg-white/5 border-white/20 text-gray-200'
        : 'bg-white/70 border-gray-300 text-gray-800 shadow-lg'
      "
    >
      <div
        class="text-lg font-bold pl-10"
        :class="isDark ? 'text-white' : 'text-gray-900'"
      >
        AI Regulatory Trends Dashboard
      </div>

      <AiDashboard />
    </div>

  </div>
</template>

<script setup>
import { inject } from "vue";

import AiDashboard from "@/components/main/AiDashboard.vue";
import Timeline from "@/components/main/Timeline.vue";
import WorldMap from "@/components/main/WorldMap.vue";

const isDark = inject("isDark");
</script>

<style scoped>
/* Glass-like default (Dark mode base) */
.card-style {
  backdrop-filter: blur(18px);
  border-radius: 1rem;
  transition: all 0.3s ease;
}

/* Custom Scrollbar */
.overflow-y-auto::-webkit-scrollbar {
  width: 8px;
}
.overflow-y-auto::-webkit-scrollbar-thumb {
  background-color: #0A192F; 
  border-radius: 4px;
}
.overflow-y-auto::-webkit-scrollbar-track {
  background-color: rgba(255, 255, 255, 0.05);
}
</style>
