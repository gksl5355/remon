export function useAuth() {
  const login = (id, pw) => console.log(\`로그인 시도: \${id}\`)
  const logout = () => console.log('로그아웃')
  return { login, logout }
}
