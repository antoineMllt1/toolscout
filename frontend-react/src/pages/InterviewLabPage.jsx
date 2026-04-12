import { useEffect, useMemo, useState } from 'react'
import AppPageHeader from '../components/AppPageHeader'
import { useAuth } from '../context/AuthContext'

const STORAGE_KEY = 'stageai_interview_lab_v1'

function buildQuestionId(item, index) {
  return `${item.category || 'question'}-${index}-${(item.question || '').slice(0, 40)}`
}

function flattenInterviewPrep(profile) {
  const prep = profile?.interview_prep || {}
  const items = [
    ...(prep.motivation_questions || []),
    ...(prep.behavioural_questions || []),
    ...((prep.role_question_sets || []).flatMap((group) =>
      (group.questions || []).map((item) => ({ ...item, category: group.track || item.category })),
    )),
  ]

  return items.map((item, index) => ({
    ...item,
    id: buildQuestionId(item, index),
  }))
}

function loadStoredState() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
  } catch {
    return {}
  }
}

function saveStoredState(nextState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(nextState))
  } catch {
    // ignore storage failures
  }
}

function analyzeAnswer(answer) {
  const text = (answer || '').trim()
  const wordCount = text ? text.split(/\s+/).length : 0
  const lower = text.toLowerCase()
  const hasMetric = /\b\d+([.,]\d+)?\b|%|x\b/.test(text)
  const hasContext = /(contexte|situation|mission|problem|context)/.test(lower)
  const hasAction = /(j'ai|i |nous avons|implemented|built|created|analys|designed|launched|automatis)/.test(lower)
  const hasResult = /(resultat|impact|outcome|gain|improved|reduced|increased|learned|appris)/.test(lower)
  const hasLearning = /(appris|learned|retenu|next time|improve|ferais diff)/.test(lower)

  const strengths = []
  const gaps = []

  if (wordCount >= 80) strengths.push('La réponse a assez de matière pour être crédible.')
  else gaps.push('La réponse est encore trop courte. Vise au moins 80 mots.')

  if (hasMetric) strengths.push('Tu apportes un signal concret avec une mesure ou un volume.')
  else gaps.push('Ajoute un chiffre, une fréquence, un volume ou un ordre de grandeur.')

  if (hasContext) strengths.push('Le contexte du problème apparaît.')
  else gaps.push('Ajoute une phrase de contexte avant de parler de tes actions.')

  if (hasAction) strengths.push('On voit mieux ce que tu as fait toi-même.')
  else gaps.push('Rends tes actions plus explicites: ce que tu as décidé, construit ou analysé.')

  if (hasResult) strengths.push('Le résultat ou l’impact est visible.')
  else gaps.push('Termine avec un résultat, même qualitatif si tu n’as pas de métrique exacte.')

  if (hasLearning) strengths.push('Tu montres un recul utile pour un entretien.')
  else gaps.push('Ajoute une ligne sur ce que tu as appris ou ce que tu referais différemment.')

  const score = [wordCount >= 80, hasMetric, hasContext, hasAction, hasResult, hasLearning].filter(Boolean).length

  return {
    score,
    scoreLabel: `${score}/6`,
    wordCount,
    strengths,
    gaps,
    rewritePrompt: `Réécris cette réponse en 90 secondes maximum avec 1 phrase de contexte, 3 actions très concrètes, 1 résultat et 1 apprentissage.`,
  }
}

function CategoryPill({ label, active, onClick }) {
  return (
    <button className={`filter-chip ${active ? 'is-active' : ''}`} type="button" onClick={onClick}>
      <span>{label}</span>
    </button>
  )
}

export default function InterviewLabPage({ onNavigate }) {
  const { user, authFetch } = useAuth()
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [selectedQuestionId, setSelectedQuestionId] = useState(null)
  const [answersById, setAnswersById] = useState({})
  const [practicedIds, setPracticedIds] = useState({})

  useEffect(() => {
    const stored = loadStoredState()
    setAnswersById(stored.answersById || {})
    setPracticedIds(stored.practicedIds || {})
    setSelectedQuestionId(stored.selectedQuestionId || null)
  }, [])

  useEffect(() => {
    if (!user) {
      setLoading(false)
      return
    }
    void loadProfile()
  }, [user])

  async function loadProfile() {
    setLoading(true)
    try {
      const response = await authFetch('/api/cv/profile')
      if (!response.ok) return
      setProfile(await response.json())
    } finally {
      setLoading(false)
    }
  }

  const allQuestions = useMemo(() => flattenInterviewPrep(profile), [profile])

  const categories = useMemo(() => {
    const values = new Set(['all'])
    allQuestions.forEach((item) => values.add(item.category || 'Other'))
    return [...values]
  }, [allQuestions])

  const visibleQuestions = useMemo(() => {
    if (selectedCategory === 'all') return allQuestions
    return allQuestions.filter((item) => (item.category || 'Other') === selectedCategory)
  }, [allQuestions, selectedCategory])

  const selectedQuestion =
    visibleQuestions.find((item) => item.id === selectedQuestionId) ||
    allQuestions.find((item) => item.id === selectedQuestionId) ||
    visibleQuestions[0] ||
    allQuestions[0] ||
    null

  useEffect(() => {
    if (!selectedQuestion && allQuestions.length) {
      setSelectedQuestionId(allQuestions[0].id)
    }
  }, [allQuestions, selectedQuestion])

  function persist(nextAnswers, nextPracticed, nextSelectedId = selectedQuestionId) {
    saveStoredState({
      answersById: nextAnswers,
      practicedIds: nextPracticed,
      selectedQuestionId: nextSelectedId,
    })
  }

  function updateAnswer(questionId, value) {
    const nextAnswers = { ...answersById, [questionId]: value }
    setAnswersById(nextAnswers)
    persist(nextAnswers, practicedIds)
  }

  function togglePracticed(questionId) {
    const nextPracticed = { ...practicedIds, [questionId]: !practicedIds[questionId] }
    setPracticedIds(nextPracticed)
    persist(answersById, nextPracticed)
  }

  function selectQuestion(questionId) {
    setSelectedQuestionId(questionId)
    persist(answersById, practicedIds, questionId)
  }

  function jumpToNext() {
    if (!selectedQuestion) return
    const currentIndex = visibleQuestions.findIndex((item) => item.id === selectedQuestion.id)
    const next = visibleQuestions[currentIndex + 1] || visibleQuestions[0]
    if (next) selectQuestion(next.id)
  }

  function chooseRandom() {
    if (!visibleQuestions.length) return
    const next = visibleQuestions[Math.floor(Math.random() * visibleQuestions.length)]
    selectQuestion(next.id)
  }

  if (!user) {
    return (
      <main className="interview-page">
        <section className="empty-panel">
          <p className="eyebrow">Compte requis</p>
          <h3>Connecte-toi pour t’entraîner sur des questions liées à ton profil candidat.</h3>
          <button className="primary-button" onClick={() => onNavigate('auth')}>
            Ouvrir la connexion
          </button>
        </section>
      </main>
    )
  }

  if (loading) {
    return (
      <main className="interview-page">
        <section className="empty-panel">
          <p className="eyebrow">Interview lab</p>
          <h3>Chargement du pack d’entretien...</h3>
        </section>
      </main>
    )
  }

  const currentAnswer = selectedQuestion ? answersById[selectedQuestion.id] || '' : ''
  const review = analyzeAnswer(currentAnswer)
  const practicedCount = Object.values(practicedIds).filter(Boolean).length
  const completionRate = allQuestions.length ? Math.round((practicedCount / allQuestions.length) * 100) : 0

  return (
    <main className="interview-page">
      <AppPageHeader
        eyebrow="Interview lab"
        title="Entrainement entretien"
        description={
          profile?.candidate_brief?.summary || 'Travaille tes reponses avec des questions liees a ton profil, tes roles cibles et tes projets.'
        }
        actions={
          <>
            <button className="primary-button" onClick={chooseRandom}>
              Question aleatoire
            </button>
            <button className="secondary-button" onClick={() => onNavigate('cv')}>
              Retour au profil
            </button>
          </>
        }
        stats={[
          { label: 'Questions', value: allQuestions.length, tone: 'tone-blue' },
          { label: 'Pratiquees', value: practicedCount, tone: 'tone-green' },
          { label: 'Progression', value: `${completionRate}%`, tone: 'tone-yellow' },
        ]}
      />

      <section className="interview-layout">
        <aside className="interview-queue panel-shell fade-stagger" style={{ '--index': 2 }}>
          <div className="panel-head">
            <div>
              <p className="eyebrow">Question bank</p>
              <h2>File d’entraînement</h2>
            </div>
          </div>

          <div className="interview-category-row">
            {categories.map((category) => (
              <CategoryPill
                key={category}
                label={category === 'all' ? 'Toutes' : category}
                active={selectedCategory === category}
                onClick={() => setSelectedCategory(category)}
              />
            ))}
          </div>

          <div className="interview-queue-stack">
            {visibleQuestions.map((item, index) => (
              <button
                key={item.id}
                type="button"
                className={`interview-queue-card ${selectedQuestion?.id === item.id ? 'is-active' : ''}`}
                onClick={() => selectQuestion(item.id)}
              >
                <div className="interview-queue-top">
                  <span className="inline-badge">{item.category}</span>
                  <span className={`inline-badge ${practicedIds[item.id] ? 'is-selected' : ''}`}>
                    {practicedIds[item.id] ? 'Pratiquee' : `Q${index + 1}`}
                  </span>
                </div>
                <strong>{item.question}</strong>
              </button>
            ))}
          </div>
        </aside>

        <section className="interview-main">
          <section className="panel-shell fade-stagger" style={{ '--index': 3 }}>
            <div className="panel-head">
              <div>
                <p className="eyebrow">{selectedQuestion?.category || 'Question'}</p>
                <h2>{selectedQuestion?.question || 'Aucune question disponible'}</h2>
              </div>
              {selectedQuestion ? (
                <button className="secondary-button" type="button" onClick={() => togglePracticed(selectedQuestion.id)}>
                  {practicedIds[selectedQuestion.id] ? 'Marquer non pratiquee' : 'Marquer pratiquee'}
                </button>
              ) : null}
            </div>

            {selectedQuestion ? (
              <div className="interview-question-shell">
                <div className="candidate-brief-grid compact">
                  <article className="candidate-brief-card">
                    <p className="eyebrow">Pourquoi elle tombe</p>
                    <h3>Intention recruteur</h3>
                    <p>{selectedQuestion.why_asked}</p>
                  </article>
                  <article className="candidate-brief-card">
                    <p className="eyebrow">Structure</p>
                    <h3>Angle de réponse</h3>
                    <p>{selectedQuestion.answer_shape}</p>
                  </article>
                </div>

                {(selectedQuestion.evidence_refs || []).length ? (
                  <div className="coach-chip-row">
                    {selectedQuestion.evidence_refs.map((item) => (
                      <span key={item} className="inline-badge">
                        {item}
                      </span>
                    ))}
                  </div>
                ) : null}

                <label className="field-stack">
                  <span>Ta réponse de travail</span>
                  <textarea
                    className="interview-answer-editor"
                    rows={14}
                    value={currentAnswer}
                    onChange={(event) => updateAnswer(selectedQuestion.id, event.target.value)}
                    placeholder="Rédige une version claire, puis lis-la à voix haute. Essaie de garder une réponse tenable en 60 à 90 secondes."
                  />
                </label>

                <div className="cv-panel-actions">
                  <button className="primary-button" type="button" onClick={jumpToNext}>
                    Question suivante
                  </button>
                  <button className="secondary-button" type="button" onClick={chooseRandom}>
                    Changer de question
                  </button>
                </div>
              </div>
            ) : (
              <div className="cv-empty-slot">Aucune question disponible. Complète ton profil candidat.</div>
            )}
          </section>
        </section>

        <aside className="interview-review panel-shell fade-stagger" style={{ '--index': 4 }}>
          <div className="panel-head">
            <div>
              <p className="eyebrow">Review</p>
              <h2>Lecture rapide</h2>
            </div>
          </div>

          <div className="review-score-card">
            <span>Score structure</span>
            <strong>{review.scoreLabel}</strong>
            <small>{review.wordCount} mots</small>
          </div>

          <div className="review-block">
            <span>Déjà solide</span>
            {review.strengths.length ? (
              <ul className="signal-list">
                {review.strengths.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p>Écris une première version pour voir les points forts apparaître.</p>
            )}
          </div>

          <div className="review-block">
            <span>À renforcer</span>
            {review.gaps.length ? (
              <ul className="signal-list">
                {review.gaps.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p>La réponse est déjà bien structurée. Raccourcis-la maintenant pour l’oral.</p>
            )}
          </div>

          <div className="review-block">
            <span>Prompt de réécriture</span>
            <p>{review.rewritePrompt}</p>
          </div>
        </aside>
      </section>
    </main>
  )
}
