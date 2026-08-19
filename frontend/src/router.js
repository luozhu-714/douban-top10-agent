import { createRouter, createWebHashHistory } from 'vue-router'
import MovieList from './views/MovieList.vue'
import MovieDetail from './views/MovieDetail.vue'
import Report from './views/Report.vue'
import Dashboard from './views/Dashboard.vue'

// 用 hash 模式，静态托管时无需服务端 SPA 回退配置
export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: MovieList },
    { path: '/movie/:title', component: MovieDetail },
    { path: '/report', component: Report },
    { path: '/dashboard', component: Dashboard },
  ],
})
