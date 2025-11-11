import { ref } from "vue";

export const isLoggedIn = ref(false);

export function login() {
  isLoggedIn.value = true;
  localStorage.setItem("loggedIn", "true"); // (선택) 새로고침 유지용
}

export function logout() {
  isLoggedIn.value = false;
  localStorage.removeItem("loggedIn");
}
