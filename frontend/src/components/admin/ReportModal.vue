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
        class="p-5 border-b border-white/10 flex justify-between items-center bg-[#0F1A2C]/90 rounded-t-2xl"
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
              ? 'bg-green-500/20 text-green-200 hover:bg-green-500/30'
              : 'bg-yellow-300/20 text-yellow-200 hover:bg-yellow-300/30'
          ]"
        >
          {{ isEditing ? "저장하기" : "수정하기" }}
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
              <textarea
                class="textarea"
                v-model="local.summary.regulationSummary"
                :disabled="!isEditing"
              />
            </div>

            <div class="grid grid-cols-2 gap-4 mt-4">
              <div>
                <p class="field-label">Impact</p>
                <input class="input" v-model="local.summary.impact" :disabled="!isEditing" />
              </div>
              <div>
                <p class="field-label">Recommendation</p>
                <textarea
                  class="textarea"
                  v-model="local.summary.recommendation"
                  :disabled="!isEditing"
                />
              </div>
            </div>
          </div>
        </section>

        <!-- PRODUCTS -->
        <section>
          <h3 class="section-title">Products</h3>
          <div class="card divide-y divide-white/10">
            <div v-for="(p, idx) in local.products" :key="idx" class="py-3">
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
            <textarea class="textarea h-28" v-model="analysisString" :disabled="!isEditing" />
          </div>
        </section>

        <!-- STRATEGY -->
        <section>
          <h3 class="section-title">Strategy</h3>
          <div class="card">
            <textarea class="textarea h-28" v-model="strategyString" :disabled="!isEditing" />
          </div>
        </section>

        <!-- IMPACT REASON -->
        <section>
          <h3 class="section-title">Impact Reason</h3>
          <div class="card">
            <textarea
              class="textarea h-28"
              v-model="local.impactReason"
              :disabled="!isEditing"
            />
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

      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from "vue";

/* ===============================
   DEMO DATA (내장)
================================ */
const demoData = {
  summary: {
    country: "미국 (US)",
    category: "니코틴 제품 규제",
    regulationSummary:
      "미국 FDA는 청소년 사용 감소를 목적으로 향이 첨가된 전자담배 제품에 대해 니코틴 함량 상한을 강화하는 규제 개정안을 발표했습니다.",
    impact: "높음",
    recommendation:
      "대상 제품의 니코틴 함량을 기준치 이하로 조정하고, 관련 라벨링 및 인증 문서를 사전에 준비할 필요가 있습니다."
  },

  products: [
    {
      item: "니코틴 함량",
      product: "향 첨가 전자담배",
      current: "5%",
      required: "2% 이하"
    },
    {
      item: "건강 경고 표시",
      product: "일회용 베이프",
      current: "텍스트 경고 문구",
      required: "그래픽 건강 경고 이미지"
    }
  ],

  changeAnalysis: [
    "전자담배 제품에 허용되는 니코틴 함량 기준이 대폭 하향 조정되었습니다.",
    "향이 포함된 제품은 추가적인 규제 및 심사 대상이 됩니다.",
    "기준 미충족 시 판매 제한 또는 시장 철수 가능성이 존재합니다."
  ],

  strategy: [
    "매출 비중이 높은 주요 제품군을 우선적으로 개편합니다.",
    "규제 전문 컨설턴트와 협업하여 컴플라이언스 검증을 진행합니다.",
    "단기적으로는 기존 재고 처리 및 중장기 대체 제품 전략을 병행합니다."
  ],

  impactReason:
    "본 규제는 제품의 핵심 사양에 직접적인 영향을 미치며, 미국 시장 내 유통 가능 여부에 중대한 변화를 초래할 수 있습니다.",

  references: [
    {
      name: "미국 FDA 담배 제품 규제 공지",
      url: "https://www.fda.gov/tobacco-products"
    },
    {
      name: "연방 관보 규제 개정안",
      url: "https://www.federalregister.gov"
    }
  ]
};

/* ===============================
   STATE
================================ */
const isEditing = ref(false);
const local = reactive(JSON.parse(JSON.stringify(demoData)));
const emit = defineEmits(["close"]);

/* ===============================
   COMPUTED
================================ */
const analysisString = computed({
  get: () => local.changeAnalysis.join("\n"),
  set: (v) => (local.changeAnalysis = v.split("\n"))
});

const strategyString = computed({
  get: () => local.strategy.join("\n"),
  set: (v) => (local.strategy = v.split("\n"))
});

/* ===============================
   METHODS
================================ */
function toggleEdit() {
  if (isEditing.value) {
    console.log("저장된 데이터 (demo):", local);
    isEditing.value = false;
  } else {
    isEditing.value = true;
  }
}

function close() {
  emit("close"); // ⭐ 실제로 모달 닫기
}
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

/* ===== Custom Scrollbar (Modal Body) ===== */
.modal-surface::-webkit-scrollbar {
  width: 6px;
}

.modal-surface::-webkit-scrollbar-track {
  background: transparent;
}

.modal-surface::-webkit-scrollbar-thumb {
  background: rgba(180, 200, 255, 0.18);
  border-radius: 9999px;
}

.modal-surface::-webkit-scrollbar-thumb:hover {
  background: rgba(180, 200, 255, 0.32);
}

/* Firefox */
.modal-surface {
  scrollbar-width: thin;
  scrollbar-color: rgba(180,200,255,0.25) transparent;
}

.textarea {
  line-height: 1.6;
}

.input:not(:disabled),
.textarea:not(:disabled) {
  border-color: #22446a;
  background: #0f1a2c;
}
</style>
