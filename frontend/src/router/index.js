import AdminPage from "@/pages/AdminPage.vue";
import MainPage from "@/pages/MainPage.vue";
import { createRouter, createWebHistory } from "vue-router";

const routes = [
  { path: "/", name: "MainPage", component: MainPage },
  { path: "/admin", name: "AdminPage", component: AdminPage },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;


