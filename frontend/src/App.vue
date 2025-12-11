<template>
  <div class="w-full h-screen overflow-hidden text-gray-100">
    
    <HeaderBar   v-if="route.path !== '/' && route.path !== '/login'" ref="headerRef" class="fixed top-0 left-0 w-full z-50" />
    
    <div
      class="w-full h-full"
      :style="contentStyle" 
    >
      <router-view :header-height="headerHeight" />
    </div>
  </div>
</template>

<script setup>
import HeaderBar from "@/components/HeaderBar.vue";
import { computed, inject, nextTick, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();       // ✅ 반드시 최상단에서 선언해야 함
const isDark = inject("isDark");

const headerRef = ref(null);
const headerHeight = ref(0);

/* ---------------------------
     🔥 헤더 표시/숨김 감지
---------------------------- */
watch(
  () => route.path,
  async () => {
    await nextTick();

    // 로그인/루트 페이지 → 헤더 없음
    if (route.path === "/" || route.path === "/login") {
      headerHeight.value = 0;
      return;
    }

    // 그 외 페이지 → 헤더 높이 적용
    if (headerRef.value?.$el) {
      headerHeight.value = headerRef.value.$el.offsetHeight;
    }
  },
  { immediate: true }
);

/* ---------------------------
     컨텐츠 padding-top 계산
---------------------------- */
const contentStyle = computed(() => {
  return `padding-top: ${headerHeight.value}px;`;
});

/* ---------------------------
     초기 mount 시 헤더 높이 계산
---------------------------- */
onMounted(async () => {
  await nextTick();
  if (headerRef.value?.$el) {
    headerHeight.value = headerRef.value.$el.offsetHeight;
  }
});
</script>

<style>
body, html, #app {
  height: 100%;
  margin: 0;
  padding: 0;
  background-color: #040E1B; /* 다크 배경 */
}
</style>
