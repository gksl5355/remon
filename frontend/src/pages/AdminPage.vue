<template>
  <div class="p-10 min-h-screen bg-[#080D17] text-gray-200">
    <!-- MAIN PAGE HEADER -->
    <div class="mb-10">

      <div class="flex items-center gap-4 mb-2">

        <!-- Icon Badge (Shield Check) -->
        <div
          class="w-12 h-12 flex items-center justify-center rounded-xl
                bg-[#1A1F2B] border border-white/10 shadow-md"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="w-6 h-6 text-[#cad660]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="1.6"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 3l7 4v5c0 5-3.5 9-7 9s-7-4-7-9V7l7-4z"
            />
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M9.5 12l2 2 3.5-4"
            />
          </svg>
        </div>

        <!-- Title -->
        <div>
          <h1 class="text-2xl font-bold tracking-wide text-gray-100">
            ADMIN DASHBOARD
          </h1>
          <p class="text-sm text-gray-500 mt-1">
            Manage Files, AI Reports & Crawling Pipelines
          </p>
        </div>

      </div>

      <!-- Underline Accent -->
      <div class="h-[2px] w-full bg-gradient-to-r from-[#cad660] to-transparent opacity-70"></div>
    </div>



    <div class="grid grid-cols-1 lg:grid-cols-12 gap-8">

      <!-- File Data -->
      <div
        class="lg:col-span-6 rounded-xl bg-[#0D1523]/60 
               border border-gray-700/40 shadow-xl p-6 flex flex-col h-[70vh]"
      >
        <FileDataPanel />
      </div>

      <!-- Crawling Data -->
      <div
        class="lg:col-span-6 rounded-xl bg-[#0D1523]/60 
               border border-gray-700/40 shadow-xl p-6 flex flex-col h-[70vh]"
      >
        <CrawlingDataPanel />
      </div>

    </div>
  </div>
</template>

<script setup>
import CrawlingDataPanel from "@/components/admin/CrawlingDataPanel.vue";
import FileDataPanel from "@/components/admin/FileDataPanel.vue";
</script>
