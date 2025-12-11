import AdminPage from "@/pages/AdminPage.vue";
import LoginPage from "@/pages/LoginPage.vue";
import MainPage from "@/pages/MainPage.vue";

import { createRouter, createWebHistory } from "vue-router";

const routes = [
  { path: "/", name: "login", component: LoginPage },
  { path: "/main", name: "MainPage", component: MainPage },
  { path: "/admin", name: "AdminPage", component: AdminPage },

  {
    path: "/regulation/:countryCode/files",
    name: "FileList",
    component: () => import("@/pages/FileListPage.vue")
  },
  {
    path: "/regulation/:countryCode/file/:fileId",
    name: "RegulationDetail",
    component: () => import("@/pages/RegulationDetailPage.vue")
  }
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

export default router;
