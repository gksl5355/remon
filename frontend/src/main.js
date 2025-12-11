import { createApp, ref, watchEffect } from "vue"; // ← watchEffect 추가!
import App from "./App.vue";
import router from "./router";

import "./assets/tailwind.css";

import { MapChart } from "echarts/charts";
import { GeoComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import VueECharts from "vue-echarts";

use([CanvasRenderer, MapChart, TooltipComponent, VisualMapComponent, GeoComponent]);

const app = createApp(App);

// ----------------------------
// 🌙 전역 다크모드 provide
// ----------------------------
const isDark = ref(true);

watchEffect(() => {
  if (isDark.value) {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
});

const toggleDarkMode = () => {
  isDark.value = !isDark.value;
};

app.provide("isDark", isDark);
app.provide("toggleDarkMode", toggleDarkMode);

// v-chart 등록
app.component("v-chart", VueECharts);

app.use(router);
app.mount("#app");
