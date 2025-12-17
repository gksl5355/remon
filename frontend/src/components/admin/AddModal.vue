<template>
  <!-- 오버레이 -->
  <div
    class="fixed inset-0 bg-black/50 backdrop-blur-sm flex justify-center items-center z-50"
    @click="closeModal"
  >
    <!-- 팝업 컨테이너 -->
    <div
      class="w-[420px] p-6 rounded-xl relative overflow-hidden modal-surface border border-white/10 shadow-2xl"
      @click.stop
    >
      <!-- 상단 라인 -->
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
        <option value="reg">Regulation</option>
        <option value="report">AI Report</option>
      </select>

      <!-- Upload -->
      <label class="label">파일 업로드</label>

      <!-- ⭐ 완전한 안정형 파일 업로드 UI -->
      <label class="input flex justify-between items-center cursor-pointer">
        <span class="text-gray-400">
          {{ form.name || "업로드할 파일 선택" }}
        </span>

        <input
          type="file"
          class="hidden"
          @change="onFile"
        />
      </label>

      <!-- Buttons -->
      <div class="flex justify-end gap-3 mt-7">
        <button
          class="px-4 py-1.5 rounded-md text-xs border border-white/20 
                 text-gray-300 hover:bg-white/10 transition"
          @click="closeModal"
        >
          취소
        </button>

        <button
          class="px-4 py-1.5 rounded-md text-xs font-semibold 
                  bg-[#FDFF78] text-black shadow-[0_0_5px_rgba(233,199,87,0.4)]
                  hover:shadow-[0_0_18px_rgba(233,199,87,0.6)]
                  hover:brightness-105 transition-all disabled:opacity-50"
          :disabled="loading"
          @click="uploadFile"
        >
          {{ loading ? "업로드 중..." : "추가하기" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import api from "@/services/api";
import { reactive, ref } from "vue";

const emit = defineEmits(["close", "save"]);
const loading = ref(false);

const countries = ["US", "RU", "ID"];

const form = reactive({
  country: "",
  type: "",
  file: null,
  name: ""
});

/* ---------------------------------
   파일 선택
----------------------------------- */
function onFile(e) {
  const file = e.target.files?.[0];

  console.log("📌 선택된 파일:", file);

  if (file) {
    form.file = file;
    form.name = file.name;
  }
}

/* ---------------------------------
   업로드 실행
----------------------------------- */
async function uploadFile() {
  if (!form.country) return alert("국가를 선택해주세요.");
  if (!form.type) return alert("파일 종류를 선택해주세요.");
  if (!form.file) return alert("파일을 업로드해주세요.");

  loading.value = true;

  try {
    const fd = new FormData();
    fd.append("file", form.file);
    fd.append("file_type", form.type);
    fd.append("country", form.country);

    // 디버깅 로그
    console.log("📤 업로드 직전 FormData:");
    console.log(" - file:", fd.get("file"));
    console.log(" - file_type:", fd.get("file_type"));
    console.log(" - country:", fd.get("country"));

    const res = await api.post("/admin/s3/upload", fd);

    if (res.data.status !== "success") {
      throw new Error(res.data.detail || "업로드 실패");
    }

    if (!res.data.s3_key && !res.data.key) {
      throw new Error("업로드 응답에 s3_key가 없습니다.");
    }

    // 부모로 전달 (FileDataPanel.vue에서 리스트 갱신)
    emit("save", {
      name: form.name,
      country: form.country,
      type: form.type,
      s3_key: res.data.s3_key || res.data.key,
      date: new Date().toISOString().split("T")[0]
    });

    emit("close");

  } catch (err) {
    console.error("❌ 업로드 오류:", err);
    alert("업로드 중 오류가 발생했습니다.");
  } finally {
    loading.value = false;
  }
}

/* ---------------------------------
   모달 닫기
----------------------------------- */
function closeModal() {
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
</style>
