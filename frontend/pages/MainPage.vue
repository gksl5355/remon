<template>
  <div class="page">
    <h2>REMON 메인 페이지</h2>
    <p>백엔드와 통신 중...</p>
    <button @click="checkHealth">헬스체크</button>
    <p v-if="status">{{ status }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { checkHealthAPI } from '../services/api.js'

const status = ref('')

const checkHealth = async () => {
  const result = await checkHealthAPI()
  status.value = result.status
}
</script>

<style scoped>
.page {
  padding: 2rem;
}
button {
  padding: 0.6rem 1.2rem;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
</style>
