export function decode(words) {
  if (words.length !== 24 || words[0] !== 0x4646 || words[1] !== 1) {
    throw new Error('显示 DB 地址或协议版本不匹配')
  }
  const dint = i => (words[i] << 16) | words[i + 1]
  return {
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
