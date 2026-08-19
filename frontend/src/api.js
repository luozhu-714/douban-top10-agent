import axios from 'axios'

// 开发时 Vite 把 /api 代理到 http://localhost:8000；生产时由 FastAPI 直接服务
const api = axios.create({ baseURL: '/api', timeout: 0 })

export const getMovies = () => api.get('/movies').then(r => r.data)
export const getReviews = () => api.get('/reviews').then(r => r.data)
export const getReport = () => api.get('/report').then(r => r.data)
export const getStats = () => api.get('/stats').then(r => r.data)
export const runPipeline = (analyze = true) =>
  api.post('/run', null, { params: { analyze } }).then(r => r.data)
export const getRunStatus = () => api.get('/run/status').then(r => r.data)
