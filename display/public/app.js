import { createApp } from '/vue.js'

const runningStates = [30, 40, 50]
const stoppingStates = [55, 60, 70]

createApp({
  data: () => ({
    f: null,
    online: false,
    demo: false,
    reason: '',
    received: 0,
    full: false,
    fullscreenError: ''
  }),
  computed: {
    frame() { return this.online ? this.f : null },
    running() { return runningStates.includes(this.frame?.state) },
    stopping() { return stoppingStates.includes(this.frame?.state) },
    faulted() { return [900, 905].includes(this.frame?.state) },
    outcome() { return Boolean(this.frame?.valid) },
    overlap() {
      return this.running && Math.abs(this.frame.actual - this.frame.target) < this.frame.tolerance
    },
    connectionLabel() {
      if (!this.online) return 'PLC 离线'
      return this.demo ? '演示模式' : 'PLC 在线'
    },
    modeLabel() {
      if (!this.frame) return ''
      return { 1: '固定目标', 2: '移动目标' }[this.frame.mode] ?? '模式未知'
    },
    canFullscreen() { return document.fullscreenEnabled === true },
    tone() {
      if (!this.online) return 'offline'
      if (this.faulted) return 'fault'
      if (this.outcome) return this.frame.success ? 'hit' : 'miss'
      return this.overlap ? 'ready' : 'normal'
    },
    title() {
      if (!this.online) return this.f ? '连接中断' : '等待连接'
      if (this.faulted) return '夹爪等待恢复'
      if (this.outcome) return this.frame.success ? '命中！' : '未命中'
      if (this.stopping) return '等待停稳'
      if (this.frame.state === 10) return '等待启动'
      if (this.frame.state === 0) return '等待夹爪就绪'
      return this.overlap ? '现在暂停' : '看准目标'
    },
    hint() {
      if (!this.online) return this.reason || '等待现场数据'
      if (this.faulted) return '请查看设备状态和诊断码'
      if (this.outcome) return '按下复位按钮，继续挑战'
      if (this.stopping) return '停稳后显示本轮成绩'
      if (this.frame.state === 10) return '按下复位按钮，开始挑战'
      if (this.frame.state === 0) return '等待 PLC 获取有效反馈'
      return this.overlap ? '按下实体暂停按钮' : '夹爪指针进入目标窗口时，按下暂停按钮'
    },
    announcement() {
      const status = this.running ? '挑战进行中' : this.title
      return this.connectionLabel + ' · ' + status
    },
    band() {
      const { target, tolerance } = this.frame
      const a = this.positionPercent(target - tolerance)
      const b = this.positionPercent(target + tolerance)
      return { left: Math.min(a, b), width: Math.abs(a - b), center: this.positionPercent(target) }
    },
    pointer() { return this.positionPercent(this.frame.actual) }
  },
  methods: {
    positionPercent(value) {
      const { close, open } = this.frame
      return open === close ? 0 : 100 * Math.max(0, Math.min(1, (value - close) / (open - close)))
    },
    mm(value) { return Number.isFinite(value) ? (value / 1000).toFixed(3) : '—' },
    signed(value) { return (value > 0 ? '+' : '') + this.mm(value) },
    hex(value) { return Number.isFinite(value) ? '0x' + value.toString(16).padStart(4, '0').toUpperCase() : '—' },
    async fullscreen() {
      this.fullscreenError = ''
      try {
        if (document.fullscreenElement) await document.exitFullscreen()
        else await document.documentElement.requestFullscreen()
      } catch {
        this.fullscreenError = '无法切换全屏'
      }
    }
  },
  mounted() {
    document.addEventListener('fullscreenchange', () => { this.full = !!document.fullscreenElement })
    const events = new EventSource('/events')
    events.onmessage = ({ data }) => {
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
