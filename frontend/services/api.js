import axios from 'axios';

export async function checkHealthAPI() {
  try {
    const res = await fetch('http://localhost:8000/health/')
    return await res.json()
  } catch (e) {
    console.error('서버 연결 실패:', e)
    return { status: 'error' }
  }
}


// ==========================================
// 2. [신규] 크롤링 API (Spring Boot - Port 8081)
// ==========================================
const CRAWL_API_BASE_URL = 'http://localhost:8081/api/crawl';

// 크롤링 전용 Axios 인스턴스
const crawlClient = axios.create({
  baseURL: CRAWL_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// crawlApi라는 이름으로 묶어서 내보냅니다.
export const crawlApi = {
  // 타겟 목록 조회 (GET)
  getTargets() {
    return crawlClient.get('/targets');
  },

  // 타겟 추가 (POST)
  addTarget(data) {
    return crawlClient.post('/targets', data);
  },

  // 타겟 수정 (PATCH)
  updateTarget(id, data) {
    return crawlClient.patch(`/targets/${id}`, data);
  },

  // 타겟 삭제 (DELETE)
  deleteTarget(id) {
    return crawlClient.delete(`/targets/${id}`);
  },

  // 상태 변경 (활성/비활성)
  updateStatus(id, enabled) {
    return crawlClient.patch(`/targets/${id}/status`, null, {
      params: { enabled }
    });
  },

  // 크롤링 실행 (버저닝 모드)
  runBatchCrawling() {
    return crawlClient.post('/run-batch/versioning');
  }
};