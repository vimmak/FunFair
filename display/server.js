import express from 'express'
import ModbusRTU from 'modbus-serial'
import { fileURLToPath } from 'node:url'
import { setTimeout as delay } from 'node:timers/promises'
import { decode, movingReplay, replay } from './protocol.js'

const demo = process.argv.includes('--demo')
const host = process.env.PLC_HOST
if (!demo && !host) throw new Error('请设置 PLC_HOST，或使用 npm run demo')
const app = express()
const clients = new Set()
let pendingMode
let demoMode = 1
app.post('/mode', express.json({ limit: '1kb' }), (req, res) => {
  const { mode } = req.body || {}
  if (mode !== 1 && mode !== 2) return res.sendStatus(400)
  if (!snapshot.online || !snapshot.canSwitch || ![30, 40, 50].includes(snapshot.state)) {
    return res.sendStatus(409)
  }
  if (demo) demoMode = mode
  else pendingMode = mode
  return res.sendStatus(202)
})
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
        if (count === 24 && data[0] === 0x4646 && data[1] === 2) {
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
        if (pendingMode && frame.canSwitch && [30, 40, 50].includes(frame.state)) {
          const mode = pendingMode
          pendingMode = undefined
          await plc.writeRegister(25, mode)
        }
        await delay(50)
      }
    } catch (error) {
      count = 24
      pendingMode = undefined
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
  let lastMode
  setInterval(() => {
    const frame = demoMode === 1 ? replay(Date.now() - start) : movingReplay(Date.now() - start)
    if (demoMode !== lastMode) latest = undefined
    if (frame.valid) latest = { seq: frame.seq, lastSuccess: frame.success, lastError: frame.error }
    lastMode = demoMode
    publish({ ...frame, seq: 0, ...latest, online: true, mode: demoMode, canSwitch: true })
  }, 50)
} else {
  poll().catch(error => { console.error(error); process.exit(1) })
}
