import { useState, useEffect } from 'react'

const API_URL = 'http://localhost:8000'

const CAT_LABEL = {
  casual: { label: 'Casual', desc: '001-011 (1P)' },
  level:  { label: 'Level',  desc: '14-25 (1P)' },
  dk:     { label: 'DK',     desc: 'DK01-DK10 (2P)' },
}

const DIFFICULTIES = ['easy', 'normal', 'hard']

export default function GameSettingsScreen({ game, onConfirm, onBack }) {
  const [categories, setCategories] = useState({})
  const [playerCount, setPlayerCount] = useState(1)
  const [category, setCategory]       = useState('casual')
  const [level, setLevel]             = useState('')
  const [difficulty, setDifficulty]   = useState('normal')
  const [loading, setLoading]         = useState(true)

  useEffect(() => {
    fetch(`${API_URL}/levels`)
      .then(r => r.json())
      .then(d => {
        if (d.success) {
          setCategories(d.categories || {})
          const first = (d.categories?.['casual'] || [])[0]
          if (first) setLevel(first.id)
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const handleCategory = (cat) => {
    setCategory(cat)
    const lvls = filteredLevels(cat)
    if (lvls.length) setLevel(lvls[0].id)
  }

  const handlePlayerCount = (n) => {
    setPlayerCount(n)
    const defaultCat = n === 2 ? 'dk' : 'casual'
    setCategory(defaultCat)
    const lvls = filteredLevels(defaultCat, n)
    if (lvls.length) setLevel(lvls[0].id)
  }

  const filteredLevels = (cat, players = playerCount) => {
    const lvls = categories[cat] || []
    if (players === 2) return lvls.filter(l => l.multiplayer)
    return lvls.filter(l => !l.multiplayer)
  }

  const handleConfirm = () => {
    onConfirm({ level, difficulty, playerCount })
  }

  if (loading) return <div className="screen"><p>Loading levels…</p></div>

  const levels = filteredLevels(category)

  return (
    <div className="screen settings-screen">
      <h2>Hoops — Game Settings</h2>

      <div className="setting-group">
        <label>Players</label>
        <div className="btn-row">
          {[1, 2].map(n => (
            <button key={n}
              className={playerCount === n ? 'active' : ''}
              onClick={() => handlePlayerCount(n)}>
              {n}P
            </button>
          ))}
        </div>
      </div>

      <div className="setting-group">
        <label>Series</label>
        <div className="btn-row">
          {Object.entries(CAT_LABEL).map(([key, { label, desc }]) => {
            if (playerCount === 2 && key !== 'dk') return null
            if (playerCount === 1 && key === 'dk') return null
            return (
              <button key={key}
                className={category === key ? 'active' : ''}
                onClick={() => handleCategory(key)}
                title={desc}>
                {label}
              </button>
            )
          })}
        </div>
      </div>

      <div className="setting-group">
        <label>Level</label>
        <select value={level} onChange={e => setLevel(e.target.value)}>
          {levels.map(l => (
            <option key={l.id} value={l.id}>{l.name}</option>
          ))}
        </select>
      </div>

      <div className="setting-group">
        <label>Difficulty</label>
        <div className="btn-row">
          {DIFFICULTIES.map(d => (
            <button key={d}
              className={difficulty === d ? 'active' : ''}
              onClick={() => setDifficulty(d)}>
              {d}
            </button>
          ))}
        </div>
      </div>

      <div className="btn-row actions">
        <button onClick={onBack}>Back</button>
        <button className="primary" onClick={handleConfirm} disabled={!level}>
          Start Game
        </button>
      </div>
    </div>
  )
}
