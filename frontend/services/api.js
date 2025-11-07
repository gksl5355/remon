export async function checkHealthAPI() {
  try {
    const res = await fetch('http://localhost:8000/health/')
    return await res.json()
  } catch (e) {
    console.error('서버 연결 실패:', e)
    return { status: 'error' }
  }
}
