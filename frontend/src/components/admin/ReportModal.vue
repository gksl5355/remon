<template>
  <div
    class="fixed inset-0 bg-black/50 backdrop-blur-sm flex justify-center items-center z-50"
    @click="close"
  >
    <div
      class="w-[760px] max-h-[85vh] overflow-y-auto rounded-2xl p-0 shadow-2xl modal-surface border border-white/10"
      @click.stop
    >
      <!-- HEADER -->
      <div
        class="p-5 border-b border-white/10 flex justify-between items-center bg-[#0F1A2C]/90 rounded-t-2xl relative"
      >
        <div>
          <h2 class="text-[18px] text-gray-100 font-semibold">AI Report 상세</h2>
          <p class="text-[12px] text-gray-400 mt-1">규제 요약 · 분석 · 전략 · 영향도</p>
        </div>

        <button
          @click="toggleEdit"
          :class="[
            'px-4 py-1.5 text-xs rounded-md transition shadow-md flex items-center gap-1',
            'border border-white/20 backdrop-blur-sm',
            isEditing
              ? 'bg-green-500/20 text-green-200 hover:bg-green-500/30'    // 저장하기 상태 (초록)
              : 'bg-yellow-300/20 text-yellow-200 hover:bg-yellow-300/30' // 수정하기 상태 (노랑)
          ]"
        >
          <span v-if="isEditing">저장하기</span>
          <span v-else>수정하기</span>
        </button>
      </div>

      <!-- BODY -->
      <div class="p-6 space-y-7">

        <!-- SUMMARY -->
        <section>
          <h3 class="section-title">Summary</h3>

          <div class="card">
            <div class="grid grid-cols-2 gap-4">
              <div>
                <p class="field-label">Country</p>
                <input class="input" v-model="local.summary.country" :disabled="!isEditing" />
              </div>

              <div>
                <p class="field-label">Category</p>
                <input class="input" v-model="local.summary.category" :disabled="!isEditing" />
              </div>
            </div>

            <div class="mt-4">
              <p class="field-label">Regulation Summary</p>
              <textarea class="textarea" v-model="local.summary.regulationSummary" :disabled="!isEditing" />
            </div>

            <div class="grid grid-cols-2 gap-4 mt-4">
              <div>
                <p class="field-label">Impact</p>
                <input class="input" v-model="local.summary.impact" :disabled="!isEditing" />
              </div>

              <div>
                <p class="field-label">Recommendation</p>
                <textarea class="textarea" v-model="local.summary.recommendation" :disabled="!isEditing" />
              </div>
            </div>
          </div>
        </section>

        <!-- PRODUCTS -->
        <section>
          <h3 class="section-title">Products</h3>

          <div class="card divide-y divide-white/10">
            <div
              v-for="(p, idx) in local.products"
              :key="idx"
              class="py-3"
            >
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <p class="field-label">Item</p>
                  <input class="input" v-model="p.item" :disabled="!isEditing" />
                </div>
                <div>
                  <p class="field-label">Product</p>
                  <input class="input" v-model="p.product" :disabled="!isEditing" />
                </div>
              </div>

              <div class="grid grid-cols-2 gap-4 mt-4">
                <div>
                  <p class="field-label">Current</p>
                  <input class="input" v-model="p.current" :disabled="!isEditing" />
                </div>
                <div>
                  <p class="field-label">Required</p>
                  <input class="input" v-model="p.required" :disabled="!isEditing" />
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- CHANGE ANALYSIS -->
        <section>
          <h3 class="section-title">Change Analysis</h3>
          <div class="card">
            <textarea class="textarea h-28" v-model="analysisString" :disabled="!isEditing"></textarea>
          </div>
        </section>

        <!-- STRATEGY -->
        <section>
          <h3 class="section-title">Strategy</h3>
          <div class="card">
            <textarea class="textarea h-28" v-model="strategyString" :disabled="!isEditing"></textarea>
          </div>
        </section>

        <!-- IMPACT REASON -->
        <section>
          <h3 class="section-title">Impact Reason</h3>
          <div class="card">
            <textarea class="textarea h-28" v-model="local.impactReason" :disabled="!isEditing"></textarea>
          </div>
        </section>

        <!-- REFERENCES -->
        <section>
          <h3 class="section-title">References</h3>
          <div class="card space-y-4">
            <div v-for="(ref, i) in local.references" :key="i">
              <p class="field-label">Name</p>
              <input class="input" v-model="ref.name" :disabled="!isEditing" />

              <p class="field-label mt-3">URL</p>
              <input class="input" v-model="ref.url" :disabled="!isEditing" />
            </div>
          </div>
        </section>

      </div> <!-- BODY 끝 -->

    </div> <!-- MODAL 끝 -->
  </div> <!-- BACKDROP 끝 -->
</template>

<script setup>
import { computed, reactive, ref } from "vue";

const props = defineProps({
  data: { type: Object, required: true },
});
const emit = defineEmits(["close", "save"]);

const isEditing = ref(false);

// 로컬 복사본 유지
const local = reactive(JSON.parse(JSON.stringify(props.data)));

function toggleEdit() {
  // 저장하기 클릭 시
  if (isEditing.value) {
    emit("save", local);

    // 저장 후 수정모드 종료
    isEditing.value = false;
    return;
  }

  // 수정하기 클릭 시 → 편집 모드 ON
  isEditing.value = true;
};

// computed 리스트 형태 변환
const analysisString = computed({
  get: () => local.changeAnalysis.join("\n"),
  set: (v) => (local.changeAnalysis = v.split("\n")),
});

const strategyString = computed({
  get: () => local.strategy.join("\n"),
  set: (v) => (local.strategy = v.split("\n")),
});

function close() {
  emit("close");
};

</script>

<style scoped>
.modal-surface {
  background: rgba(13, 21, 35, 0.95);
}

.section-title {
  font-size: 14px;
  color: #e4e9f2;
  font-weight: 600;
  margin-bottom: 8px;
}

.card {
  background: #101a2b;
  border: 1px solid #243044;
  padding: 16px;
  border-radius: 10px;
}

.field-label {
  font-size: 12px;
  color: #8fa0b9;
  margin-bottom: 4px;
}

.input,
.textarea {
  width: 100%;
  background: #0d1422;
  border: 1px solid #3a4457;
  padding: 8px 10px;
  border-radius: 6px;
  color: #dce3ee;
  font-size: 13px;
}

.input:disabled,
.textarea:disabled {
  opacity: 0.6;
}
</style>
