<template>
  <div
    class="fixed inset-0 bg-black/50 backdrop-blur-md z-40
           flex items-center justify-center animate-fadeIn"
    @click.self="close"
  >
    <div
      class="w-80 rounded-xl shadow-[0_8px_30px_rgba(0,0,0,0.45)]
             border border-white/10 bg-[#121a28]/90 backdrop-blur-xl
             p-6 animate-popupEnter relative"
    >
      <!-- Top Glow -->
      <div
        class="absolute top-0 left-0 right-0 h-[2px]
               bg-gradient-to-r from-transparent via-white/20 to-transparent"
      />

      <h3 class="text-[15px] font-semibold text-gray-100 mb-4 tracking-wide">
        파일 다운로드
      </h3>

      <!-- Buttons -->
      <div class="space-y-2.5">
        <button
          class="w-full py-2 text-[14px] rounded-lg
                 bg-[#1A2333]/70 hover:bg-[#212d42]
                 border border-white/10 transition
                 text-gray-100 flex items-center justify-center"
          @click="downloadOriginal"
        >
          원문 다운로드
        </button>

        <button
          class="w-full py-2 text-[14px] rounded-lg
                 bg-[#1A2333]/70 hover:bg-[#212d42]
                 border border-white/10 transition
                 text-gray-100 flex items-center justify-center"
          @click="downloadTranslated"
        >
          번역본 다운로드
        </button>
      </div>

      <div class="mt-4 mb-3 border-t border-white/10"></div>

      <p class="text-[11px] text-gray-400 leading-relaxed text-center">
        * 번역본 다운로드는 번역 작업으로 인해<br />
        &nbsp;&nbsp;약간의 시간이 소요될 수 있습니다.
      </p>
    </div>

    <!-- Progress Modal -->
    <TranslationProgress
      v-if="showProgress"
      :progress="progress"
    />
  </div>
</template>

<script setup>
import api from "@/services/api";
import { ref } from "vue";
import TranslationProgress from "./TranslationProgressModal.vue";

const props = defineProps({
  item: { type: Object, required: true }
});

const emit = defineEmits(["close"]);

const close = () => emit("close");

async function downloadOriginal() {
  const res = await api.post("/admin/s3/download-url", {
    key: props.item.s3_key
  });
  window.open(res.data.url, "_blank");
  close();
}

const showProgress = ref(false);
const progress = ref(0);

async function downloadTranslated() {
  showProgress.value = true;
  progress.value = 15;

  let fakeTimer = setInterval(() => {
    if (progress.value < 88) {
      progress.value += Math.random() * 3 + 1;
    }
  }, 700);

  try {
    progress.value = 35;

    // 🔥 JSON 응답으로 받는다
    const res = await api.post(
      "/admin/s3/translations/generate",
      {
        s3_key: props.item.s3_key,
        target_lang: "ko",
      },
      {
        timeout: 0,
      }
    );

    clearInterval(fakeTimer);
    progress.value = 95;

    const { download_url } = res.data;

    if (!download_url) {
      throw new Error("download_url not found in response");
    }

    // 🔥 실제 PDF 다운로드는 S3에서
    window.open(download_url, "_blank");

    progress.value = 100;

    setTimeout(() => {
      showProgress.value = false;
      close();
    }, 500);

  } catch (e) {
    clearInterval(fakeTimer);
    console.error(e);
    alert("번역본 생성 중 오류가 발생했습니다.");
    showProgress.value = false;
  }
}

</script>

<style scoped>
@keyframes fadeIn {
  from { opacity: 0 }
  to { opacity: 1 }
}
.animate-fadeIn {
  animation: fadeIn 0.25s ease-out;
}

@keyframes popupEnter {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
.animate-popupEnter {
  animation: popupEnter 0.28s cubic-bezier(0.16, 1, 0.3, 1);
}
</style>
