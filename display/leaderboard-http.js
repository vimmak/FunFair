import express from 'express'
import { randomUUID } from 'node:crypto'
import { mkdirSync } from 'node:fs'
import { isIPv4 } from 'node:net'
import { fileURLToPath } from 'node:url'
import QRCode from 'qrcode'
import { openLeaderboard } from './leaderboard.js'

const publicDir = new URL('./public/', import.meta.url)
const send = (res, file) => res.sendFile(fileURLToPath(new URL(file, publicDir)))

export function setupLeaderboard(kioskApp, { demo, phoneHost, phonePort }) {
  if (phoneHost && (!isIPv4(phoneHost) || phoneHost === '0.0.0.0' || phoneHost.startsWith('127.'))) {
    throw new Error('FUNFAIR_PHONE_HOST 请填写展台 Wi-Fi 网卡的 IPv4 地址')
  }
  if (!Number.isInteger(phonePort) || phonePort < 1 || phonePort > 65535) {
    throw new Error('FUNFAIR_PHONE_PORT 请填写有效端口')
  }
  const location = new URL('./data/', import.meta.url)
  if (!demo) mkdirSync(location, { recursive: true })
  const store = openLeaderboard(demo ? ':memory:' : fileURLToPath(new URL('leaderboard.sqlite', location)))
  const phoneUrl = phoneHost ? `http://${phoneHost}:${phonePort}/leaderboard` : null
  let lastSequence
  let latest
  let scoreFeedReady = demo
  const phone = express()
  phone.disable('x-powered-by')
  phone.get('/leaderboard', (_, res) => send(res, 'leaderboard.html'))
  phone.get('/leaderboard.css', (_, res) => send(res, 'leaderboard.css'))
  phone.get('/leaderboard-page.js', (_, res) => send(res, 'leaderboard-page.js'))
  phone.get('/leaderboard-view.js', (_, res) => send(res, 'leaderboard-view.js'))
  phone.get('/api/leaderboard', (_, res) => {
    res.set('Cache-Control', 'no-store').json({ fixed: store.top(1), moving: store.top(2) })
  })

  const attempts = new Map()
  phone.post('/api/claim', express.json({ limit: '1kb' }), (req, res) => {
    const time = Date.now()
    for (const [ip, entry] of attempts) {
      if (entry.until <= time) attempts.delete(ip)
    }
    const key = req.ip
    const entry = attempts.get(key) || { count: 0, until: time + 60_000 }
    if (entry.count >= 12) return res.status(429).json({ error: '尝试次数过多，请稍后再试' })
    entry.count++
    attempts.set(key, entry)
    const { code, nickname } = req.body || {}
    if (typeof nickname !== 'string' || !nickname.trim() || [...nickname.trim()].length > 20 ||
        typeof code !== 'string' || !/^\d{6}$/.test(code)) {
      return res.status(400).json({ error: '请填写昵称和 6 位认领码' })
    }
    const claimed = store.claim(code, nickname)
    if (!claimed) return res.status(409).json({ error: '认领码无效、已过期或已被使用' })
    if (latest?.id === claimed.id) latest.claimed = true
    return res.json({ ...claimed, rank: store.rankOf(claimed) })
  })

  kioskApp.use(phone)
  if (phoneHost) {
    phone.listen(phonePort, phoneHost, () => console.log('手机排行榜 ' + phoneUrl))
  }
  kioskApp.get('/leaderboard-qr.png', async (_, res) => {
    if (!phoneUrl) return res.sendStatus(404)
    const png = await QRCode.toBuffer(phoneUrl, { width: 320, margin: 4, errorCorrectionLevel: 'M' })
    return res.type('png').send(png)
  })
  kioskApp.get('/api/kiosk', (_, res) => {
    const active = latest && latest.expiresAt > Date.now() ? latest : null
    res.set('Cache-Control', 'no-store').json({
      phoneUrl, scoreFeedReady, latest: active,
      fixed: store.top(1, 5), moving: store.top(2, 5)
    })
  })

  return function capture(frame) {
    scoreFeedReady = [1, 2].includes(frame.resultMode) || frame.protocolVersion === 3
    const previous = lastSequence
    lastSequence = frame.seq
    // Establish a live baseline so a restarted display does not reissue an old score.
    if ((!demo && previous === undefined) || !frame.seq || frame.seq === previous ||
        ![1, 2].includes(frame.resultMode)) return
    const id = randomUUID()
    const issued = store.recordRound({
      id, mode: frame.resultMode, errorUm: frame.lastError, success: frame.lastSuccess
    })
    latest = { id, code: issued.code, expiresAt: issued.expiresAt, claimed: false }
  }
}
