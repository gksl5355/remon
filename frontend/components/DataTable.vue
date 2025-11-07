<template>
  <table class="data-table">
    <thead>
      <tr><th v-for="col in columns" :key="col">{{ col }}</th></tr>
    </thead>
    <tbody>
      <tr v-for="(row, i) in rows" :key="i">
        <td v-for="(col, j) in columns" :key="j">{{ row[col] }}</td>
      </tr>
    </tbody>
  </table>
</template>

<script setup>
defineProps({ columns: Array, rows: Array })
</script>

<style scoped>
.data-table {
  width: 100%;
  border-collapse: collapse;
}
.data-table th, .data-table td {
  padding: 8px;
  border: 1px solid #ddd;
}
</style>
