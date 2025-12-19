<template>
  <div
    class="rounded-xl bg-[#0B1220]/80 border border-gray-700/30 shadow-md flex flex-col relative overflow-hidden"
    style="height: 70vh"
  >
    <!-- LEFT GRADIENT LINE -->
    <div
      class="absolute left-0 top-0 h-full w-[4px]"
      style="
        background: linear-gradient(
          to bottom,
          rgb(45, 56, 74),
          rgba(111,133,168,0.12),
          rgba(11, 18, 32, 0)
        );
      "
    ></div>

    <!-- HEADER -->
    <div
      class="flex items-center justify-between px-6 py-4"
      style="background: linear-gradient(to right, rgba(45,56,74), rgba(111,133,168,0.15)); backdrop-filter: blur(6px);"
    >
      <h2 class="text-lg font-bold text-white tracking-wide">REGULATION AI REPORT</h2>

      <div class="flex items-center gap-2">
        <button
          @click="openModal"
          class="px-3 py-1.5 rounded-md text-xs border border-white/20 bg-white/5 hover:bg-white/10 text-[#E1EAF7]"
        >Human Validation</button>

        <button
          @click="downloadReport"
          class="px-3 py-1.5 rounded-md text-xs border border-white/10 hover:bg-white/5 text-[#DDE6F3]"
        >Download</button>
      </div>
    </div>

    <!-- CONTENT -->
    <div ref="scrollArea" class="flex-1 overflow-y-auto p-6 space-y-10 custom-scrollbar">

      <!-- No data -->
      <div v-if="!props.fileId" class="text-gray-500 text-center py-20">
        리포트를 불러오는 중...
      </div>

      <!-- LOADING -->
      <div v-else-if="isLoading"
           class="flex flex-col items-center justify-center h-full text-gray-400 space-y-3">
        <div class="w-10 h-10 border-4 border-gray-500 border-t-transparent rounded-full animate-spin"></div>
        <p>AI 모델이 Human Feedback을 반영 중...</p>
      </div>

      <!-- ============================= -->
      <!-- BASIC REPORT MODE (NOT STREAM) -->
      <!-- ============================= -->
      <div v-else-if="!isStreaming && baseSection1">

        <!-- SECTION 0 -->
        <section>
          <h3 class="sec-title">0. 종합 요약</h3>

          <p class="text-gray-300 whitespace-pre-line">
            {{ baseOverall }}
          </p>
        </section>

        <!-- SECTION 1 -->
        <section>
          <h3 class="sec-title">1. 규제 변경 요약</h3>

          <p class="text-gray-300 whitespace-pre-line">
            {{ baseSection1 }}
          </p>
        </section>

        <!-- SECTION 2 -->
        <section class="mt-6">
          <h3 class="sec-title">2. 영향받는 제품 목록</h3>

          <table class="w-full text-left text-[13px] text-gray-300 border-collapse">
            <thead class="text-gray-400 border-b border-gray-600/40">
              <tr><th class="py-2">항목</th><th class="py-2">제품명</th><th class="py-2">조치</th></tr>
            </thead>

            <tbody>
              <tr v-for="(row, idx) in baseProducts" :key="idx" class="border-b border-gray-700/20">
                <td class="py-2">{{ row.item }}</td>
                <td class="py-2">{{ row.product }}</td>
                <td class="py-2">{{ row.action }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- SECTION 3 -->
        <section class="mt-6">
          <h3 class="sec-title">3. 주요 변경 사항 해석</h3>
          <ul class="list-disc pl-5 space-y-1 text-gray-300">
            <li v-for="(v,i) in baseAnalysis" :key="i">{{ v }}</li>
          </ul>
        </section>

        <!-- SECTION 4 -->
        <section class="mt-6">
          <h3 class="sec-title">4. 대응 전략</h3>
          <ul class="list-disc pl-5 space-y-1 text-gray-300">
            <li v-for="(v,i) in baseStrategy" :key="i">{{ v }}</li>
          </ul>
        </section>

        <!-- SECTION 5 -->
        <section class="mt-6">
          <h3 class="sec-title">5. 영향 평가 근거</h3>
          <p class="text-gray-300 whitespace-pre-line">{{ baseImpactReason }}</p>
        </section>

        <section class="mt-6">
          <h3 class="sec-title">6. 참고 및 원문 링크</h3>
          <p class="text-gray-300 whitespace-pre-line">{{ baseUrl }}</p>
        </section>

      </div>

      <!-- ========================== -->
      <!-- STREAMING MODE (TYPEWRITER) -->
      <!-- ========================== -->
      <div v-else-if="isStreaming">

        <!-- SECTION 0 (ONE TEXT STREAM) -->
        <section v-if="showSection0">
          <h3 class="sec-title">0. 종합 요약</h3>

          <p class="text-gray-300 whitespace-pre-line leading-relaxed">
            {{ streamedOverrall }}
            <span v-if="cursorAt === 'Overrall'" class="cursor">|</span>
          </p>
        </section>

        <!-- SECTION 1 (ONE TEXT STREAM) -->
        <section v-if="showSection1">
          <h3 class="sec-title">1. 규제 변경 요약</h3>

          <p class="text-gray-300 whitespace-pre-line leading-relaxed">
            {{ streamedSection1 }}
            <span v-if="cursorAt === 'section1'" class="cursor">|</span>
          </p>
        </section>

        <!-- SECTION 2 -->
        <section v-if="showSection2" class="mt-6">
          <h3 class="sec-title">2. 영향받는 제품 목록</h3>

          <table class="w-full text-left text-[13px] text-gray-300 border-collapse">
            <thead class="text-gray-400 border-b border-gray-600/40">
              <tr><th class="py-2">항목</th><th class="py-2">제품명</th><th class="py-2">조치</th></tr>
            </thead>

            <tbody>
              <tr v-for="(row, idx) in streamedProducts" :key="idx" class="border-b border-gray-700/20">
                <td class="py-2">{{ row.item }}</td>
                <td class="py-2">{{ row.product }}</td>
                <td class="py-2">
                  {{ row.action }}
                  <span v-if="cursorAt === 'products' && idx === streamedProducts.length - 1"
                        class="cursor">|</span>
                </td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- SECTION 3 -->
        <section v-if="showSection3" class="mt-6">
          <h3 class="sec-title">3. 주요 변경 사항 해석</h3>

          <ul class="list-disc pl-5 space-y-1 text-gray-300">
            <li v-for="(v,i) in streamedAnalysis" :key="i">
              {{ v }}
              <span v-if="cursorAt === 'analysis' && i === streamedAnalysis.length - 1"
                    class="cursor">|</span>
            </li>
          </ul>
        </section>

        <!-- SECTION 4 -->
        <section v-if="showSection4" class="mt-6">
          <h3 class="sec-title">4. 대응 전략</h3>

          <ul class="list-disc pl-5 space-y-1 text-gray-300">
            <li v-for="(v,i) in streamedStrategy" :key="i">
              {{ v }}
              <span v-if="cursorAt === 'strategy' && i === streamedStrategy.length - 1"
                    class="cursor">|</span>
            </li>
          </ul>
        </section>

        <!-- SECTION 5 -->
        <section v-if="showSection5" class="mt-6">
          <h3 class="sec-title">5. 영향 평가 근거</h3>

          <p class="text-gray-300 whitespace-pre-line">
            {{ streamedImpactReason }}
            <span v-if="cursorAt === 'impactReason'" class="cursor">|</span>
          </p>
        </section>

        <section v-if="showSection6" class="mt-6">
          <h3 class="sec-title">6. 참고 및 원문 링크</h3>

          <p class="text-gray-300 whitespace-pre-line">
            {{ streamedReferences }}
            <span v-if="cursorAt === 'references'" class="cursor">|</span>
          </p>
        </section>

      </div>
    </div>

    <!-- MODAL -->
    <div
      v-if="showModal"
      class="fixed inset-0 z-[999] flex items-center justify-center"
    >

      <!-- Dimmed background -->
      <div
        class="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        @click="showModal = false"
      ></div>

      <!-- MODAL CARD -->
      <div
        class="relative w-[480px] p-7 rounded-2xl shadow-2xl
              bg-[#0A0F19]/80 border border-white/10
              animate-modal-in"
        style="
          box-shadow: 0 0 35px rgba(0,0,0,0.55);
          backdrop-filter: blur(14px);
          background-image: linear-gradient(
            to bottom right,
            rgba(20, 28, 45, 0.65),
            rgba(8, 12, 22, 0.85)
          );
        "
      >

        <!-- Title -->
        <div class="flex items-center justify-between mb-6">
          <div class="flex items-center gap-2">
            <div
              class="w-2 h-2 rounded-full bg-[#FDFF78] shadow-[0_0_8px_#FDFF78]"
            ></div>
            <h3 class="text-[17px] font-semibold text-gray-100 tracking-wide">
              Human Validation
            </h3>
          </div>
        </div>

        <!-- Input -->
        <textarea
          v-model="hvInput"
          class="w-full h-40 resize-none rounded-xl
                bg-[#0D1523]/70 border border-white/10 text-gray-200 p-4 text-sm
                focus:outline-none focus:ring-2 focus:ring-[#FDFF78]/30
                placeholder-gray-500
                transition shadow-inner"
          placeholder="AI 출력에 대한 피드백을 입력해주세요."
        ></textarea>

        <!-- Divider -->
        <div class="my-6 border-t border-white/10"></div>

        <!-- BUTTONS -->
        <div class="flex justify-end gap-3">

          <!-- Cancel -->
          <button
            @click="showModal = false"
            class="px-4 py-1.5 rounded-lg text-sm 
                  bg-white/5 border border-white/10 
                  hover:bg-white/10 text-gray-300
                  transition shadow-sm"
          >
            Cancel
          </button>

          <!-- Re-run -->
          <button
            @click="runHV"
            class="px-5 py-1.5 text-sm rounded-lg font-semibold
                  bg-gradient-to-r from-[#FDFF78] to-[#D6D764] text-black
                  shadow-[0_4px_10px_rgba(253,255,120,0.35)]
                  hover:shadow-[0_6px_14px_rgba(253,255,120,0.45)]
                  transition-transform hover:-translate-y-0.5"
          >
            재실행
          </button>

        </div>

      </div>

    </div>

  </div>
</template>




<script setup>
import api from "@/services/api";
import { computed, ref, watch } from "vue";

/* AUTO SCROLL */
const scrollArea = ref(null);
let lastScroll = 0;

function autoScroll() {
  const now = Date.now();
  if (now - lastScroll < 35) return;
  lastScroll = now;
  if (scrollArea.value) {
    scrollArea.value.scrollTop = scrollArea.value.scrollHeight;
  }
}

/* STREAM VARIABLES */
const isStreaming = ref(false);

const streamedOverrall = ref("");
const streamedSection1 = ref("");
const streamedProducts = ref([]);
const streamedAnalysis = ref([]);
const streamedStrategy = ref([]);
const streamedImpactReason = ref("");
const streamedReferences = ref("");

const cursorAt = ref(null);

/* SECTION FLAGS */
const showSection0 = ref(false);
const showSection1 = ref(false);
const showSection2 = ref(false);
const showSection3 = ref(false);
const showSection4 = ref(false);
const showSection5 = ref(false);
const showSection6 = ref(false);

/* BASE STATIC VALUES */
const baseOverall = ref([]);
const baseSection1 = ref("");
const baseProducts = ref([]);
const baseAnalysis = ref([]);
const baseStrategy = ref([]);
const baseImpactReason = ref("");
const baseUrl = ref([]);
/* MODAL */
const showModal = ref(false);
const hvInput = ref("");
const isLoading = ref(false);

/* REPORT INPUT */
const props = defineProps({
  fileId: Number,
  regulationId: Number
});

/* TYPEWRITER BASED ON CHARACTER */
async function typeText(targetRef, text, section, speed = 17) {
  cursorAt.value = section;
  targetRef.value = "";

  for (let i = 0; i < text.length; i++) {
    targetRef.value += text[i];
    autoScroll();
    await new Promise(r => setTimeout(r, speed));
  }

  cursorAt.value = null;
  await new Promise(r => setTimeout(r, 70));
}

/* LIST STREAM */
async function typeList(targetRef, list, section, speed = 17) {
  cursorAt.value = section;
  targetRef.value = [];

  for (let line of list) {
    let typed = "";

    for (let i = 0; i < line.length; i++) {
      typed += line[i];
      targetRef.value[targetRef.value.length - 1] = typed;
      targetRef.value = [...targetRef.value];
      autoScroll();
      await new Promise(res => setTimeout(res, speed));
    }

    targetRef.value.push("");
    await new Promise(res => setTimeout(res, 120));
  }

  cursorAt.value = null;
}

/* PRODUCT STREAM */
async function typeProducts(targetRef, products, section, speed = 17) {
  cursorAt.value = section;
  targetRef.value = [];

  for (let p of products) {
    let full = p.action;
    let typed = "";

    for (let i = 0; i < full.length; i++) {
      typed += full[i];

      targetRef.value[targetRef.value.length - 1] = {
        item: p.item,
        product: p.product,
        action: typed
      };

      targetRef.value = [...targetRef.value];
      autoScroll();
      await new Promise(r => setTimeout(r, speed));
    }

    targetRef.value.push({});
    await new Promise(r => setTimeout(r, 120));
  }

  cursorAt.value = null;
}

/* LOAD BASE REPORT WHEN FILE ID CHANGES */
watch(
  () => props.fileId,
  async (id) => {
    if (!id) return;

    // 백엔드에서 리포트 데이터 가져오기
    isLoading.value = true;
    try {
      const res = await api.get(`/reports/${id}`);
      const data = res.data;

      // sections 배열을 파싱하여 각 섹션에 맞게 할당
      if (data.sections && Array.isArray(data.sections)) {
        data.sections.forEach(section => {
          if (section.title.includes('종합 요약')){
            baseOverall.value = section.content;
          } else if (section.title.includes('규제 변경 요약')) {
            baseSection1.value = section.content.join('\n');
          } else if (section.title.includes('제품 분석')) {
            baseProducts.value = section.tables.flatMap(table => 
              table.rows.map(row => ({
                item: row[0],      // 제품 속성
                product: table.product_name,  // 제품명
                action: row[1]
            }))
          );
          } else if (section.title.includes('변경 사항')) {
            baseAnalysis.value = section.content;
          } else if (section.title.includes('대응 전략')) {
            baseStrategy.value = section.content;
          } else if (section.title.includes('영향 평가')) {
            baseImpactReason.value = section.content.join('\n');
          } else if (section.title.includes('참고 및 원문 링크')) {
            baseUrl.value = section.content;
          }
        });
      }

      streamedOverrall.value = "";
      streamedSection1.value = "";
      streamedProducts.value = [];
      streamedAnalysis.value = [];
      streamedStrategy.value = [];
      streamedImpactReason.value = [];
      streamedReferences.value = [];

      isStreaming.value = false;
    } catch (err) {
      console.error('리포트 불러오기 실패:', err);
    } finally {
      isLoading.value = false;
    }
  },
  { immediate: true }
);

/* HUMAN VALIDATION */
const runHV = async () => {
  if (!hvInput.value.trim()) {
    alert('피드백을 입력해주세요.');
    return;
  }

  if (!props.regulationId) {
    alert('규제 ID가 없습니다.');
    return;
  }

  showModal.value = false;
  isLoading.value = true;

  try {
    // ✅ 백엔드 HITL API 호출
    const res = await api.post('/ai/hitl/feedback', {
      regulation_id: props.regulationId,
      user_message: hvInput.value
    });

    console.log('✅ HITL 응답:', res.data);

    // Intent 분기 처리
    if (res.data.intent === 'question') {
      // 질문 답변만 표시 (재실행 없음)
      alert(`답변: ${res.data.answer}`);
      isLoading.value = false;
      hvInput.value = '';
      return;
    }

    // modification: 새 보고서 로드
    if (res.data.report_id) {
      const reportRes = await api.get(`/reports/${res.data.report_id}`);
      const data = reportRes.data;

      // ✅ 새 데이터로 업데이트
      if (data.sections && Array.isArray(data.sections)) {
        data.sections.forEach(section => {
          if (section.title.includes('종합 요약')){
            baseOverall.value = section.content;
          } else if (section.title.includes('규제 변경 요약')) {
            baseSection1.value = section.content.join('\n');
          } else if (section.title.includes('제품 분석')) {
            baseProducts.value = section.tables.flatMap(table => 
              table.rows.map(row => ({
                item: row[0],
                product: table.product_name,
                action: row[1]
            }))
          );
          } else if (section.title.includes('변경 사항')) {
            baseAnalysis.value = section.content;
          } else if (section.title.includes('대응 전략')) {
            baseStrategy.value = section.content;
          } else if (section.title.includes('영향 평가')) {
            baseImpactReason.value = section.content.join('\n');
          } else if (section.title.includes('참고 및 원문 링크')) {
            baseUrl.value = section.content;
          }
        });
      }

      // ✅ 스트리밍 효과로 표시
      isLoading.value = false;
      isStreaming.value = true;

      showSection0.value = false;
      showSection1.value = false;
      showSection2.value = false;
      showSection3.value = false;
      showSection4.value = false;
      showSection5.value = false;
      showSection6.value = false;

      showSection0.value = true;
      await typeList(streamedOverrall, baseOverall.value, "Overrall");

      showSection1.value = true;
      await typeText(streamedSection1, baseSection1.value, "section1");

      showSection2.value = true;
      await typeProducts(streamedProducts, baseProducts.value, "products");

      showSection3.value = true;
      await typeList(streamedAnalysis, baseAnalysis.value, "analysis");

      showSection4.value = true;
      await typeList(streamedStrategy, baseStrategy.value, "strategy");

      showSection5.value = true;
      await typeText(streamedImpactReason, baseImpactReason.value, "impactReason");

      showSection6.value = true;
      await typeList(streamedReferences, baseUrl.value, "references");

      isStreaming.value = false;
    }

  } catch (err) {
    console.error('❌ HITL 실패:', err);
    alert('피드백 처리 중 오류가 발생했습니다.');
  } finally {
    isLoading.value = false;
    hvInput.value = '';
  }
};

const openModal = () => (showModal.value = true);

/* DOWNLOAD */
const downloadReport = async () => {
  if (!props.fileId) return;

  try {
    const res = await api.get(`/reports/${props.fileId}/download`, {
      responseType: "blob",
      timeout: 30000
    });
    const blob = new Blob([res.data], { type: "application/pdf" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `report_${props.fileId}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    console.error('리포트 다운로드 실패:', err);
    const status = err?.response?.status;
    if (status === 503) {
      alert('서버가 잠시 응답하지 않습니다. 잠시 후 다시 시도해주세요.');
    } else if (status === 504 || err.code === 'ECONNABORTED') {
      alert('다운로드 시간이 초과되었습니다. 다시 시도하거나 잠시 기다려주세요.');
    } else {
      alert('리포트 다운로드 중 오류가 발생했습니다.');
    }
  }
};
</script>

<style>
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgba(255,255,255,0.15);
  border-radius: 8px;
}

/* cursor blink */
.cursor {
  display: inline-block;
  width: 8px;
  animation: blink 1s step-start infinite;
  color: #FDFF78;
}

@keyframes blink {
  50% { opacity: 0; }
}

@keyframes modalIn {
  0% {
    opacity: 0;
    transform: translateY(8px) scale(0.96);
  }
  100% {
    opacity: 1;
    transform: translateY(0px) scale(1);
  }
}

.animate-modal-in {
  animation: modalIn 0.26s ease-out forwards;
}

.sec-title {
  font-size: 17px;
  font-weight: 600;
  margin-bottom: 12px;
  color: #B7C6DD;
}
</style>
