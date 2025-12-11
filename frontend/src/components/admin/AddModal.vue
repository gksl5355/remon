<template>
  <!-- 오버레이 (배경 클릭 시 닫힘) -->
  <div
    class="fixed inset-0 bg-black/50 backdrop-blur-sm flex justify-center items-center z-50"
    @click="closeModal"
  >
    <!-- 팝업 컨테이너 (내부 클릭 시 닫히지 않음) -->
    <div
      class="w-[420px] p-6 rounded-xl relative overflow-hidden modal-surface border border-white/10 shadow-2xl"
      @click.stop
    >
      <!-- 상단 그라데이션 라인 -->
      <div
        class="absolute top-0 left-0 w-full h-[4px] 
        bg-gradient-to-r from-[#3A4F7A] via-[#748BB7] to-[#E8C663] opacity-80"
      ></div>

      <h2 class="text-gray-200 text-lg font-semibold mb-6 tracking-wide">
        파일 추가
      </h2>

      <!-- Country -->
      <label class="label">국가</label>
      <select v-model="form.country" class="input">
        <option value="">국가 선택</option>
        <option v-for="c in countries" :key="c">{{ c }}</option>
      </select>

      <!-- Type -->
      <label class="label">파일 종류</label>
      <select v-model="form.type" class="input">
        <option value="">유형 선택</option>
        <option value="report">AI Report</option>
      </select>

      <!-- Upload -->
      <label class="label">파일 업로드</label>
      <input type="file" @change="onFile" class="input file-input" />

      <!-- Buttons -->
      <div class="flex justify-end gap-3 mt-7">
        <button
          class="px-4 py-1.5 rounded-md text-xs border border-white/20 
                 text-gray-300 hover:bg-white/10 transition"
          @click="$emit('close')"
        >
          취소
        </button>

        <button
          class="px-4 py-1.5 rounded-md text-xs font-semibold 
                  bg-[#FDFF78]
                  text-black shadow-[0_0_5px_rgba(233,199,87,0.4)]
                  hover:shadow-[0_0_18px_rgba(233,199,87,0.6)]
                  hover:brightness-105 transition-all"
          @click="save"
        >
          추가하기
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive } from "vue";

const emit = defineEmits(["close", "save"]);

function closeModal() {
  emit("close");      // ⭐ 오버레이 클릭 → 모달 닫힘
}

const countries = ["US", "RU", "ID"];
const products = ["Heated Tobacco", "E-Cigarette", "Cigarette"];

const form = reactive({
  country: "",
  type: "",
  product: "Heated Tobacco",
  name: ""
});

function onFile(e) {
  const file = e.target.files?.[0];
  if (file) form.name = file.name;
}

function save() {
  if (!form.name) return alert("파일을 업로드해주세요.");
  emit("save", { ...form });
  emit("close");
}
</script>

<style scoped>
.modal-surface {
  background: rgba(13, 21, 35, 0.9);
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
}

.label {
  font-size: 12px;
  color: #cbd3e1;
  margin-top: 12px;
  margin-bottom: 4px;
  display: block;
  letter-spacing: 0.3px;
}

.input {
  width: 100%;
  background: #111a28;
  border: 1px solid #3a4457;
  padding: 8px 12px;
  border-radius: 8px;
  color: #dce3ee;
  font-size: 13px;
  transition: 0.15s;
}

.input:hover {
  border-color: #4e5a72;
}

.input:focus {
  outline: none;
  border-color: #748bb7;
  background: #131d30;
}

.file-input {
  padding: 6px 10px !important;
}
</style>
