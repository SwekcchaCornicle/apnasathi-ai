import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

const API = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const INTENTS = [
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
    headers: { ...authHeaders(token), ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers },
  })
  const data = response.status === 204 ? null : await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data?.detail?.message || data?.detail || 'Something went wrong. Please try again.')
  return data
}
function categoryFor(conversation, messages) {
  const intents = messages.map((message) => message.intent).filter(Boolean)
  const intent = intents.find((value) => value !== 'GREETING') || conversation.last_intent
  if (intent) {
    const found = INTENTS.find((item) => item.id === intent)
    if (found) return found
  }
  const content = messages.map((message) => message.content).join(' ').toLowerCase()
  return INTENTS.find((item) => item.terms.some((term) => content.includes(term))) || INTENTS[5]
}
function summaryFor(messages) {
  const first = messages.find((message) => message.role === 'user')?.content || 'No messages yet'
  return first.length > 86 ? `${first.slice(0, 83)}…` : first
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
  const chunksRef = useRef([])

  const refreshConversations = useCallback(async () => {
    const rows = await apiRequest('/conversations?limit=100', token)
    const hydrated = await Promise.all(rows.map(async (conversation) => {
      try {
        const messages = await apiRequest(`/conversations/${conversation.id}/messages?limit=200`, token)
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
  }, [token])

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const rows = await refreshConversations()
        if (!alive) return
        if (rows.length) {
          setActiveId(rows[0].id)
          setMessageList(rows[0].messages)
        } else {
          const created = await apiRequest('/conversations', token, {
            method: 'POST', body: JSON.stringify({ title: 'New conversation', channel: 'chat', language }),
          })
          if (!alive) return
          setActiveId(created.id)
          await refreshConversations()
        }
      } catch (error) { if (alive) setNotice(error.message) }
      finally { if (alive) setLoading(false) }
    })()
    return () => { alive = false }
  }, [refreshConversations, token, language])

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messageList, busy])

  async function newConversation() {
    setNotice('')
    setBusy(true)
    try {
      const created = await apiRequest('/conversations', token, {
        method: 'POST', body: JSON.stringify({ title: 'New conversation', channel: 'chat', language }),
      })
      setActiveId(created.id)
      setMessageList([])
      await refreshConversations()
      setDrawerOpen(false)
    } catch (error) { setNotice(error.message) }
    finally { setBusy(false) }
  }

  async function openConversation(conversation) {
    setActiveId(conversation.id)
    setMessageList(conversation.messages)
    setDrawerOpen(false)
    try {
      const messages = await apiRequest(`/conversations/${conversation.id}/messages?limit=200`, token)
      setMessageList(messages)
    } catch (error) { setNotice(error.message) }
  }

  async function sendText(text = draft) {
    const content = text.trim()
    if (!content || !activeId || busy) return
    setDraft('')
    setNotice('')
    setMessageList((current) => [...current, { id: `pending-${Date.now()}`, role: 'user', content, language }])
    setBusy(true)
    try {
      const result = await apiRequest('/assistant/chat', token, {
        method: 'POST', body: JSON.stringify({ conversation_id: activeId, message: content }),
      })
      setMessageList((current) => [
        ...current.filter((item) => !String(item.id).startsWith('pending-')),
        { id: result.user_message_id, role: 'user', content, language: result.language },
        { id: result.assistant_message_id, role: 'assistant', content: result.response, language: result.language, intent: result.intent, source: result.source },
      ])
      await refreshConversations()
    } catch (error) {
      setMessageList((current) => current.filter((item) => !String(item.id).startsWith('pending-')))
      setDraft(content)
      setNotice(error.message)
    } finally { setBusy(false) }
  }

  async function toggleMic() {
    if (recording) {
      recorderRef.current?.stop()
      setRecording(false)
      return
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setNotice('Microphone recording is not supported in this browser.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []
      const mime = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4'].find((type) => MediaRecorder.isTypeSupported(type))
      const recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream)
      recorderRef.current = recorder
      recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data) }
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop())
        streamRef.current = null
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        if (!blob.size) return
        setBusy(true)
        setNotice('')
        try {
          const form = new FormData()
          form.append('audio', blob, 'voice-message.webm')
          const response = await fetch(`${API}/assistant/audio?conversation_id=${activeId}`, { method: 'POST', headers: authHeaders(token), body: form })
          const result = await response.json().catch(() => ({}))
          if (!response.ok) throw new Error(result?.detail || 'Voice request failed.')
          setMessageList((current) => [
            ...current,
            { id: result.user_message_id, role: 'user', content: '🎙️ Voice message', language: result.language },
            { id: result.assistant_message_id, role: 'assistant', content: result.response, language: result.language, intent: result.intent, source: result.source },
          ])
          await refreshConversations()
        } catch (error) { setNotice(error.message) }
        finally { setBusy(false) }
      }
      recorder.start()
      setRecording(true)
    } catch { setNotice('Please allow microphone access to talk to ApnaSathi.') }
  }

  useEffect(() => () => {
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
    streamRef.current?.getTracks().forEach((track) => track.stop())
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
            <button className="new-chat-button" type="button" onClick={newConversation} disabled={busy}>＋ New chat</button>
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
                  {message.role === 'assistant' && message.source === 'semantic_cache' && <span className="reuse-note">↻ Reused your previous guidance</span>}
                </div>
              </article>
            ))}
            {busy && <div className="assistant-thinking"><span></span><span></span><span></span><small>ApnaSathi is thinking</small></div>}
            <div ref={scrollRef} />
          </div>

          {notice && <div className="chat-notice" role="status">{notice}</div>}
          <form className="chat-composer" onSubmit={(event) => { event.preventDefault(); void sendText() }}>
            <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void sendText() } }} placeholder={language === 'hi' ? 'यहाँ अपना संदेश लिखें…' : 'Message ApnaSathi…'} rows="1" disabled={busy || loading} />
            <button className={`mic-button ${recording ? 'mic-recording' : ''}`} type="button" onClick={() => void toggleMic()} disabled={busy || loading} aria-label={recording ? 'Stop recording and send' : 'Speak to ApnaSathi'}>{recording ? '■' : '🎙'}</button>
            <button className="send-button" type="submit" disabled={!draft.trim() || busy || loading} aria-label="Send message">↑</button>
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
