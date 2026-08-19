<template>
  <div>
    <h2 class="page-title">数据图表</h2>
    <div v-if="loading" class="hint">加载中…</div>
    <div v-else-if="!hasData" class="empty">暂无数据，请先运行流水线。</div>
    <div v-else>
      <div class="stat-row">
        <div class="stat"><b>{{ stats.movie_total }}</b><span>部电影</span></div>
        <div class="stat"><b>{{ stats.review_total }}</b><span>条短评</span></div>
        <div class="stat"><b>{{ stats.avg_rating }}</b><span>平均分</span></div>
      </div>
      <div ref="ratingChartRef" style="width: 100%; height: 360px" class="chart"></div>
      <div ref="starChartRef" style="width: 100%; height: 360px" class="chart"></div>
      <h3>高赞短评 Top10</h3>
      <div v-for="(r, i) in stats.top_voted" :key="i" class="review">
        <div class="review-head">
          <span class="user">{{ r.title }} · {{ r.user }}</span>
          <span class="stars">{{ '★'.repeat(r.rating) }}</span>
          <span class="votes">👍 {{ r.vote_count }}</span>
        </div>
        <p class="content">{{ r.content }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getStats } from '../api'

const stats = ref(null)
const hasData = ref(false)
const loading = ref(true)
const ratingChartRef = ref(null)
const starChartRef = ref(null)
let ratingChart = null
let starChart = null

onMounted(async () => {
  try {
    const d = await getStats()
    hasData.value = d.has_data
    stats.value = d
    if (d.has_data) {
      await nextTick()
      renderRatingChart(d)
      renderStarChart(d)
    }
  } finally {
    loading.value = false
  }
})

function renderRatingChart(d) {
  ratingChart = echarts.init(ratingChartRef.value)
  ratingChart.setOption({
    title: { text: 'Top10 评分', left: 'center' },
    tooltip: {},
    grid: { left: 140, right: 40, top: 40, bottom: 30 },
    xAxis: { type: 'value', min: 8 },
    yAxis: {
      type: 'category',
      data: d.rating_bar.map(x => x.title).reverse(),
      axisLabel: { fontSize: 12 },
    },
    series: [
      {
        type: 'bar',
        data: d.rating_bar.map(x => x.rating).reverse(),
        itemStyle: { color: '#4c8bf5' },
        label: { show: true, position: 'right' },
      },
    ],
  })
}

function renderStarChart(d) {
  starChart = echarts.init(starChartRef.value)
  starChart.setOption({
    title: { text: '短评星级分布', left: 'center' },
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [
      {
        type: 'pie',
        radius: '60%',
        data: d.star_dist.map(x => ({ name: x.star + ' 星', value: x.count })),
        label: { formatter: '{b}: {c}' },
      },
    ],
  })
}

onBeforeUnmount(() => {
  if (ratingChart) ratingChart.dispose()
  if (starChart) starChart.dispose()
})
</script>
