import { useEffect, useRef, useState } from 'react'
import { deleteRecording, getRecordings, saveRecording } from './audioStorage.js'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

function formatDate(timestamp) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(timestamp)
}

function fileExtension(mimeType) {
  if (mimeType.includes('ogg')) return 'ogg'
  if (mimeType.includes('mp4')) return 'm4a'
  return 'webm'
}

export default function AudioRecorder({ onSignOut }) {
  const [recordings, setRecordings] = useState([])
  const [isRecording, setIsRecording] = useState(false)
  const [message, setMessage] = useState('')
  const [turns, setTurns] = useState([])
  const [shopping, setShopping] = useState(null)
  const [instagramStep, setInstagramStep] = useState('')
  const [instagramBusy, setInstagramBusy] = useState(false)
  const [instagramDraft, setInstagramDraft] = useState(null)
  const [requestPending, setRequestPending] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const latestTurn = useRef(null)
  const [replyAudio, setReplyAudio] = useState('')
  const [replyVersion, setReplyVersion] = useState(0)
  const [guide, setGuide] = useState(null)
  const [guidePending, setGuidePending] = useState(false)
  const replyPlayer = useRef(null)
  const [backendStatus, setBackendStatus] = useState('checking')
  const objectUrls = useRef(new Map())
  const mediaRecorder = useRef(null)
  const audioStream = useRef(null)
  const audioChunks = useRef([])

  useEffect(() => {
    let isMounted = true

    getRecordings()
      .then((savedRecordings) => {
        if (!isMounted) return
        const withUrls = savedRecordings.map((recording) => {
          const audioUrl = URL.createObjectURL(recording.audio)
          objectUrls.current.set(recording.id, audioUrl)
          return { ...recording, audioUrl }
        })
        setRecordings(withUrls)
      })
      .catch(() => setMessage('Your browser could not open local audio storage.'))

    fetch(`${API_BASE_URL}/health`)
      .then((response) => {
        if (!response.ok) throw new Error('Backend is unavailable')
        return response.json()
      })
      .then(() => setBackendStatus('connected'))
      .catch(() => setBackendStatus('offline'))

    return () => {
      isMounted = false
      if (mediaRecorder.current?.state === 'recording') {
        mediaRecorder.current.onstop = null
        mediaRecorder.current.stop()
      }
      audioStream.current?.getTracks().forEach((track) => track.stop())
      objectUrls.current.forEach((audioUrl) => URL.revokeObjectURL(audioUrl))
    }
  }, [])

  useEffect(() => {
    latestTurn.current?.scrollIntoView({ block: 'nearest' })
  }, [turns])

  function addTurn(text, response, playback, instagram, attachment, shoppingTurn) {
    if (!text?.trim() && !response?.trim() && !attachment) return
    setTurns((current) => [...current, { text: text?.trim(), response: response?.trim(), playback, instagram, attachment, shopping: shoppingTurn }])
  }

  function showReply(result) {
    if (result.intent === 'POST_PHOTO') {
      setInstagramDraft(null)
      setInstagramStep('image')
    }
    if (result.shopping) {
      const next = result.shopping
      setShopping(next.done ? null : next)
      if (next.launch && next.action) window.open(next.action.url, '_blank', 'noopener,noreferrer')
    }
    addTurn(result.text, result.response, null, result.intent === 'POST_PHOTO' ? result : null, null, result.shopping)
    setMessage('')
    setIsSpeaking(false)
    setReplyVersion((version) => version + 1)
    setReplyAudio(result.voice?.status === 'ready'
      ? `data:${result.voice.mime_type};base64,${result.voice.data}`
      : '')
  }

  useEffect(() => {
    if (instagramStep !== 'authorization') return
    let active = true
    const timer = window.setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/instagram/status`, { cache: 'no-store' })
        if (!active) return
        if (response.status === 404) {
          active = false
          setInstagramStep('')
          setMessage('The Instagram draft expired. Ask to post a photo again.')
          return
        }
        if (!response.ok) return
        const result = await response.json()
        if (!active) return
        if (result.step === 'caption') {
          active = false
          setInstagramStep('review')
          addTurn(null, 'Instagram is connected. Review your caption and post when ready.', null, { step: 'review' })
        } else if (result.step === 'failed') {
          active = false
          setInstagramStep('')
          setMessage('Instagram authorization did not complete. Ask to post a photo again.')
        }
      } catch {
        // Keep waiting while the authorization tab is open.
      }
    }, 1500)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [instagramStep])

  async function sendInstagramForm(path, body, consentTab = null) {
    setInstagramBusy(true)
    setMessage('')
    try {
      const response = await fetch(`${API_BASE_URL}/instagram/${path}`, { method: 'POST', body })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail || 'Instagram request failed')
      setInstagramStep(result.step)
      addTurn(null, result.response, null, result)
      if (consentTab && !consentTab.closed && result.step === 'authorization') {
        try {
          consentTab.location.replace(result.action.url)
        } catch {
          consentTab.close()
        }
      }
    } catch (error) {
      consentTab?.close()
      addTurn(null, error.message)
    } finally {
      setInstagramBusy(false)
    }
  }

  async function answerShopping(answer) {
    if (!shopping) return
    setRequestPending(true)
    replyPlayer.current?.pause()
    try {
      const body = new FormData()
      body.append('session', JSON.stringify(shopping.session))
      body.append('language', shopping.language)
      body.append('answer', answer)
      const response = await fetch(`${API_BASE_URL}/shopping/reply`, { method: 'POST', body })
      if (!response.ok) throw new Error('The shopping guide could not process that answer.')
      showReply(await response.json())
    } catch (error) {
      setMessage(error.message)
    } finally {
      setRequestPending(false)
    }
  }

  async function advanceGuide(step, language, platform, audioBlob) {
    setGuidePending(true)
    try {
      const body = new FormData()
      body.append('step', step)
      body.append('language', language)
      body.append('platform', platform)
      if (audioBlob) body.append('audio', audioBlob, `answer.${fileExtension(audioBlob.type)}`)
      const response = await fetch(`${API_BASE_URL}/watch-show/troubleshoot`, { method: 'POST', body })
      if (!response.ok) throw new Error('Guide request failed')
      const result = await response.json()
      showReply(result)
      setGuide(result.done ? null : { step: result.step, language, platform })
    } catch {
      setMessage('Could not reach the playback guide. Try recording your answer again.')
    } finally {
      setGuidePending(false)
    }
  }

  async function transcribeCaption(audioBlob, draftImage) {
    setInstagramBusy(true)
    try {
      const body = new FormData()
      body.append('audio', audioBlob, `caption.${fileExtension(audioBlob.type)}`)
      const response = await fetch(`${API_BASE_URL}/instagram/caption`, { method: 'POST', body })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail || 'Could not transcribe the caption.')
      setInstagramDraft((draft) => draft?.image === draftImage
        ? { ...draft, caption: [draft.caption.trim(), result.text].filter(Boolean).join(' ').slice(0, 2200) }
        : draft)
    } catch (error) {
      setMessage(error.message)
    } finally {
      setInstagramBusy(false)
    }
  }

  async function startRecording() {
    replyPlayer.current?.pause()
    setIsSpeaking(false)
    if (!guide) {
      setMessage('')
      setReplyAudio('')
    }

    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setMessage('Audio recording is not supported in this browser. Try a current version of Chrome, Edge, or Firefox.')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      audioStream.current = stream
      audioChunks.current = []

      const preferredType = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4']
        .find((type) => MediaRecorder.isTypeSupported(type))
      const recorder = preferredType ? new MediaRecorder(stream, { mimeType: preferredType }) : new MediaRecorder(stream)

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunks.current.push(event.data)
      }

      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop())
        audioStream.current = null

        const audioBlob = new Blob(audioChunks.current, { type: recorder.mimeType || 'audio/webm' })
        if (audioBlob.size === 0) {
          setMessage('No audio was captured. Please try recording again.')
          return
        }

        if (instagramStep === 'caption' && instagramDraft) {
          await transcribeCaption(audioBlob, instagramDraft.image)
          return
        }

        // Guide replies go to Whisper only and are skipped by recording history.
        if (guide) {
          await advanceGuide(guide.step, guide.language, guide.platform, audioBlob)
          return
        }

        setRequestPending(true)
        try {
          const id = await saveRecording(audioBlob)
          const audioUrl = URL.createObjectURL(audioBlob)
          objectUrls.current.set(id, audioUrl)
          setRecordings((current) => [{ id, audio: audioBlob, createdAt: Date.now(), mimeType: audioBlob.type, audioUrl }, ...current])
        } catch {
          setMessage('The recording could not be saved locally. The voice request will still be sent.')
        }

        try {
          const formData = new FormData()
          formData.append('audio', audioBlob, `recording-${Date.now()}.${fileExtension(audioBlob.type)}`)
          if (shopping) {
            // Continue the current shopping step with Whisper and the shopping agent.
            formData.append('shopping_session', JSON.stringify(shopping.session))
            formData.append('shopping_language', shopping.language)
          }
          const response = await fetch(`${API_BASE_URL}/upload-audio`, {
            method: 'POST',
            body: formData,
          })

          if (!response.ok) {
            const result = await response.json().catch(() => ({}))
            throw new Error(result.detail || 'Audio upload failed')
          }

          const result = await response.json()
          setBackendStatus('connected')
          if (result.intent === 'WATCH_SHOW' && result.playback_status === 'ready' && result.playback_url) {
            const platform = result.playback_platform || 'the streaming service'
            const language = result.response_language || 'en'
            // The app opens a tab only after the classified watch request has a URL.
            const videoTab = window.open('about:blank', '_blank')
            let step = 'tab'
            if (videoTab && !videoTab.closed) {
              try {
                videoTab.opener = null
                const document = videoTab.document
                document.title = 'Opening video'
                const style = document.createElement('style')
                style.textContent = `
                  body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #000; }
                  .spinner { width: 42px; height: 42px; border: 3px solid #383838;
                    border-top-color: #fff; border-radius: 50%; animation: spin .8s linear infinite; }
                  @keyframes spin { to { transform: rotate(360deg); } }
                  @media (prefers-reduced-motion: reduce) { .spinner { animation: none; } }
                `
                const spinner = document.createElement('div')
                spinner.className = 'spinner'
                spinner.setAttribute('role', 'status')
                spinner.setAttribute('aria-label', 'Opening video')
                document.head.append(style)
                document.body.replaceChildren(spinner)
                videoTab.location.replace(result.playback_url)
                step = 'opened'
              } catch {
                videoTab.close()
              }
            }
            addTurn(result.text, result.response, { url: result.playback_url, platform, language })
            setGuide({ step, language, platform })
            await advanceGuide(step, language, platform)
          } else {
            showReply(result)
          }
        } catch (error) {
          setBackendStatus('offline')
          setMessage(`The voice request failed: ${error.message}`)
        } finally {
          setRequestPending(false)
        }
      }

      recorder.start()
      mediaRecorder.current = recorder
      setIsRecording(true)
    } catch {
      setMessage('Microphone access was not available. Allow microphone access and try again.')
    }
  }

  function stopRecording() {
    if (mediaRecorder.current?.state === 'recording') {
      mediaRecorder.current.stop()
      mediaRecorder.current = null
      setIsRecording(false)
    }
  }

  async function removeRecording(id) {
    try {
      await deleteRecording(id)
      const audioUrl = objectUrls.current.get(id)
      if (audioUrl) URL.revokeObjectURL(audioUrl)
      objectUrls.current.delete(id)
      setRecordings((current) => current.filter((recording) => recording.id !== id))
      setMessage('Recording deleted from this device.')
    } catch {
      setMessage('Could not delete that recording. Please try again.')
    }
  }

  const busy = requestPending || guidePending || instagramBusy
  const voiceState = isRecording ? 'listening' : busy ? 'thinking' : isSpeaking ? 'speaking' : 'ready'
  const dictatingCaption = instagramStep === 'caption' && Boolean(instagramDraft)
  const voiceLabel = { listening: 'Listening…', thinking: 'Thinking…', speaking: 'Speaking…', ready: dictatingCaption ? 'Tap to dictate your caption' : guide || shopping ? 'Waiting for your answer' : 'Tap to talk' }[voiceState]

  return (
    <main className="recorder-page">
      <header className="recorder-header">
        <a className="brand brand-light" href="/" aria-label="ApnaSathi home" onClick={(event) => { event.preventDefault(); onSignOut() }}>
          <span className="brand-mark">a</span><span>apnasathi<span className="brand-dot">.</span></span>
        </a>
        <button className="sign-out-button" onClick={onSignOut} type="button">Sign out</button>
      </header>

      <section className="recorder-content">
        <div className="recorder-status"><span className={`status-dot status-${backendStatus}`} />{backendStatus === 'checking' ? 'Checking backend…' : backendStatus === 'connected' ? 'Backend connected' : 'Backend offline'}</div>
        <h1 className="voice-title">Voice conversation</h1>
        <div className="voice-session">
          <div className="voice-transcript" role="log" aria-label="Conversation">
            {turns.map((turn, index) => (
              <div className="voice-turn" key={index}>
                {(turn.text || turn.attachment) && (
                  <div className="voice-bubble voice-bubble-user">
                    <strong>You</strong>
                    {turn.text}
                    {turn.attachment && (
                      <img className="voice-photo" src={turn.attachment.url} alt={`Attached photo: ${turn.attachment.name}`} />
                    )}
                  </div>
                )}
                {(turn.response || turn.playback) && (
                  <div className="voice-bubble">
                    <strong>ApnaSathi</strong>
                    {turn.response}
                    {turn.instagram?.step === 'image' && instagramStep === 'image' && index === turns.findLastIndex(({ instagram }) => instagram?.step === 'image') && (
                      <label className="voice-link">
                        Attach JPEG photo
                        <input
                          type="file"
                          accept="image/jpeg"
                          aria-label="Attach JPEG photo"
                          disabled={busy || isRecording}
                          onChange={(event) => {
                            const image = event.currentTarget.files?.[0]
                            event.currentTarget.value = ''
                            if (!image) return
                            // Keep the draft local until the user explicitly chooses to connect.
                            const url = URL.createObjectURL(image)
                            objectUrls.current.set(Symbol('instagram-photo'), url)
                            setInstagramDraft({ image, caption: '' })
                            setInstagramStep('caption')
                            addTurn(null, null, null, null, { url, name: image.name })
                            addTurn(null, 'What caption would you like to use?', null, { step: 'caption' })
                          }}
                        />
                      </label>
                    )}
                    {turn.instagram?.step === 'authorization' && instagramStep === 'authorization' && index === turns.findLastIndex(({ instagram }) => instagram?.step === 'authorization') && (
                      <a className="voice-link" href={turn.instagram.action.url} target="_blank" rel="noopener noreferrer">
                        Connect Instagram ↗
                      </a>
                    )}
                    {turn.instagram?.step === 'caption' && instagramStep === 'caption' && instagramDraft && index === turns.findLastIndex(({ instagram }) => instagram?.step === 'caption') && (
                      <form onSubmit={(event) => {
                        event.preventDefault()
                        const tab = window.open('about:blank', '_blank')
                        if (tab) tab.opener = null
                        const body = new FormData()
                        body.append('image', instagramDraft.image)
                        void sendInstagramForm('photo', body, tab)
                      }}>
                        <label className="voice-link" htmlFor="instagram-caption">Caption (type or use the mic)</label>
                        <textarea
                          id="instagram-caption"
                          rows="3"
                          maxLength={2200}
                          value={instagramDraft.caption}
                          onChange={(event) => setInstagramDraft({ ...instagramDraft, caption: event.target.value })}
                        />
                        <button className="voice-link" type="submit" disabled={busy || isRecording}>Connect Instagram</button>
                      </form>
                    )}
                    {turn.instagram?.step === 'review' && instagramStep === 'review' && instagramDraft && index === turns.findLastIndex(({ instagram }) => instagram?.step === 'review') && (
                      <form onSubmit={(event) => {
                        event.preventDefault()
                        const body = new FormData()
                        body.append('caption', instagramDraft.caption)
                        void sendInstagramForm('publish', body)
                      }}>
                        <p>{instagramDraft.caption || 'No caption'}</p>
                        <button className="voice-link" type="submit" disabled={instagramBusy}>Post to Instagram</button>
                      </form>
                    )}
                    {(turn.shopping?.actions ?? (turn.shopping?.action ? [turn.shopping.action] : [])).map((action) => (
                      <a className="voice-link" key={action.url} href={action.url} target="_blank" rel="noopener noreferrer">
                        {action.label} ↗
                      </a>
                    ))}
                    {shopping === turn.shopping && shopping && (
                      <div>
                        {shopping.choices.map((choice) => (
                          <button className="voice-link" type="button" key={choice} disabled={busy || isRecording} onClick={() => void answerShopping(choice)}>
                            {choice}
                          </button>
                        ))}
                        <button className="voice-link" type="button" disabled={busy || isRecording} onClick={() => void answerShopping('cancel')}>
                          End shopping
                        </button>
                      </div>
                    )}
                    {turn.playback && (
                      <a
                        className="voice-link"
                        href={turn.playback.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={() => {
                          if (isRecording || busy) return
                          const { language, platform } = turn.playback
                          replyPlayer.current?.pause()
                          setGuide({ step: 'opened', language, platform })
                          void advanceGuide('opened', language, platform)
                        }}
                      >
                        Open in {turn.playback.platform} ↗
                      </a>
                    )}
                  </div>
                )}
              </div>
            ))}
            <div ref={latestTurn} />
          </div>

          <div className="voice-controls">
            <button
              className={`voice-mic voice-mic-${voiceState}`}
              type="button"
              onClick={isRecording ? stopRecording : startRecording}
              disabled={busy}
              aria-label={isRecording ? 'Stop and send' : dictatingCaption ? 'Dictate Instagram caption' : guide ? 'Record yes or no' : 'Start recording'}
            >
              <span className="voice-mic-icon" aria-hidden="true" />
            </button>
            <p className="voice-state" role="status">{voiceLabel}</p>
            {isRecording && <span className="voice-hint">Tap again to send</span>}
            {replyAudio && (
              <audio
                key={replyVersion}
                ref={replyPlayer}
                controls
                autoPlay
                src={replyAudio}
                aria-label="ApnaSathi voice reply"
                onPlay={() => setIsSpeaking(true)}
                onPause={() => setIsSpeaking(false)}
                onEnded={() => setIsSpeaking(false)}
              />
            )}
          </div>
        </div>
        {message && <p className="recorder-message" role="status">{message}</p>}
        <div className="recordings-heading"><h2>Your recordings</h2><span>{recordings.length}</span></div>
        {recordings.length === 0 ? (
          <div className="empty-recordings">Your saved audio will appear here after your first recording.</div>
        ) : (
          <div className="recordings-list">
            {recordings.map((recording) => (
              <article className="saved-recording" key={recording.id}>
                <div className="saved-recording-top"><div><strong>Voice note</strong><span>{formatDate(recording.createdAt)}</span></div><div className="recording-actions"><a href={recording.audioUrl} download={`apnasathi-recording-${recording.id}.${fileExtension(recording.mimeType)}`}>Download</a><button onClick={() => removeRecording(recording.id)} type="button">Delete</button></div></div>
                <audio controls preload="metadata" src={recording.audioUrl}>Your browser does not support audio playback.</audio>
              </article>
            ))}
          </div>
        )}
        <p className="local-note">Stored locally in this browser on this device.</p>
      </section>
      <footer className="recorder-footer">© 2025 ApnaSathi <span>YOUR VOICE, YOUR SPACE</span></footer>
    </main>
  )
}
