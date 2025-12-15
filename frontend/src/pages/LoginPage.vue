<template>
  <div class="login-page">
    <div class="login-container">
        <div class="title-wrapper">
            <h1 class="title">R E M O N</h1>
            <p class="subtitle">Regulation Monitoring AI System</p>
        </div>

        <div class="login-floating">
            
            <div class="segmented-control">
                <input type="radio" id="user" value="user" v-model="userType">
                <label for="user">General User</label>

                <input type="radio" id="admin" value="admin" v-model="userType">
                <label for="admin">Admin</label>

                <div class="selection-indicator" :class="userType"></div>
            </div>

            <div class="input-group">
                <label for="ID" class="label">ID</label>
                <input
                id="ID"
                type="text"
                placeholder="Enter your ID"
                v-model="ID"
                @keyup.enter="focusPassword"
                autocomplete="off"  
                />
            </div>

            <div class="input-group">
                <label for="password" class="label">Password</label>
                <input
                id="password"
                type="password"
                placeholder="Enter your password"
                v-model="password"
                @keyup.enter="login"
                ref="passwordInput"  
                />
            </div>


            <button class="login-btn" @click="login">
                <span class="btn-text">ACCESS SYSTEM</span>
            </button>

        </div>
    </div>

  </div>
</template>

<script setup>
import { Spring_Api } from "@/services/api";
import { nextTick, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

// 선택된 사용자 타입
const userType = ref("user");

// 입력값
const ID = ref("");
const password = ref("");

// ⭐ password input ref
const passwordInput = ref(null);

// ⭐ Username에서 엔터 시 → Password로 포커스 이동
const focusPassword = async () => {
  await nextTick();
  passwordInput.value?.focus();
};

// 로그인 처리
const login = async () => {
  if (!ID.value || !password.value) {
    alert("아이디와 비밀번호를 입력해주세요.");
    return;
  }

  try {
    const res = await Spring_Api.post('/auth/login', {
      username: ID.value,
      password: password.value,
    });

    const userId = res.data.userId;
    const isAdmin = userId === 1;

    // UI에서 선택한 타입과 실제 권한 비교
    if (userType.value === 'admin' && !isAdmin) {
      alert('관리자 계정이 아닙니다.');
      await Spring_Api.post('/auth/logout');
      return;
    }

    if (userType.value === 'user' && isAdmin) {
      alert('일반 사용자로 로그인해주세요.');
      await Spring_Api.post('/auth/logout');
      return;
    }

    // 권한 저장
    localStorage.setItem('user_role', userType.value);
    router.push('/main');

  } catch (err) {
    if (err.response?.status === 401) {
      alert('아이디 또는 비밀번호가 올바르지 않습니다.');
    } else {
      alert('서버 오류가 발생했습니다.');
    }
  }
};
</script>

<style scoped>
/* 색상 변수 */
:root {
  --color-accent: #FDFF78; /* 포인트 색상: REMON 제목, 버튼 */
  --color-primary: #88C0D0; /* 보조 강조색: 지구본, 인풋 포커스 */
  --color-dark-bg: #040E1B; 
  --color-mid-bg: #0A192F; 
  --color-text: #E5E9F0;
  --color-white-glow: rgba(255, 255, 255, 0.12); /* 로그인 창 화이트 글로우 색상 */
}

.login-page {
  width: 100%;
  height: 100vh;
  position: relative;
  background: linear-gradient(180deg, var(--color-mid-bg) 0%, var(--color-dark-bg) 100%) !important;
  overflow: hidden;
  display: flex;
  justify-content: center;
  align-items: center;
}

.login-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    position: relative;
    z-index: 10; 
}

.title-wrapper { margin-bottom: 40px; text-align: center; }

.title {
  font-size: 58px; 
  color:#FDFF78;
  /* color: var(--color-accent); REMON 글자 색상 */
  letter-spacing: 14px; 
  font-weight: 800;
  /* 글로우 효과 유지 */
  text-shadow: 0 0 12px rgba(253, 255, 120, 0.7); 
}

.subtitle {
  margin-top: 8px;
  color: var(--color-primary); 
  font-size: 16px;
  font-weight: 300;
  letter-spacing: 2px;
}

/* ----------- 로그인 UI ----------- */

.login-floating {
    width: 380px;
    padding: 30px;
    border-radius: 12px;
    
    background: rgba(255, 255, 255, 0.08); 
    border: none;
    backdrop-filter: blur(12px);
    
    /* 로그인 창 글로우 효과 색상 수정 */
    box-shadow: 0 0 30px var(--color-white-glow), /* 흰색 계열 글로우 */
                0 10px 40px 0 rgba(0, 0, 0, 0.6); /* 하단 그림자 유지 */

    display: flex;
    flex-direction: column;
    gap: 15px; 
}

/* 사용자 타입 선택 (Segmented Control 스타일) */
.segmented-control {
  position: relative;
  display: flex;
  width: 100%;
  padding: 4px;
  border-radius: 10px;

  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.15);

  backdrop-filter: blur(10px);
  user-select: none;
  margin-bottom: 16px;
}

.segmented-control input {
  display: none;
}

.segmented-control label {
  flex: 1;
  text-align: center;
  padding: 8px 0;
  font-size: 14px;
  color: rgba(255,255,255,0.55);
  cursor: pointer;
  z-index: 2;
  transition: color 0.25s ease;
}

.segmented-control input:checked + label {
  color: #cccccc;
  font-weight: 600;
}

/* ⭐ 토글 인디케이터 */
.selection-indicator {
  position: absolute;
  top: 4px;
  left: 4px;
  width: calc(50% - 4px);
  height: calc(100% - 8px);

  /* ✔ 더 연하고 은은한 골드 tone */
  background: rgba(255, 255, 255, 0.12);
  border-radius: 8px;

  /* ✔ 글로우도 더 부드럽게 */
  box-shadow:
    0 0 6px rgba(253, 255, 120, 0.18),
    0 0 3px rgba(253, 255, 120, 0.10) inset;

  backdrop-filter: blur(2px); /* ✔ glass 느낌 */
  transition: transform 0.25s ease, background 0.25s ease;
}

/* ⭐ 토글 이동 애니메이션 */
.selection-indicator.admin {
  transform: translateX(100%);
}

.selection-indicator.user {
  transform: translateX(0%);
}

/* Input Group */
.input-group { 
    display: flex; 
    flex-direction: column; 
    gap: 6px; 
    margin-bottom: 5px; 
}

.label { 
    font-size: 14px; 
    color: var(--color-text); 
    opacity: 0.8; 
    font-weight: 500; 
}

/* 투명 글라스 input */
.login-floating input {
    padding: 14px 16px;
    background: rgba(255, 255, 255, 0.05);
    border: none; 
    color: #ffffff;
    border-radius: 8px;
    font-size: 16px;
    outline: none;
    transition: 0.3s;
}

.login-floating input:focus {
    border: 1px solid var(--color-primary); 
    box-shadow: 0 0 8px rgba(136, 192, 208, 0.8);
    background: rgba(255, 255, 255, 0.1);
}

.login-floating input::placeholder {
  color: rgba(255, 255, 255, 0.45);
}

/* 로그인 버튼 */
.login-btn {
    position: relative;
    margin-top: 15px;
    padding: 14px 0;
    border-radius: 8px;

    background: var(--color-accent); 
    border: none;
    
    color: var(--color-mid-bg); 
    font-weight: 700;
    font-size: 16px;
    letter-spacing: 1px;

    cursor: pointer;
    transition: all 0.3s ease;
    
    box-shadow: 0 0 15px rgba(107, 107, 93, 0.7);
}

.login-btn:hover {
    box-shadow: 0 0 20px rgb(140, 141, 129), 
                0 0 40px rgba(118, 118, 94, 0.4);
    transform: translateY(-2px);
}
</style>