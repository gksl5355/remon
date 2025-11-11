<template>
  <!-- 헤더 높이 약 100px 가정 -->
  <div class="p-8 bg-[#0E0E0E] min-h-[calc(100vh-100px)]">
    <div class="grid grid-cols-5 gap-6 h-[calc(100vh-100px-64px)]">
      <!-- 좌측: 규제 목록 + 종합 리포트 -->
      <div class="col-span-2 flex flex-col gap-6 h-full overflow-hidden">
        <div class="flex-1 h-full overflow-hidden">
          <RegulationTable @select-regulation="selectRegulation" />
        </div>
        <div class="h-[240px] overflow-hidden">
          <CombinedReport />
        </div>
      </div>

      <!-- 우측: 선택된 규제의 요약 리포트 -->
      <div class="col-span-3 h-full overflow-hidden">
        <SummaryReport :selectedRegulation="selectedRegulation" />
      </div>
    </div>
  </div>
</template>

<script setup>
import CombinedReport from "@/components/CombinedReport.vue";
import RegulationTable from "@/components/RegulationTable.vue";
import SummaryReport from "@/components/SummaryReport.vue";
import { ref } from "vue";

const selectedRegulation = ref(null);

const selectRegulation = (r) => {
  selectedRegulation.value = r;
};
</script>
