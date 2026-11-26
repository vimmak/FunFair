import { createApp } from '/vue.js'

createApp({
  data: () => ({ f: null, online: false, demo: false, reason: '', received: 0, full: false }),
  computed: {
    modeLabel() {
      if (!this.f) return '等待模式数据'
      if (this.f.mode === 1) return '固定目标'
      if (this.f.mode === 2) return '移动目标'
      return '模式数据无效'
    },
    overlap() {
      return this.online && [30, 40, 50].includes(this.f.state) &&
        Math.abs(this.f.actual - this.f.target) < this.f.tolerance
    },
    title() {
      if (!this.online) return this.f ? '连接中断' : '等待连接'
      if (this.f.state === 900 || this.f.state === 905) return '夹爪等待恢复'
      if (this.f.valid) return this.f.success ? '命中！' : '差一点'
      if ([55, 60, 70].includes(this.f.state)) return '等待停稳'
      if (this.f.state === 10) return '等待解锁'
      if (this.overlap) return '现在暂停'
      return this.f.state === 0 ? '等待夹爪就绪' : '看准目标'
    },
    hint() {
      if (!this.online) return this.reason || '等待现场数据'
      if (this.f.valid || this.f.state === 10) return '解锁暂停按钮，继续挑战'
      if (this.f.state >= 900) return '请查看设备状态和诊断码'
      if (this.f.state >= 55) return '停稳后显示本轮成绩'
      return '夹爪指针进入目标窗口时，按下暂停按钮'
    },
    band() {
      const a = this.x(this.f.target - this.f.tolerance)
      const b = this.x(this.f.target + this.f.tolerance)
      return { left: Math.min(a,b), width: Math.abs(a-b) }
    }
  },
  methods: {
    x(v) {
      const span = this.f.open - this.f.close
      return span ? 40 + 920 * Math.max(0, Math.min(1, (v-this.f.close)/span)) : 40
    },
    mm(v) { return Number.isFinite(v) ? (v/1000).toFixed(3) : '—' },
    signed(v) { return (v > 0 ? '+' : '') + this.mm(v) },
    hex(v) { return Number.isFinite(v) ? '0x'+v.toString(16).padStart(4,'0').toUpperCase() : '—' },
    fullscreen() {
      if (document.fullscreenElement) document.exitFullscreen()
      else document.documentElement.requestFullscreen()
    }
  },
  mounted() {
    document.addEventListener('fullscreenchange', () => { this.full = !!document.fullscreenElement })
    const events = new EventSource('/events')
    events.onmessage = ({data}) => {
      const frame = JSON.parse(data)
      this.received = Date.now()
      this.online = frame.online
      this.demo = frame.demo
      this.reason = frame.reason
      if (frame.online) this.f = frame
    }
    events.onerror = () => { this.online = false; this.reason = '等待本地服务重连' }
    setInterval(() => {
      if (this.online && Date.now() - this.received > 2000) {
        this.online = false
        this.reason = '数据停止刷新'
      }
    }, 500)
  }
}).mount('#app')
