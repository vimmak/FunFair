const avatars = ['🤖', '⚙️', '🔧', '🔩', '🦾', '🧲', '💡', '🔋',
  '⚡', '🛰️', '🧰', '🔬', '🛠️', '📐', '🧪', '🛞']

export function avatarFor(id) {
  return avatars[id] ?? avatars[0]
}

export function scoreText(errorUm, signed = false) {
  const value = (signed ? errorUm : Math.abs(errorUm)) / 1000
  return (signed && value > 0 ? '+' : '') + value.toFixed(3) + ' mm'
}
