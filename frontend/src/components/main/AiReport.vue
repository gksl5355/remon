<template>
  <div :class="['glass-card', isDark ? 'glass-dark' : 'glass-light']">
    <h3 class="font-semibold text-sm mb-4">{{ title }}</h3>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: "AI 종합 리포트" }
});
</script>
<style scoped>
.glass-card {
  position: relative;   /* ← 반드시 필요! */

  border-radius: 20px;
  padding: 24px;

  /* 반투명 + blur */
  background: rgba(255, 255, 255, 0.22);

  /* 연한 테두리 */
  border: 1px solid rgba(255, 255, 255, 0.35);

  /* 부드러운 입체감 */
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);

  overflow: hidden;     /* ← before 하이라이트가 넘치지 않도록 */
  transition: all 0.3s ease;
}

/* ☀ 라이트 모드 */
.glass-light {
  background: rgba(255, 255, 255, 0.28);
  border-color: rgba(255, 255, 255, 0.45);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.08);
}

/* 🌙 다크 모드 */
.glass-dark {
  background: rgba(255, 255, 255, 0.08); /* 더 투명 + 어둡고 우아한 느낌 */
  border-color: rgba(255, 255, 255, 0.12);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.45);
}
</style>