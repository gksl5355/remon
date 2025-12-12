<template>
  <div
    class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center
           transition-opacity duration-300"
  >
    <div
      class="w-80 bg-[#0E1522] border border-white/10 rounded-xl p-6 shadow-2xl
             animate-[fadeIn_0.25s_ease-out]"
    >
      <!-- Title -->
      <h3 class="text-[15px] font-semibold text-gray-100 mb-4 tracking-wide">
        번역본 생성 중...
      </h3>

      <!-- Progress Bar Wrapper -->
      <div class="w-full h-3 bg-[#1A2333] rounded-full overflow-hidden relative">

        <!-- Progress Bar Actual -->
        <div
          class="h-full bg-[#4A90E2] rounded-full
                 transition-all duration-300 ease-out"
          :style="{ width: progress + '%' }"
        ></div>
        
      </div>

      <p class="text-[12px] text-gray-400 mt-3 leading-relaxed">
        번역을 처리하는 중입니다. 잠시만 기다려주세요.
      </p>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  progress: {
    type: Number,
    default: 0
  }
});
</script>

<style>
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
