import test from 'node:test'
import assert from 'node:assert/strict'
import { decode, replay } from './protocol.js'

test('现场截图与寄存器映射，包括负偏差和高字', () => {
  const words = [0x4646,1,3,80,1,0,0,0,7,0,0,22000,0,22000,0,1000,0,13000,0,1000,0,9000,0,9000]
  const f = decode(words)
  assert.deepEqual([f.state,f.valid,f.success,f.actual,f.error,f.seq], [80,true,false,22000,9000,7])
  words.splice(20,2,0xffff,0xfffe)
  assert.equal(decode(words).error,-2)
  words.splice(10,2,1,1)
  assert.equal(decode(words).actual,65537)
  assert.throws(() => decode(words.slice(1)))
})
test('回放先未命中、后命中，并在解锁后保留成绩', () => {
  assert.equal(replay(5500).state,70)
  assert.equal(replay(6200).lastError,9000)
  assert.equal(replay(7800).valid,false)
  assert.equal(replay(7800).seq,1)
  assert.equal(replay(14300).lastSuccess,true)
})

test('V2 扩展帧反馈实际模式，V1 帧仍可解码', () => {
  const words = [0x4646, 2, ...Array(22).fill(0), 2, 1]
  assert.equal(decode(words).mode, 2)
  assert.equal(decode(words).canSwitch, true)
  words[1] = 1
  assert.equal(decode(words.slice(0, 24)).canSwitch, false)
})
