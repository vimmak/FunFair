export function decode(words) {
  if (words[0] !== 0x4646 || !((words[1] === 1 && words.length === 24) ||
      (words[1] === 2 && words.length === 26))) {
    throw new Error('显示 DB 地址或协议版本不匹配')
  }
  const dint = i => (words[i] << 16) | words[i + 1]
  return {
    mode: words[1] === 1 ? 1 : [1, 2].includes(words[24]) ? words[24] : null,
    activeModeWord: words[1] === 2 ? words[24] : null,
    heartbeat: words[2], state: words[3], valid: !!words[4], success: !!words[5],
    fault: words[6], gripperFault: words[7], seq: words[8], lastSuccess: !!words[9],
    actual: dint(10), open: dint(12), close: dint(14), target: dint(16),
    tolerance: dint(18), error: dint(20), lastError: dint(22)
  }
}

// Alternates the field screenshot miss and a hit, with motion, settling and recovery.
export function replay(ms) {
  const round = Math.floor(ms / 8000)
  const t = ms % 8000
  const stop = round % 2 ? 13400 : 22000
  const valid = t >= 6000 && t < 7500
  const seq = round + Number(t >= 6000)
  const actual = t < 5400 ? Math.round(1000 + (stop - 1000) * t / 5400) : stop
  return { heartbeat: Math.floor(ms / 50) % 65536, state: t < 5400 || t >= 7500 ? 50 : valid ? 80 : 70,
    valid, success: valid && stop === 13400, actual, open: 22000, close: 1000,
    target: 13000, tolerance: 1000, error: actual - 13000, fault: 0, gripperFault: 0,
    seq, lastSuccess: seq > 0 && seq % 2 === 0, lastError: !seq ? 0 : seq % 2 ? 9000 : 400 }
}


export function movingReplay(ms) {
  const round = Math.floor(ms / 8000)
  const local = ms % 8000
  const elapsed = Math.min(local, 5400)
  const duration = 2300 + (round * 977 + 1470) % 2901
  const t = (elapsed % duration) / duration
  const ease = t * t * (3 - 2 * t)
  const phase = Math.floor(elapsed / duration) % 2 ? 1 - ease : ease
  const target = Math.round(1000 + phase * 21000)
  const actual = local < 5400 ? 1000 + (local * 5 <= 21000 ? local * 5 : 42000 - local * 5) : 16000
  const valid = local >= 6000 && local < 7500
  return {
    ...replay(ms), mode: 2, target, actual, error: actual - target,
    success: valid && Math.abs(actual - target) < 1000
  }
}
