<template>
  <header class="header">
    <h1>REMON Dashboard</h1>
    <nav>
      <router-link to="/">홈</router-link>
      <router-link to="/admin">관리자</router-link>
    </nav>
  </header>
</template>

<style scoped>
.header {
  background-color: #20232a;
  color: #fff;
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
nav a {
  color: #61dafb;
  margin-left: 1rem;
  text-decoration: none;
}
nav a.router-link-active {
  font-weight: bold;
}
</style>
