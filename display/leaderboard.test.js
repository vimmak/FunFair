import assert from 'node:assert/strict'
import test from 'node:test'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { openLeaderboard } from './leaderboard.js'

const round = (id, mode = 2, errorUm = -151) => ({ id, mode, errorUm, success: true })

test('模拟成绩只可认领一次，榜单保留原始误差与头像', t => {
  const store = openLeaderboard()
  t.after(() => store.close())
  const { code } = store.recordRound(round('round-1'))
  assert.match(code, /^\d{6}$/)
  assert.deepEqual(store.top(2), [])
  const claimed = store.claim(code, '  小陈  ')
  assert.equal(claimed.nickname, '小陈')
  assert.equal(claimed.errorUm, -151)
  assert.equal(claimed.success, true)
  assert.ok(Number.isInteger(claimed.avatar) && claimed.avatar >= 0 && claimed.avatar < 16)
  assert.equal(store.claim(code, '其他玩家'), null)
  assert.deepEqual(store.top(2), [claimed])
})

test('固定和移动目标分别按绝对偏差排名', t => {
  const store = openLeaderboard()
  t.after(() => store.close())
  for (const [id, mode, errorUm] of [['a', 2, -151], ['b', 2, 80], ['c', 1, 1]]) {
    const { code } = store.recordRound(round(id, mode, errorUm))
    assert.ok(store.claim(code, id))
  }
  assert.deepEqual(store.top(2).map(item => item.id), ['b', 'a'])
  assert.deepEqual(store.top(1).map(item => item.id), ['c'])
})

test('无效认领、到期和重复录入', t => {
  let now = 0
  const store = openLeaderboard(':memory:', { now: () => now })
  t.after(() => store.close())
  const data = round('round-1')
  const issued = store.recordRound(data)
  assert.equal(store.claim(issued.code, '   '), null)
  assert.equal(store.claim('invalid', '玩家'), null)
  now = issued.expiresAt
  assert.equal(store.claim(issued.code, '玩家'), null)
  assert.deepEqual(store.recordRound(data), issued)
  assert.deepEqual(store.top(2), [])
})

test('重开 SQLite 文件后保留成绩、头像和一次性认领状态', () => {
  const directory = mkdtempSync(join(tmpdir(), 'funfair-leaderboard-'))
  const filename = join(directory, 'leaderboard.sqlite')
  let store = openLeaderboard(filename)
  try {
    const { code } = store.recordRound(round('round-1'))
    const claimed = store.claim(code, '小陈')
    store.close()
    store = openLeaderboard(filename)
    assert.deepEqual(store.top(2), [claimed])
    assert.equal(store.claim(code, '另一位玩家'), null)
  } finally {
    store.close()
    rmSync(directory, { recursive: true })
  }
})
