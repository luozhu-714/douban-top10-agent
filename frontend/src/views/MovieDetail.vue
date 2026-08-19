<template>
  <div>
    <router-link to="/" class="back">← 返回榜单</router-link>
    <div v-if="loading" class="hint">加载中…</div>
    <div v-else-if="!entry" class="empty">未找到该电影的短评数据。</div>
    <div v-else>
      <h2 class="page-title">{{ entry.title }}</h2>
      <div class="score-row" style="margin: 6px 0 18px">
        <span class="score">{{ (entry.rating || 0).toFixed(1) }}</span>
        <span class="score-unit">分</span>
        <div class="score-bar" style="max-width: 240px">
          <i :style="{ width: (entry.rating || 0) * 10 + '%' }"></i>
        </div>
      </div>
      <div ref="starChartRef" style="width: 100%; height: 260px" class="chart"></div>
      <h3>短评（{{ entry.reviews.length }} 条）</h3>
      <div v-for="(r, i) in entry.reviews" :key="i" class="review">
        <div class="review-head">
          <span class="user">{{ r.user }}</span>
          <span class="stars">{{ '★'.repeat(r.rating) }}{{ '☆'.repeat(5 - r.rating) }}</span>
          <span class="votes">👍 {{ r.vote_count }}</span>
          <span class="time">{{ r.time }}</span>
        </div>
        <p class="content">{{ r.content }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import { getReviews } from '../api'

const route = useRoute()
const entry = ref(null)
const loading = ref(true)
const starChartRef = ref(null)

onMounted(async () => {
  try {
    const d = await getReviews()
    const list = d.reviews || []
    entry.value = list.find(r => r.title === route.params.title)
    if (entry.value) {
      await nextTick()
      renderStarChart()
    }
  } finally {
    loading.value = false
  }
})

function renderStarChart() {
  const dist = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 }
  entry.value.reviews.forEach(r => {
    if (dist[r.rating] != null) dist[r.rating]++
  })
  const chart = echarts.init(starChartRef.value)
  chart.setOption({
    title: { text: '星级分布', left: 'center' },
    tooltip: {},
    xAxis: { type: 'category', data: Object.keys(dist).map(k => k + ' 星') },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{ type: 'bar', data: Object.values(dist), itemStyle: { color: '#f5a623' } }],
  })
}
</script>
