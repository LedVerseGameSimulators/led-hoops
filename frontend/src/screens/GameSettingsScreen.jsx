import { useState, useEffect } from 'react'

import { API_URL } from '../config'

const CAT_LABEL = {
  casual: { label: 'Casual', desc: '001–011 (1P)' },
  level:  { label: 'Level',  desc: '014–025 (1P)' },
  dk:     { label: 'DK',     desc: 'DK01–DK10 (2P)' },
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
          const first = (d.categories?.casual || [])[0]
          if (first) setLevel(first.id)
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const filteredLevels = (cat = category, players = playerCount) => {
    const lvls = categories[cat] || []
    if (players === 2) return lvls.filter(l => l.multiplayer)
    return lvls.filter(l => !l.multiplayer)
  }

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

  const levelList = filteredLevels()
  const availableCats = Object.keys(CAT_LABEL).filter(cat => {
    if (playerCount === 2 && cat !== 'dk') return false
    if (playerCount === 1 && cat === 'dk') return false
    return filteredLevels(cat).length > 0
  })

  const handleConfirm = () => {
    if (!level) return
    onConfirm({ game, level, difficulty, playerCount })
  }

  if (loading) {
    return (
      <div className="screen">
        <div className="card">
          <p style={{ textAlign: 'center', color: '#888' }}>Loading levels…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="screen">
      <div className="card">
        <h1>🏀 Hoops</h1>
        <p style={{ textAlign: 'center', color: '#888', marginTop: '-10px' }}>
          Game Settings
        </p>

        <h2 style={{ fontSize: '0.9rem', color: '#aaa', marginTop: '24px' }}>PLAYERS</h2>
        <div style={{ display: 'flex', gap: '10px' }}>
          {[1, 2].map(n => (
            <button
              key={n}
              type="button"
              className={`option-btn ${playerCount === n ? 'selected' : ''}`}
              style={{ flex: 1 }}
              onClick={() => handlePlayerCount(n)}
            >
              {n === 1 ? '1 Player' : '2 Players'}
            </button>
          ))}
        </div>

        <h2 style={{ fontSize: '0.9rem', color: '#aaa', marginTop: '20px' }}>SERIES</h2>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {availableCats.map(cat => (
            <button
              key={cat}
              type="button"
              className={`option-btn ${category === cat ? 'selected' : ''}`}
              style={{ flex: '1 1 30%', padding: '10px 8px' }}
              onClick={() => handleCategory(cat)}
              title={CAT_LABEL[cat]?.desc}
            >
              <div style={{ fontWeight: 'bold' }}>{CAT_LABEL[cat]?.label || cat}</div>
              <div style={{ fontSize: '0.7rem', color: '#888', marginTop: '3px' }}>
                {CAT_LABEL[cat]?.desc}
              </div>
            </button>
          ))}
        </div>

        <h2 style={{ fontSize: '0.9rem', color: '#aaa', marginTop: '20px' }}>
          LEVEL <span style={{ color: '#555' }}>({levelList.length})</span>
        </h2>
        <select value={level} onChange={e => setLevel(e.target.value)}>
          {levelList.map(l => (
            <option key={l.id} value={l.id}>{l.name}</option>
          ))}
        </select>

        <h2 style={{ fontSize: '0.9rem', color: '#aaa', marginTop: '20px' }}>DIFFICULTY</h2>
        <div style={{ display: 'flex', gap: '8px' }}>
          {DIFFICULTIES.map(d => (
            <button
              key={d}
              type="button"
              className={`option-btn ${difficulty === d ? 'selected' : ''}`}
              style={{ flex: 1 }}
              onClick={() => setDifficulty(d)}
            >
              {d.charAt(0).toUpperCase() + d.slice(1)}
            </button>
          ))}
        </div>

        <button type="button" onClick={handleConfirm} disabled={!level}>
          Next → Login
        </button>
        <button type="button" onClick={onBack} style={{ background: '#333', marginTop: '10px' }}>
          Back
        </button>
      </div>
    </div>
  )
}
