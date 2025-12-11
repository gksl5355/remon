<template>
  <div
    class="fixed inset-0 bg-black/50 backdrop-blur-sm flex justify-center items-center z-50"
    @click="close"
  >
    <div
      class="w-[450px] p-6 rounded-xl relative overflow-hidden modal-surface border border-white/10 shadow-2xl"
      @click.stop
    >
      <!-- Top gradient -->
      <div
        class="absolute top-0 left-0 w-full h-[4px]
        bg-gradient-to-r from-[#3A4F7A] via-[#748BB7] to-[#E8C663] opacity-80"
      />

      <h2 class="text-gray-200 text-lg font-semibold mb-6 tracking-wide">
        {{ mode === 'add' ? 'Crawling 추가' : 'Crawling 수정' }}
      </h2>

      <!-- Country -->
      <label class="label">국가</label>
      <select v-model="form.country" class="input">
        <option value="">국가 선택</option>
        <option v-for="c in countries" :key="c" :value="c">
          {{ c }}
        </option>
      </select>

      <!-- Type -->
      <label class="label">유형</label>
      <select v-model="form.type" class="input">
        <option value="">유형 선택</option>
        <option value="reg">Regulation</option>
        <option value="news">News</option>
      </select>

      <!-- REQUIRED: Domain -->
      <label class="label">사이트 도메인 <span class="text-red-400">*</span></label>
      <input
        class="input"
        v-model="form.domain"
        placeholder="예: www.gov.us/regulations"
      />
      <p v-if="errors.domain" class="text-red-400 text-[11px] mt-1">{{ errors.domain }}</p>

      <!-- REQUIRED: Keywords -->
      <label class="label mt-4">
        키워드 <span class="text-red-400">*</span>
      </label>
      <input
        class="input"
        v-model="keywordInput"
        placeholder="키워드 입력 후 Enter"
        @keyup.enter="addKeyword"
      />

      <p v-if="errors.keywords" class="text-red-400 text-[11px] mt-1">{{ errors.keywords }}</p>

      <div class="flex flex-wrap gap-2 mt-2 mb-4">
        <span
          v-for="(k, idx) in form.keywords"
          :key="idx"
          class="px-2 py-0.5 text-[11px] rounded-md bg-white/10 border border-white/10 text-gray-200 flex items-center gap-1"
        >
          #{{ k }}
          <button class="text-red-300" @click="removeKeyword(idx)">×</button>
        </span>
      </div>

      <!-- OPTIONAL SECTION -->
      <div class="mt-6 pt-4 border-t border-white/10">
        <p class="text-[12px] text-gray-400 mb-3">추가 옵션 (선택)</p>

        <!-- Format -->
        <label class="label">문서 포맷</label>
        <select v-model="form.format" class="input">
          <option value="">선택 안함</option>
          <option value="pdf">PDF</option>
          <option value="html">HTML</option>
        </select>

        <!-- Date -->
        <label class="label">기준 날짜</label>
        <input
          type="date"
          v-model="form.date"
          class="input"
        />

      </div>

      <!-- Buttons -->
      <div class="flex justify-end gap-3 mt-8">
        <button
          class="px-4 py-1.5 rounded-md text-xs border border-white/20 text-gray-300 hover:bg-white/10"
          @click="close"
        >
          취소
        </button>

        <button
          class="px-4 py-1.5 rounded-md text-xs font-semibold
                 bg-gradient-to-b from-[#FFE27A] to-[#E9C757]
                 text-black hover:brightness-105"
          @click="saveForm"
        >
          {{ mode === 'add' ? '추가하기' : '수정하기' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, watch } from "vue";

const props = defineProps({
  mode: { type: String, default: "add" },
  initialData: { type: Object, default: null }
});
const emit = defineEmits(["close", "save"]);

const close = () => emit("close");

const countries = ["US", "RU", "ID", "JP"];

/* 폼 기본 값 */
const form = reactive({
  id: null,
  country: "",
  type: "",
  domain: "",
  format: "",
  date: "",
  targetUrl: "",
  keywords: []
});

const errors = reactive({
  domain: "",
  keywords: ""
});

const keywordInput = ref("");

/* Edit mode 초기값 */
watch(
  () => props.initialData,
  (val) => {
    if (val) {
      Object.assign(form, val);
    }
  },
  { immediate: true }
);

/* Keyword 추가 */
function addKeyword() {
  const k = keywordInput.value.trim();
  if (!k) return;
  form.keywords.push(k);
  keywordInput.value = "";
}

/* Keyword 삭제 */
function removeKeyword(idx) {
  form.keywords.splice(idx, 1);
}

/* 필수값 검증 */
function validate() {
  errors.domain = form.domain.trim() ? "" : "사이트 도메인은 필수입니다.";
  errors.keywords = form.keywords.length ? "" : "키워드는 최소 1개 이상 입력해야 합니다.";
  errors.country = form.country ? "" : "국가는 필수입니다.";
  errors.type = form.type ? "" : "유형은 필수입니다.";

  return !errors.domain && !errors.keywords && !errors.country && !errors.type;
}

/* 저장 */
function saveForm() {
  if (!validate()) return;

  emit("save", { ...form });
  emit("close");
}
</script>

<style scoped>
.modal-surface {
  background: rgba(13, 21, 35, 0.97);
}
.label {
  font-size: 12px;
  color: #cbd3e1;
  margin-top: 12px;
  margin-bottom: 4px;
}
.input {
  width: 100%;
  background: #111a28;
  border: 1px solid #3a4457;
  padding: 8px 12px;
  border-radius: 8px;
  color: #dce3ee;
  font-size: 13px;
}
input[type="date"]::-webkit-calendar-picker-indicator {
  filter: invert(1) brightness(1.4);
  cursor: pointer;
}

</style>
