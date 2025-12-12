<template>
  <div
    class="fixed inset-0 bg-black/50 backdrop-blur-md z-40 flex items-center justify-center animate-fadeIn"
    @click.self="$emit('close')"
  >
    <div
      class="w-80 rounded-xl shadow-[0_8px_30px_rgba(0,0,0,0.45)]
             border border-white/10 bg-[#121a28]/90 backdrop-blur-xl
             p-6 animate-popupEnter relative"
    >

      <div
        class="absolute top-0 left-0 right-0 h-[2px] rounded-t-xl
               bg-gradient-to-r from-transparent via-white/20 to-transparent"
      ></div>

      <h3 class="text-[15px] font-semibold text-gray-100 mb-4 tracking-wide">
        파일 다운로드
      </h3>

      <!-- BUTTON GROUP -->
      <div class="space-y-2.5">

        <!-- Original -->
        <button
          class="w-full py-2 text-[14px] rounded-lg
                 bg-[#1A2333]/70 hover:bg-[#212d42]
                 border border-white/10 transition-all
                 text-gray-100 flex items-center justify-center gap-2"
          @click="$emit('download-original')"
        >
          <span>원문 다운로드</span>
        </button>

        <!-- Translated -->
        <button
          class="w-full py-2 text-[14px] rounded-lg
                 bg-[#1A2333]/70 hover:bg-[#212d42]
                 border border-white/10 transition-all
                 text-gray-100 flex items-center justify-center gap-2"
          @click="$emit('download-translated')"
        >
          <span>번역본 다운로드</span>
        </button>
      </div>

      <!-- Divider -->
      <div class="mt-4 mb-3 border-t border-white/10"></div>

      <!-- Description -->
      <p class="text-[11px] text-gray-400 leading-relaxed text-center">
        * 번역본 다운로드는 번역 작업으로 인해<br />
        &nbsp;&nbsp;약간의 시간이 소요될 수 있습니다.
      </p>
    </div>
  </div>
</template>

<style scoped>
/* Dim Fade-In */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
.animate-fadeIn {
  animation: fadeIn 0.25s ease-out;
}

/* Popup Enter Animation */
@keyframes popupEnter {
  0% {
    opacity: 0;
    transform: translateY(10px) scale(0.97);
    filter: blur(2px);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
    filter: blur(0);
  }
}
.animate-popupEnter {
  animation: popupEnter 0.28s cubic-bezier(0.16, 1, 0.3, 1);
}
</style>
