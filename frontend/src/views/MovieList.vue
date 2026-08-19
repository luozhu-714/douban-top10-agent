<template>
  <div>
    <h2 class="page-title">豆瓣电影 Top 10</h2>
    <p class="page-sub">爬虫抓取榜单 · Agent 分析短评口碑</p>

    <div v-if="loading" class="hint">加载中…</div>
    <div v-else-if="!movies.length" class="empty">
      <div class="empty-emoji">🎬</div>
      暂无数据，请点右上角「运行流水线」抓取一次。
    </div>
    <div v-else class="grid">
      <router-link
        v-for="m in movies"
        :key="m.rank"
        :to="`/movie/${encodeURIComponent(m.title)}`"
        class="card"
      >
        <div class="poster">
          <img
            v-if="m.poster"
            :src="`/api/poster?url=${encodeURIComponent(m.poster)}`"
            :alt="m.title"
            loading="lazy"
          />
          <div v-else class="poster-fallback">{{ m.title.slice(0, 1) }}</div>
          <span class="rank-badge">NO.{{ m.rank }}</span>
        </div>

        <div class="info">
          <div class="title-row">
            <span class="title">{{ m.title }}</span>
            <span class="orig">{{ m.original_title }}</span>
          </div>

          <div class="score-row">
            <span class="score">{{ (m.rating || 0).toFixed(1) }}</span>
            <span class="score-unit">分</span>
            <div class="score-bar"><i :style="{ width: (m.rating || 0) * 10 + '%' }"></i></div>
          </div>
          <div class="count">{{ formatCount(m.rating_count) }} 人评价</div>

          <div class="meta">{{ m.year }} · {{ m.country }} · {{ m.genre }}</div>
          <div class="directors">导演：{{ (m.directors || []).join(' / ') }}</div>
          <div class="quote">「{{ m.quote }}」</div>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getMovies } from '../api'

const movies = ref([])
const loading = ref(true)

function formatCount(n) {
  if (n == null) return '0'
  if (n >= 10000) return (n / 10000).toFixed(1).replace(/\.0$/, '') + '万'
  return String(n)
}

onMounted(async () => {
  try {
    const d = await getMovies()
    movies.value = d.movies || []
  } catch (e) {
    movies.value = []
  } finally {
    loading.value = false
  }
})
</script>
