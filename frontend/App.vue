<template>
  <div id="app">
    <HeaderBar />
    <router-view />
  </div>
</template>

<script setup>
import HeaderBar from './components/HeaderBar.vue'
</script>

<style>
#app {
  font-family: 'Inter', sans-serif;
  background-color: #f8f9fa;
  min-height: 100vh;
  margin: 0;
}
</style>
