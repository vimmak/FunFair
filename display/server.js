import express from 'express'
import ModbusRTU from 'modbus-serial'
import { fileURLToPath } from 'node:url'
import { setTimeout as delay } from 'node:timers/promises'
import { decode, replay } from './protocol.js'

const demo = process.argv.includes('--demo')
const host = process.env.PLC_HOST
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
  for (;;) {
    const plc = new ModbusRTU()
    try {
      await plc.connectTCP(host, { port: Number(process.env.PLC_PORT || 502), timeout: 1500 })
      plc.setID(Number(process.env.PLC_UNIT || 1))
      plc.setTimeout(1000)
      for (;;) {
        const { data } = await plc.readHoldingRegisters(0, 24)
        const frame = decode(data)
        if (frame.heartbeat !== lastBeat) {
          lastBeat = frame.heartbeat
          changed = Date.now()
        }
        if (Date.now() - changed > 1500) throw new Error('PLC 显示数据停止刷新')
        publish({ online: true, ...frame })
        await delay(50)
      }
    } catch (error) {
      publish({ online: false, reason: error.message })
    } finally {
      plc.close(() => {})
    }
    await delay(1000)
  }
}
if (demo) {
  const start = Date.now()
  setInterval(() => publish({ online: true, ...replay(Date.now() - start) }), 50)
} else {
  poll().catch(error => { console.error(error); process.exit(1) })
}
