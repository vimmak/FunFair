import { avatarFor, scoreText } from '/leaderboard-view.js'

const buttons = [...document.querySelectorAll('[data-mode]')]
const form = document.getElementById('claim-form')
const message = document.getElementById('claim-message')
const rows = document.getElementById('ranking')
const boardMessage = document.getElementById('board-message')
let board = { fixed: [], moving: [] }
let mode = 'moving'
let claimedId
let reading = false

function render() {
  for (const button of buttons) button.setAttribute('aria-pressed', button.dataset.mode === mode)
  rows.replaceChildren()
  board[mode].forEach((entry, index) => {
    const row = document.createElement('li')
    row.classList.toggle('own', entry.id === claimedId)
    for (const [value, className] of [
      [index + 1, 'rank'], [avatarFor(entry.avatar), 'avatar'],
      [entry.nickname, 'name'], [scoreText(entry.errorUm), 'deviation']
    ]) {
      const cell = document.createElement('span')
      cell.className = className
      cell.textContent = value
      if (className === 'avatar') cell.setAttribute('aria-hidden', 'true')
      row.append(cell)
    }
    rows.append(row)
  })
  boardMessage.hidden = board[mode].length > 0
  boardMessage.textContent = '该难度还没有已认领的成绩'
}

async function refresh() {
  if (reading) return
  reading = true
  try {
    const response = await fetch('/api/leaderboard', { cache: 'no-store' })
    if (!response.ok) throw new Error()
    board = await response.json()
    render()
  } catch {
    boardMessage.hidden = false
    boardMessage.textContent = '暂时连不上排行榜，请确认已加入展台 Wi-Fi'
  } finally {
    reading = false
  }
}

for (const button of buttons) {
  button.addEventListener('click', () => { mode = button.dataset.mode; render() })
}

form.addEventListener('submit', async event => {
  event.preventDefault()
  const submit = form.querySelector('button')
  submit.disabled = true
  message.hidden = false
  message.classList.remove('error')
  message.textContent = '正在认领…'
  try {
    const body = Object.fromEntries(new FormData(form))
    const response = await fetch('/api/claim', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    })
    const result = await response.json()
    if (!response.ok) throw new Error(result.error || '暂时无法认领，请稍后再试')
    claimedId = result.id
    mode = result.mode === 1 ? 'fixed' : 'moving'
    message.textContent = avatarFor(result.avatar) + ' ' + result.nickname + ' · ' +
      (result.success ? '命中' : '未命中') + ' · 偏差 ' + scoreText(result.errorUm, true) +
      ' · 第 ' + result.rank + ' 名'
    form.elements.code.value = ''
    await refresh()
  } catch (error) {
    message.classList.add('error')
    message.textContent = error instanceof TypeError ? '网络连接中断，请检查展台 Wi-Fi' : error.message
  } finally {
    submit.disabled = false
  }
})

refresh()
setInterval(refresh, 3000)
