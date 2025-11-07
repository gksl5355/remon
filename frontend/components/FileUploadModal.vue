<template>
  <div class="upload">
    <h3>파일 업로드</h3>
    <input type="file" @change="uploadFile" />
  </div>
</template>

<script setup>
const uploadFile = (e) => {
  const file = e.target.files[0]
  if (file) alert(\`업로드된 파일: \${file.name}\`)
}
</script>

<style scoped>
.upload {
  padding: 1rem;
  border: 1px dashed #ccc;
  text-align: center;
}
</style>
