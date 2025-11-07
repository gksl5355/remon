export function useDashboard() {
  const refreshData = () => console.log('대시보드 데이터 새로고침')
  return { refreshData }
}
