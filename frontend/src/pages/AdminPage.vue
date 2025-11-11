<template>
  <div
    class="h-[calc(100vh-100px)] bg-[#0E0E0E] text-gray-300 p-8 flex flex-col overflow-hidden"
  >
    <!-- 🔹 상단: 규제 문서 + 요약 리포트 (3/5 비율 = 60%) -->
    <div class="grid grid-cols-2 gap-6 flex-shrink-0 h-[60%] overflow-hidden">
      <AdminRegulationTable />
      <AdminSummaryTable />
    </div>

    <!-- 🔹 하단: 웹서치 (2/5 비율 = 40%) -->
    <div class="flex-1 h-[40%] mt-6 overflow-hidden">
      <AdminWebSearchTable />
    </div>
  </div>
</template>

<script setup>
import AdminRegulationTable from "@/components/admin/AdminRegulationTable.vue";
import AdminSummaryTable from "@/components/admin/AdminSummaryTable.vue";
import AdminWebSearchTable from "@/components/admin/AdminWebSearchTable.vue";
</script>
