<template>
  <div class="chart-panel">
    <h3>{{ title }}</h3>
    <canvas id="chartCanvas"></canvas>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import Chart from 'chart.js/auto'

defineProps({ title: String })

onMounted(() => {
  const ctx = document.getElementById('chartCanvas')
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['A', 'B', 'C', 'D'],
      datasets: [{ label: '샘플 데이터', data: [5, 10, 8, 6] }]
    }
  })
})
</script>

<style scoped>
.chart-panel { padding: 1rem; background: white; border-radius: 8px; }
</style>
