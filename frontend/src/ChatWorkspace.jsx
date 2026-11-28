import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import InstagramDraft from './InstagramDraft.jsx'

const API = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const INTENTS = [
  { id: 'SET_REMINDER', label: 'Reminders', icon: '⏰', terms: ['remind', 'reminder', 'याद दिला'] },
  { id: 'CREATE_TODO', label: 'To-do', icon: '✅', terms: ['todo', 'to-do', 'task', 'टू-डू'] },
  { id: 'TRACK_EXPENSE', label: 'Expenses', icon: '💸', terms: ['expense', 'spent', 'खर्च'] },
  { id: 'PLAN_MEAL', label: 'Meals', icon: '🍲', terms: ['meal', 'breakfast', 'lunch', 'dinner', 'खाना'] },
  { id: 'DRAFT_MESSAGE', label: 'Messages', icon: '✉️', terms: ['message', 'whatsapp', 'मैसेज'] },
  { id: 'CREATE_SHOPPING_LIST', label: 'Shopping lists', icon: '🧺', terms: ['shopping list', 'grocery list'] },
  { id: 'ORDER_GROCERIES', label: 'Shopping', icon: '🛍️', terms: ['blinkit', 'zepto', 'instamart', 'shopping', 'grocery', 'order'] },
  { id: 'POST_PHOTO', label: 'Instagram', icon: '📸', terms: ['instagram', 'photo', 'reel', 'caption', 'post'] },
  { id: 'WATCH_SHOW', label: 'Watching videos', icon: '▶️', terms: ['watch', 'video', 'movie', 'show', 'series', 'netflix', 'prime'] },
  { id: 'OPEN_APP', label: 'Open apps', icon: '📱', terms: ['open', 'launch', 'app'] },
  { id: 'GENERAL_QUESTION', label: 'Questions', icon: '💡', terms: ['question', 'how', 'what', 'why'] },
  { id: 'GENERAL_CONVERSATION', label: 'Conversations', icon: '💬', terms: [] },
]

function authHeaders(token) { return { Authorization: `Bearer ${token}` } }
async function apiRequest(path, token, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { ...authHeaders(token), ...(typeof options.body === 'string' ? { 'Content-Type': 'application/json' } : {}), ...options.headers },
  })
  const data = response.status === 204 ? null : await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data?.detail
    const error = new Error(detail?.message || (typeof detail === 'string' ? detail : 'Something went wrong. Please try again.'))
    error.status = response.status
    throw error
  }
  return data
}
function categoryFor(conversation, messages) {
  const intents = messages.filter((message) => message.role === 'assistant').map((message) => message.intent).filter(Boolean).reverse()
  const intent = intents.find((value) => value !== 'GREETING') || conversation.last_intent
  if (intent) {
    const found = INTENTS.find((item) => item.id === intent)
    if (found) return found
  }
  const content = messages.map((message) => message.content).join(' ').toLowerCase()
  return INTENTS.find((item) => item.terms.some((term) => content.includes(term))) || INTENTS.find((item) => item.id === 'GENERAL_CONVERSATION')
}
function summaryFor(messages) {
  const first = messages.find((message) => message.role === 'user')?.content || 'No messages yet'
  return first.length > 86 ? `${first.slice(0, 83)}…` : first
}

function speakReply(text, language) {
  if (!text || !window.speechSynthesis || !window.SpeechSynthesisUtterance) return
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = language === 'hi' ? 'hi-IN' : 'en-IN'
  window.speechSynthesis.cancel()
  window.speechSynthesis.speak(utterance)
}

function openLoadingVideoTab() {
  const tab = window.open('about:blank', '_blank')
  if (!tab) return null
  tab.opener = null
  tab.document.title = 'Opening your video'
  const body = tab.document.body
  body.style.cssText = 'margin:0;min-height:100vh;display:grid;place-items:center;background:#000;color:white'
  const spinner = tab.document.createElement('div')
  spinner.setAttribute('role', 'status')
  spinner.setAttribute('aria-label', 'Opening your video')
  spinner.style.cssText = 'width:44px;height:44px;border:4px solid #555;border-top-color:white;border-radius:50%'
  body.append(spinner)
  spinner.animate([{ transform: 'rotate(0deg)' }, { transform: 'rotate(360deg)' }], { duration: 800, iterations: Infinity })
  return tab
}

function openVideoResult(result, tab) {
  try {
    if (result.intent !== 'WATCH_SHOW' || !result.playback?.url) return false
    const url = new URL(result.playback.url)
    if (url.protocol !== 'https:' || url.username || url.password) return false
    const target = tab && !tab.closed ? tab : openLoadingVideoTab()
    if (!target) return false
    target.opener = null
    target.location.replace(url.href)
    return true
  } catch {
    return false
  }
}

export default function ChatWorkspace({ onSignOut, token, language }) {
  const [conversations, setConversations] = useState([])
  const [messageList, setMessageList] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [grouped, setGrouped] = useState([])
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [recording, setRecording] = useState(false)
  const [notice, setNotice] = useState('')
  const [historySearch, setHistorySearch] = useState('')
  const [loading, setLoading] = useState(true)
  const scrollRef = useRef(null)
  const recorderRef = useRef(null)
  const streamRef = useRef(null)
  const mountedRef = useRef(false)
  const activeIdRef = useRef(null)
  const [requestingMic, setRequestingMic] = useState(false)
  const [videoGuide, setVideoGuide] = useState(null)
  const [dismissedDraft, setDismissedDraft] = useState(null)

  function selectConversation(id, messages) {
    setVideoGuide(null)
    activeIdRef.current = id
    setActiveId(id)
    setMessageList(messages)
  }

  const request = useCallback(async (path, options) => {
    try {
      return await apiRequest(path, token, options)
    } catch (error) {
      if (error.status === 401) onSignOut()
      throw error
    }
  }, [onSignOut, token])

  const refreshConversations = useCallback(async () => {
    const rows = await request('/conversations?limit=100')
    const hydrated = await Promise.all(rows.map(async (conversation) => {
      try {
        const messages = await request(`/conversations/${conversation.id}/messages?limit=200`)
        return { ...conversation, messages, category: categoryFor(conversation, messages), summary: summaryFor(messages) }
      } catch {
        return { ...conversation, messages: [], category: INTENTS[5], summary: conversation.title || 'Conversation' }
      }
    }))
    setConversations(hydrated)
    setGrouped(INTENTS.map((intent) => ({
      ...intent,
      conversations: hydrated.filter((conversation) => conversation.category.id === intent.id),
    })).filter((group) => group.conversations.length))
    return hydrated
  }, [request])

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const rows = await refreshConversations()
        if (!alive) return
        if (rows.length) {
          selectConversation(rows[0].id, rows[0].messages)
        } else {
          const created = await request('/conversations', {
            method: 'POST', body: JSON.stringify({ title: 'New conversation', channel: 'chat', language }),
          })
          if (!alive) return
          selectConversation(created.id, [])
          await refreshConversations()
        }
      } catch (error) { if (alive) setNotice(error.message) }
      finally { if (alive) setLoading(false) }
    })()
    return () => { alive = false }
  }, [refreshConversations, request, language])

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messageList, busy])

  async function newConversation() {
    if (busy || recording || requestingMic) return
    setNotice('')
    setBusy(true)
    try {
      const created = await request('/conversations', {
        method: 'POST', body: JSON.stringify({ title: 'New conversation', channel: 'chat', language }),
      })
      selectConversation(created.id, [])
      await refreshConversations()
      setDrawerOpen(false)
    } catch (error) { setNotice(error.message) }
    finally { setBusy(false) }
  }

  async function openConversation(conversation) {
    if (busy || recording || requestingMic) return
    selectConversation(conversation.id, conversation.messages)
    setDrawerOpen(false)
    try {
      const messages = await request(`/conversations/${conversation.id}/messages?limit=200`)
      if (activeIdRef.current === conversation.id) setMessageList(messages)
    } catch (error) { setNotice(error.message) }
  }

  async function sendText(text = draft) {
    const content = text.trim()
    if (!content || !activeId || busy || recording || requestingMic) return
    const wantsVideo = /\bwatch\b|\b(?:play|find|search for|open)\b.*\b(?:video|series|movie|show|episode|netflix|prime|youtube)\b|(?:वीडियो|फ़िल्म|सीरीज़).*(?:देख|चल|खोल)/i.test(content)
    const tab = wantsVideo ? openLoadingVideoTab() : null
    let videoOpened = false
    setDraft('')
    setNotice('')
    setMessageList((current) => [...current, { id: `pending-${Date.now()}`, role: 'user', content, language }])
    setBusy(true)
    try {
      const result = await request('/assistant/chat', {
        method: 'POST', body: JSON.stringify({ conversation_id: activeId, message: content }),
      })
      setMessageList((current) => [
        ...current.filter((item) => !String(item.id).startsWith('pending-')),
        { id: result.user_message_id, role: 'user', content, language: result.language },
        { id: result.assistant_message_id, role: 'assistant', content: result.response, language: result.language, intent: result.intent, source: result.source, shopping: result.shopping, playback: result.playback, daily_actions: result.daily_actions },
      ])
      videoOpened = openVideoResult(result, tab)
      if (result.playback?.url && !videoOpened) setNotice('Use the video link if your browser blocked the new tab.')
      void refreshConversations().catch(() => {})
    } catch (error) {
      setMessageList((current) => current.filter((item) => !String(item.id).startsWith('pending-')))
      setDraft(content)
      setNotice(error.message)
    } finally {
      if (tab && !videoOpened) tab.close()
      setBusy(false)
    }
  }

  async function connectGoogleCalendar() {
    setBusy(true)
    setNotice('')
    try {
      const result = await request('/daily/google/calendar/connect')
      window.location.assign(result.authorization_url)
    } catch (error) { setNotice(error.message); setBusy(false) }
  }

  async function confirmDailyAction(actionId) {
    setBusy(true)
    setNotice('')
    try {
      const result = await request(`/daily/actions/${actionId}/confirm`, { method: 'POST' })
      setMessageList((current) => current.map((message) => ({
        ...message,
        daily_actions: message.daily_actions?.map((action) => action.id === actionId
          ? { ...action, status: result.status, result: result.result }
          : action),
      })))
      setNotice(language === 'hi' ? 'आपका काम सेव हो गया।' : 'Your action has been saved.')
    } catch (error) { setNotice(error.message) }
    finally { setBusy(false) }
  }

  async function guideVideo(platform, step, reply, audio) {
    const body = new FormData()
    body.append('language', language)
    body.append('platform', platform)
    body.append('step', step)
    if (reply) body.append('reply', reply)
    if (audio) body.append('audio', audio, 'voice-message.webm')
    setBusy(true)
    setNotice('')
    try {
      const result = await request('/watch-show/troubleshoot', { method: 'POST', body })
      setVideoGuide({ ...result, platform })
      speakReply(result.response, language)
    } catch (error) { setNotice(error.message) }
    finally { setBusy(false) }
  }

  async function toggleMic() {
    if (recording) {
      setBusy(true)
      recorderRef.current?.stop()
      setRecording(false)
      return
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setNotice('Microphone recording is not supported in this browser.')
      return
    }
    if (!activeId || busy || requestingMic) return
    setRequestingMic(true)
    setNotice('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!mountedRef.current) {
        stream.getTracks().forEach((track) => track.stop())
        return
      }
      streamRef.current = stream
      const chunks = []
      const mime = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4'].find((type) => MediaRecorder.isTypeSupported(type))
      const recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream)
      recorderRef.current = recorder
      recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data) }
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop())
        streamRef.current = null
        const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
        if (!mountedRef.current) return
        if (!blob.size) { setBusy(false); setNotice('No audio was recorded. Please try again.'); return }
        if (videoGuide && !videoGuide.done) {
          await guideVideo(videoGuide.platform, videoGuide.step, null, blob)
          return
        }
        setBusy(true)
        setNotice('')
        try {
          const form = new FormData()
          form.append('audio', blob, 'voice-message.webm')
          const result = await request(`/assistant/audio?conversation_id=${activeId}`, { method: 'POST', body: form })
          setMessageList((current) => [
            ...current,
            { id: result.user_message_id, role: 'user', content: result.transcription || '🎙️ Voice message', language: result.language },
            { id: result.assistant_message_id, role: 'assistant', content: result.response, language: result.language, intent: result.intent, source: result.source, shopping: result.shopping, playback: result.playback, daily_actions: result.daily_actions },
          ])
          if (!mountedRef.current) return
          speakReply(result.response, result.language || language)
          if (result.playback?.url && !openVideoResult(result)) setNotice('Use the video link if your browser blocked the new tab.')
          void refreshConversations().catch(() => {})
        } catch (error) { setNotice(error.message) }
        finally {
          setBusy(false)
        }
      }
      recorder.start()
      setRecording(true)
    } catch {
      streamRef.current?.getTracks().forEach((track) => track.stop())
      streamRef.current = null
      setNotice('Could not start microphone recording. Check your microphone permissions.')
    } finally {
      if (mountedRef.current) setRequestingMic(false)
    }
  }

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      window.speechSynthesis?.cancel()
      const recorder = recorderRef.current
      if (recorder) {
        recorder.onstop = null
        if (recorder.state === 'recording') recorder.stop()
      }
      streamRef.current?.getTracks().forEach((track) => track.stop())
    }
  }, [])

  const activeConversation = useMemo(() => conversations.find((item) => item.id === activeId), [conversations, activeId])
  const visibleGroups = useMemo(() => grouped.map((group) => ({ ...group, conversations: group.conversations.filter((conversation) => `${conversation.title || ''} ${conversation.summary}`.toLowerCase().includes(historySearch.toLowerCase())) })).filter((group) => group.conversations.length), [grouped, historySearch])

  return (
    <main className="chat-app">
      <header className="chat-topbar">
        <a className="brand" href="#chat"><span className="brand-mark">a</span><span>apnasathi<span className="brand-dot">.</span></span></a>
        <div className="chat-top-actions">
          <span className="language-pill">{language === 'hi' ? 'हिन्दी' : 'English'}</span>
          <button className="icon-button" type="button" onClick={() => setDrawerOpen(true)} aria-label="Open conversation sidebar"><span className="hamburger"><i></i><i></i><i></i></span></button>
          <button className="sign-out-button" type="button" onClick={onSignOut}>Sign out</button>
        </div>
      </header>

      <section className="chat-layout">
        <div className="chat-main">
          <div className="chat-heading">
            <div><span className="chat-eyebrow">YOUR PERSONAL ASSISTANT</span><h1>How can I help today?</h1><p>Ask anything, or tap the microphone and speak naturally.</p></div>
            <div className="chat-heading-actions"><button className="new-chat-button" type="button" onClick={() => void connectGoogleCalendar()} disabled={busy || recording || requestingMic}>📅 Connect Calendar</button>            <button className="new-chat-button" type="button" onClick={newConversation} disabled={busy || recording || requestingMic}>＋ New chat</button></div>
          </div>

          <div className="chat-thread" role="log" aria-label="Chat messages">
            {loading && <div className="chat-empty">Loading your conversations…</div>}
            {!loading && messageList.length === 0 && (
              <div className="chat-empty-state">
                <div className="welcome-orb">a</div>
                <h2>Namaste! What would you like to do?</h2>
                <p>Your conversations will stay here, so you can pick up where you left off.</p>
                <div className="suggestion-row">
                  <button onClick={() => sendText('Show me my previous Blinkit order details')} type="button">🛍️ My previous Blinkit order</button>
                  <button onClick={() => sendText('Help me post a photo on Instagram')} type="button">📸 Instagram help</button>
                  <button onClick={() => sendText('Help me watch a video')} type="button">▶️ Watch a video</button>
                </div>
              </div>
            )}
            {messageList.map((message) => (
              <article className={`chat-message chat-message-${message.role}`} key={message.id}>
                {message.role === 'assistant' && <span className="assistant-avatar">a</span>}
                <div className="chat-message-body">
                  <span className="chat-author">{message.role === 'user' ? 'You' : 'ApnaSathi'}</span>
                  <p>{message.content}</p>
                  {message.daily_actions?.length > 0 && <div className="daily-action-list" aria-label="Actions awaiting your confirmation">
                    {message.daily_actions.map((action) => <div className="daily-action-card" key={action.id}>
                      <div><strong>{({ SET_REMINDER: '⏰ Reminder', CREATE_TODO: '✅ To-do', DRAFT_MESSAGE: '✉️ Message draft', CREATE_SHOPPING_LIST: '🧺 Shopping list', ADD_SHOPPING_ITEM: '🛒 Shopping item', TRACK_EXPENSE: '💸 Expense', PLAN_MEAL: '🍲 Meal plan', CREATE_CALENDAR_EVENT: '📅 Calendar event' })[action.intent] || action.intent}</strong>
                        <span>{Object.values(action.payload || {}).filter((value) => typeof value === 'string' || typeof value === 'number').join(' · ')}</span>
                      </div>
                      {action.status === 'awaiting_confirmation'
                        ? <button type="button" disabled={busy} onClick={() => void confirmDailyAction(action.id)}>{language === 'hi' ? 'पुष्टि करें' : 'Confirm & save'}</button>
                        : <span className="daily-action-status">✓ {action.status === 'completed' ? 'Saved' : action.status}</span>}
                    </div>)}
                  </div>}
                  {message.playback && (
                    <div className="suggestion-row">
                      {message.playback.options?.map((option) => (
                        <a key={option.url} className="voice-link" href={option.url} target="_blank" rel="noopener noreferrer" onClick={(event) => {
                          if (option.kind === 'ready') {
                            if (openVideoResult({ intent: 'WATCH_SHOW', playback: option })) event.preventDefault()
                            void guideVideo(option.platform, 'playing')
                          }
                        }}>{option.title}{option.kind === 'search' ? ` · Search ${option.platform}` : ''}</a>
                      ))}
                      {message.playback.url && <a className="voice-link" href={message.playback.url} target="_blank" rel="noopener noreferrer">{message.playback.kind === 'search' ? 'Search' : 'Open in'} {message.playback.platform}</a>}
                      {message.playback.kind === 'ready' && message.id === messageList.at(-1)?.id && !videoGuide && <>
                        <span>{language === 'hi' ? 'क्या वीडियो चल रहा है?' : 'Is the video playing?'}</span>
                        {['Yes', 'No'].map((reply) => <button key={reply} type="button" disabled={busy || recording} onClick={() => void guideVideo(message.playback.platform, 'playing', reply)}>{reply}</button>)}
                      </>}
                    </div>
                  )}
                  {message.intent === 'POST_PHOTO' && message.id === messageList.at(-1)?.id && dismissedDraft !== message.id && (
                    <InstagramDraft key={message.id} request={request} onCancel={() => setDismissedDraft(message.id)} />
                  )}
                  {message.shopping && message.id === messageList.findLast((item) => item.shopping)?.id && (
                    <div className="suggestion-row">
                      {message.shopping.session?.items?.length > 0 && (
                        <ul aria-label="Shopping list">
                          {message.shopping.session.items.map((item, index) => {
                            const link = message.shopping.actions?.[index]
                            return <li key={item}>{link
                              ? <a href={link.url} target={link.kind === 'product' ? undefined : '_blank'} rel="noopener noreferrer">{link.label}</a>
                              : item}</li>
                          })}
                        </ul>
                      )}
                      {!message.shopping.done && message.id === messageList.at(-1)?.id && <>
                        {message.shopping.choices.map((choice) => (
                          <button key={choice} type="button" onClick={() => void sendText(choice)} disabled={busy || recording}>{choice}</button>
                        ))}
                        <button type="button" onClick={() => void sendText('Cancel')} disabled={busy || recording}>End shopping</button>
                      </>}
                    </div>
                  )}
                  {message.role === 'assistant' && message.source === 'semantic_cache' && <span className="reuse-note">↻ Reused your previous guidance</span>}
                </div>
              </article>
            ))}
            {videoGuide && <section className="chat-message" aria-label="Playback troubleshooting">
              <div className="chat-message-body">
                <p>{videoGuide.response}</p>
                {!videoGuide.done && <div className="suggestion-row">
                  {['Yes', 'No'].map((reply) => <button key={reply} type="button" disabled={busy || recording} onClick={() => void guideVideo(videoGuide.platform, videoGuide.step, reply)}>{reply}</button>)}
                </div>}
                <button type="button" disabled={busy || recording} onClick={() => setVideoGuide(null)}>Close playback guide</button>
              </div>
            </section>}
            {busy && <div className="assistant-thinking"><span></span><span></span><span></span><small>ApnaSathi is thinking</small></div>}
            <div ref={scrollRef} />
          </div>

          {notice && <div className="chat-notice" role="status">{notice}</div>}
          <form className="chat-composer" onSubmit={(event) => { event.preventDefault(); void sendText() }}>
            <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void sendText() } }} placeholder={language === 'hi' ? 'यहाँ अपना संदेश लिखें…' : 'Message ApnaSathi…'} rows="1" disabled={busy || loading} />
            <button className={`mic-button ${recording ? 'mic-recording' : ''}`} type="button" onClick={() => void toggleMic()} disabled={busy || loading || requestingMic || !activeId} aria-label={recording ? 'Stop recording and send' : 'Speak to ApnaSathi'}>{recording ? '■' : '🎙'}</button>
            <button className="send-button" type="submit" disabled={!draft.trim() || busy || loading || !activeId || recording || requestingMic} aria-label="Send message">↑</button>
          </form>
          <p className="composer-footnote">Your conversations are private to your account.</p>
        </div>
      </section>

      {drawerOpen && <div className="drawer-scrim" onClick={() => setDrawerOpen(false)} role="presentation">
        <aside className="intent-drawer" onClick={(event) => event.stopPropagation()} aria-label="Your conversations">
          <div className="drawer-header"><div><span className="chat-eyebrow">YOUR HISTORY</span><h2>Conversations</h2></div><button className="drawer-close" onClick={() => setDrawerOpen(false)} type="button" aria-label="Close sidebar">×</button></div>
          <button className="drawer-new-chat" type="button" onClick={newConversation}>＋ Start a new chat</button>
          <input className="history-search" value={historySearch} onChange={(event) => setHistorySearch(event.target.value)} placeholder="Search your conversations…" aria-label="Search conversation history" />
          <div className="intent-groups">
            {visibleGroups.length === 0 && <p className="drawer-empty">Your previous chats will appear here, organised by what you asked ApnaSathi to do.</p>}
            {visibleGroups.map((group) => <section className="intent-group" key={group.id}>
              <h3><span>{group.icon}</span>{group.label}<small>{group.conversations.length}</small></h3>
              {group.conversations.map((conversation) => <button className={`history-item ${activeId === conversation.id ? 'history-item-active' : ''}`} key={conversation.id} type="button" onClick={() => void openConversation(conversation)}>
                <strong>{conversation.title || group.label}</strong><span>{conversation.summary}</span><time>{new Date(conversation.updated_at).toLocaleDateString()}</time>
              </button>)}
            </section>)}
          </div>
          <p className="drawer-footer">Only you can see your conversation history.</p>
        </aside>
      </div>}
    </main>
  )
}
