import { createRouter, createWebHistory } from 'vue-router'
import MainPage from '../pages/MainPage.vue'
import AdminPage from '../pages/AdminPage.vue'

const routes = [
  { path: '/', component: MainPage },
  { path: '/admin', component: AdminPage }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
