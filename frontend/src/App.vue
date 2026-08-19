<template>
  <div class="app">
    <header class="topbar">
      <div class="brand"><span class="logo-dot"></span>豆瓣 Top10 口碑分析</div>
      <nav class="nav">
        <router-link to="/">榜单</router-link>
        <router-link to="/dashboard">图表</router-link>
        <router-link to="/report">报告</router-link>
      </nav>
      <div class="actions">
        <button class="run-btn" :disabled="running" @click="runAll">
          {{ running ? '运行中…' : '运行流水线' }}
        </button>
        <span v-if="jobMsg" class="job-msg">{{ jobMsg }}</span>
      </div>
    </header>
    <main class="content">
      <router-view :key="$route.fullPath" />
    </main>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'
import { runPipeline, getRunStatus } from './api'

const running = ref(false)
const jobMsg = ref('')
let timer = null

async function runAll() {
  running.value = true
  jobMsg.value = '启动中…'
  try {
    await runPipeline(true)
    poll()
  } catch (e) {
    running.value = false
    jobMsg.value = '启动失败，请确认后端已启动'
  }
}

function poll() {
  timer = setInterval(async () => {
    try {
      const s = await getRunStatus()
      jobMsg.value = s.message || ''
      if (s.status === 'done' || s.status === 'error') {
        running.value = false
        clearInterval(timer)
        timer = null
        if (s.status === 'done') location.reload()
      }
    } catch (e) {
      // 忽略轮询异常，下个周期继续
    }
  }, 2000)
}

onBeforeUnmount(() => timer && clearInterval(timer))
</script>
