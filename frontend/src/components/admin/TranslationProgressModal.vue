<template>
  <div
    class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50
           flex items-center justify-center"
  >
    <div
      class="w-80 bg-[#0E1522] border border-white/10
             rounded-xl p-6 shadow-2xl animate-fadeUp"
    >
      <h3 class="text-[15px] font-semibold text-gray-100 mb-4">
        번역본 생성 중<span class="dots"></span>
      </h3>

      <!-- Progress Bar -->
      <div class="relative w-full h-3 bg-[#1A2333] rounded-full overflow-hidden">
        <!-- 실제 진행 영역 -->
        <div
          class="relative h-full bg-[#4A90E2] rounded-full
                 transition-all duration-700 ease-out overflow-hidden"
          :style="{ width: progress + '%' }"
        >
          <!-- Photoshop 스타일 빗금 -->
          <div class="absolute inset-0 stripe-anim"></div>
        </div>
      </div>

      <p class="text-[12px] text-gray-400 mt-3 text-center animate-pulse-soft">
        번역을 처리하는 중입니다. 잠시만 기다려주세요.
      </p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  progress: { type: Number, default: 0 }
});
</script>

<style scoped>
/* 팝업 등장 */
@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.animate-fadeUp {
  animation: fadeUp 0.25s ease-out;
}

/* 점점점 */
.dots::after {
  content: "";
  animation: dots 1.4s infinite steps(4);
}
@keyframes dots {
  0% { content: ""; }
  25% { content: "."; }
  50% { content: ".."; }
  75% { content: "..."; }
}

/* 텍스트 숨쉬기 */
@keyframes pulseSoft {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}
.animate-pulse-soft {
  animation: pulseSoft 1.8s ease-in-out infinite;
}

/* ===== Photoshop 스타일 빗금 ===== */
.stripe-anim {
  background-image: linear-gradient(
    45deg,
    rgba(255,255,255,0.25) 25%,
    transparent 25%,
    transparent 50%,
    rgba(255,255,255,0.25) 50%,
    rgba(255,255,255,0.25) 75%,
    transparent 75%,
    transparent
  );
  background-size: 22px 22px;
  animation: stripeMove 0.9s linear infinite;
  opacity: 0.6;
}

@keyframes stripeMove {
  from { background-position: 0 0; }
  to { background-position: 22px 0; }
}
</style>
