import express from 'express'
import ModbusRTU from 'modbus-serial'
import { fileURLToPath } from 'node:url'
import { setTimeout as delay } from 'node:timers/promises'
import { decode, movingReplay, replay } from './protocol.js'

const demo = process.argv.includes('--demo')
const host = process.env.PLC_HOST
const pollMs = Number(process.env.PLC_POLL_MS ?? 20)
if (!demo && (!Number.isInteger(pollMs) || pollMs < 10 || pollMs > 1000)) {
  throw new Error('PLC_POLL_MS 必须是 10–1000 的整数（毫秒）')
}
if (!demo && !host) throw new Error('请设置 PLC_HOST，或使用 npm run demo')
const app = express()
const clients = new Set()
let snapshot = { online: false, reason: '等待数据', demo }
function publish(frame) {
  snapshot = { ...frame, demo }
  const message = 'data: ' + JSON.stringify(snapshot) + '\n\n'
  for (const res of clients) {
    if (!res.write(message)) res.destroy()
  }
}
app.get('/events', (req, res) => {
  res.set({ 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' })
  res.flushHeaders()
  res.write('data: ' + JSON.stringify(snapshot) + '\n\n')
  clients.add(res)
  res.on('close', () => clients.delete(res))
})
app.get('/vue.js', (_, res) => res.sendFile(fileURLToPath(
  new URL('./node_modules/vue/dist/vue.esm-browser.prod.js', import.meta.url))))
app.use(express.static(fileURLToPath(new URL('./public/', import.meta.url))))
const port = Number(process.env.PORT || 3000)
app.listen(port, '127.0.0.1', () => console.log('FunFair http://127.0.0.1:' + port))

async function poll() {
  let lastBeat
  let changed = 0
  let count = 24
  for (;;) {
    const plc = new ModbusRTU()
    try {
      await plc.connectTCP(host, { port: Number(process.env.PLC_PORT || 502), timeout: 1500 })
      plc.setID(Number(process.env.PLC_UNIT || 1))
      plc.setTimeout(1000)
      for (;;) {
        const { data } = await plc.readHoldingRegisters(0, count)
        if (count === 24 && data[0] === 0x4646 && [2, 3].includes(data[1])) {
          count = 26
          continue
        }
        const frame = decode(data)
        if (frame.heartbeat !== lastBeat) {
          lastBeat = frame.heartbeat
          changed = Date.now()
        }
        if (Date.now() - changed > 1500) throw new Error('PLC 显示数据停止刷新')
        publish({ online: true, ...frame })
        await delay(pollMs)
      }
    } catch (error) {
      count = 24
      publish({ online: false, reason: error.message })
    } finally {
      plc.close(() => {})
    }
    await delay(1000)
  }
}
if (demo) {
  const start = Date.now()
  let latest
  const demoMode = process.argv.includes('--moving') ? 2 : 1
  setInterval(() => {
    const frame = demoMode === 1 ? replay(Date.now() - start) : movingReplay(Date.now() - start)
    if (frame.valid) latest = { seq: frame.seq, lastSuccess: frame.success, lastError: frame.error }
    publish({ ...frame, seq: 0, ...latest, online: true, mode: demoMode })
  }, 50)
} else {
  poll().catch(error => { console.error(error); process.exit(1) })
}
