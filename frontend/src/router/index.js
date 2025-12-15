import AdminPage from "@/pages/AdminPage.vue";
import LoginPage from "@/pages/LoginPage.vue";
import MainPage from "@/pages/MainPage.vue";

import { createRouter, createWebHistory } from "vue-router";
import { Spring_Api } from "@/services/api";

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

router.beforeEach(async (to, from, next) => {
  // 로그인 페이지는 항상 접근 가능
  if (to.path === '/') {
    next();
    return;
  }

  try {
    // 서버에 세션 확인
    const res = await Spring_Api.get('/auth/check-auth');
    const isAdmin = res.data.isAdmin;

    // /admin 페이지는 관리자만 접근
    if (to.path === '/admin' && !isAdmin) {
      alert('관리자 권한이 필요합니다.');
      next('/main');
      return;
    }

    next(); // 인증 성공
  } catch (err) {
    // 세션 없음 (401) → 로그인 페이지로
    alert('로그인이 필요합니다.');
    next('/');
  }
});

export default router;
