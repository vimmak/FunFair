import { randomInt } from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'

const CODE_LIFETIME_MS = 120_000
const AVATAR_COUNT = 16

export function openLeaderboard(filename = ':memory:', { now = Date.now } = {}) {
  const db = new DatabaseSync(filename)
  db.exec(`
    CREATE TABLE IF NOT EXISTS rounds (
      id TEXT PRIMARY KEY NOT NULL,
      mode INTEGER NOT NULL CHECK (mode IN (1, 2)),
      error_um INTEGER NOT NULL,
      success INTEGER NOT NULL CHECK (success IN (0, 1)),
      code TEXT NOT NULL,
      expires_at INTEGER NOT NULL,
      nickname TEXT,
      avatar INTEGER
    )
  `)
  const findRound = db.prepare('SELECT code, expires_at FROM rounds WHERE id = ?')
  const codeInUse = db.prepare('SELECT 1 FROM rounds WHERE code = ? AND expires_at > ?')
  const insert = db.prepare(`
    INSERT INTO rounds (id, mode, error_um, success, code, expires_at)
    VALUES (?, ?, ?, ?, ?, ?)
  `)
  const claimRound = db.prepare(`
    UPDATE rounds SET nickname = ?, avatar = ?
    WHERE code = ? AND expires_at > ? AND nickname IS NULL
    RETURNING id, mode, nickname, avatar, error_um AS errorUm, success
  `)
  const leaders = db.prepare(`
    SELECT id, mode, nickname, avatar, error_um AS errorUm, success
    FROM rounds
    WHERE mode = ? AND nickname IS NOT NULL
    ORDER BY ABS(error_um), id
    LIMIT ?
  `)
  const rank = db.prepare(`
    SELECT COUNT(*) + 1 AS rank FROM rounds
    WHERE mode = ? AND nickname IS NOT NULL
      AND (ABS(error_um) < ABS(?) OR (ABS(error_um) = ABS(?) AND id < ?))
  `)
  const result = row => row ? { ...row, success: Boolean(row.success) } : null

  return {
    recordRound({ id, mode, errorUm, success }) {
      if (typeof id !== 'string' || !id || ![1, 2].includes(mode) ||
          !Number.isSafeInteger(errorUm) || typeof success !== 'boolean') {
        throw new TypeError('Invalid round')
      }
      // Serialize the available-code check and reservation across connections.
      db.exec('BEGIN IMMEDIATE')
      try {
        const existing = findRound.get(id)
        if (existing) {
          db.exec('COMMIT')
          return { code: existing.code, expiresAt: existing.expires_at }
        }
        const time = now()
        let code
        do {
          code = String(randomInt(0, 1_000_000)).padStart(6, '0')
        } while (codeInUse.get(code, time))
        const expiresAt = time + CODE_LIFETIME_MS
        insert.run(id, mode, errorUm, Number(success), code, expiresAt)
        db.exec('COMMIT')
        return { code, expiresAt }
      } catch (error) {
        db.exec('ROLLBACK')
        throw error
      }
    },
    claim(code, nickname) {
      if (typeof code !== 'string' || !/^\d{6}$/.test(code) ||
          typeof nickname !== 'string') return null
      const name = nickname.trim()
      if (!name || [...name].length > 20) return null
      return result(claimRound.get(name, randomInt(AVATAR_COUNT), code, now()))
    },
    rankOf({ id, mode, errorUm }) {
      return rank.get(mode, errorUm, errorUm, id).rank
    },
    top(mode, limit = 10) {
      if (![1, 2].includes(mode) || !Number.isInteger(limit) || limit < 1 || limit > 100) {
        throw new TypeError('Invalid leaderboard query')
      }
      return leaders.all(mode, limit).map(result)
    },
    close() { db.close() }
  }
}
