<template>
  <div class="h-screen flex flex-col">

    <!-- Header -->
    <div ref="headerRef" class="flex-shrink-0">
      <HeaderBar />
    </div>

    <!-- Main Layout -->
    <div
      class="flex-1 min-h-0"
      :style="headerHeight > 0 ? `height: calc(100vh - ${headerHeight}px)` : ''"
    >
      <router-view :header-height="headerHeight" />
    </div>

  </div>
</template>

<script setup>
import HeaderBar from "@/components/HeaderBar.vue";
import { nextTick, onMounted, ref } from "vue";

const headerRef = ref(null);
const headerHeight = ref(0);

onMounted(async () => {
  await nextTick();
  headerHeight.value = headerRef.value?.offsetHeight || 0;
});
</script>
