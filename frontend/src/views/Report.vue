<template>
  <div>
    <h2 class="page-title">AI 综合评价报告</h2>
    <div v-if="loading" class="hint">加载中…</div>
    <div v-else-if="!exists" class="empty">暂无报告，请先运行流水线（需配置 LLM Key）。</div>
    <div v-else class="report" v-html="html"></div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { marked } from 'marked'
import { getReport } from '../api'

const html = ref('')
const exists = ref(false)
const loading = ref(true)

onMounted(async () => {
  try {
    const d = await getReport()
    exists.value = d.exists
    if (d.exists) html.value = marked.parse(d.markdown)
  } finally {
    loading.value = false
  }
})
</script>
