// 📁 src/services/api.js
import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000/api", // ✅ FastAPI 기본 엔드포인트
  // baseURL: "http://172.25.155.179:8000/api", //또는 본인 ip 주소
  timeout: 5000, // 5초 타임아웃
  headers: {
    "Content-Type": "application/json",
  },
});

// ✅ 요청 인터셉터 (예: JWT 토큰 자동 첨부)
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
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
