// 📁 src/services/api.js
import axios from "axios";

const api = axios.create({
  baseURL: "https://ingress.skala25a.project.skala-ai.com/skala2-4-17/api", // ✅ FastAPI 기본 엔드포인트
  timeout: 5000, // 5초 타임아웃
});

// Spring 인증용 api (조영우 작성)
export const Spring_Api = axios.create({
  baseURL: "https://ingress.skala25a.project.skala-ai.com/skala2-4-17/spring/api",
  withCredentials: true, // 세션 쿠키
  timeout: 5000,
  headers: {
    "Content-Type": "application/json",
  },
});

// ✅ 요청 인터셉터 (세션 기반이므로 토큰 불필요)
api.interceptors.request.use(
  (config) => {
    // 세션은 Cookie로 자동 전송됨
    return config;
  },
  (error) => Promise.reject(error)
);

// ✅ 응답 인터셉터 (에러 공통 처리)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error("🚨 API 오류:", error);
    if (error.response?.status === 401) {
      alert("로그인이 필요합니다.");
    }
    return Promise.reject(error);
  }
);

export default api;
