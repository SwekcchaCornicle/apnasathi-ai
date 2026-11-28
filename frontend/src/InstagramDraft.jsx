import { useEffect, useRef, useState } from 'react'

export default function InstagramDraft({ request, onCancel }) {
  const [photo, setPhoto] = useState(null)
  const [preview, setPreview] = useState('')
  const [caption, setCaption] = useState('')
  const [authorizationUrl, setAuthorizationUrl] = useState('')
  const [step, setStep] = useState('image')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [recording, setRecording] = useState(false)
  const recorderRef = useRef(null)
  const mounted = useRef(false)
  const authorizationTab = useRef(null)
  const authorizationStarted = useRef(false)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      const recorder = recorderRef.current
      if (recorder) {
        recorder.onstop = null
        recorder.stream.getTracks().forEach((track) => track.stop())
      }
    }
  }, [])

  async function transcribe(audio) {
    if (!audio.size) throw new Error('No audio was recorded. Try again.')
    const body = new FormData()
    body.append('audio', audio, audio.name || 'caption-recording')
    const result = await request('/instagram/caption', { method: 'POST', body })
    if (mounted.current) setCaption(result.text.slice(0, 2200))
  }

  async function recordCaption() {
    if (recording) {
      if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
      return
    }
    let stream
    try {
      setBusy(true)
      setNotice('')
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
        throw new Error('Microphone recording is unavailable. You can upload an audio file instead.')
      }
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!mounted.current) {
        stream.getTracks().forEach((track) => track.stop())
        return
      }
      const mimeType = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4']
        .find((type) => MediaRecorder.isTypeSupported(type))
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
      const chunks = []
      recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data) }
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop())
        recorderRef.current = null
        setRecording(false)
        void run(() => transcribe(new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })))
      }
      recorder.onerror = () => {
        recorder.onstop = null
        stream.getTracks().forEach((track) => track.stop())
        recorderRef.current = null
        setRecording(false)
        setNotice('Recording failed. Try again or upload an audio file.')
      }
      recorderRef.current = recorder
      recorder.start()
      setRecording(true)
    } catch (error) {
      stream?.getTracks().forEach((track) => track.stop())
      setNotice(error.message)
    } finally {
      setBusy(false)
    }
  }

  function connect(event) {
    authorizationStarted.current = true
    const tab = window.open('about:blank', '_blank')
    if (!tab) return
    event.preventDefault()
    tab.opener = null
    authorizationTab.current = tab
    tab.location.replace(authorizationUrl)
    setNotice('')
  }

  useEffect(() => {
    if (!photo) return
    const url = URL.createObjectURL(photo)
    setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [photo])

  async function run(operation) {
    setBusy(true)
    setNotice('')
    try { await operation() }
    catch (error) { setNotice(error.message) }
    finally { setBusy(false) }
  }

  async function attach() {
    const body = new FormData()
    body.append('image', photo)
    body.append('caption', caption)
    body.append('confirmed', 'true')
    const draft = await request('/instagram/photo', { method: 'POST', body, credentials: 'include' })
    authorizationTab.current = null
    authorizationStarted.current = false
    setAuthorizationUrl(draft.action.url)
    setStep('authorization')
  }

  useEffect(() => {
    if (step !== 'authorization') return
    let active = true
    let timer
    let checking = false
    async function check() {
      if (!active || checking) return
      checking = true
      try {
        const draft = await request('/instagram/status', { credentials: 'include' })
        if (!active) return
        if (['published', 'failed', 'uncertain', 'not_authorized'].includes(draft.step)) {
          setStep(draft.step)
          setNotice(draft.response)
          return
        }
        if (draft.step === 'publishing') setNotice('Instagram is processing your post.')
        if (draft.step === 'authorization' && authorizationTab.current?.closed) {
          authorizationTab.current = null
          setNotice('Instagram not authorized. If Meta says “App not active,” use an approved test account or contact the Meta app admin.')
        }
      } catch (error) {
        if (!active) return
        setNotice(error.message)
        if ([401, 404].includes(error.status)) {
          setStep('not_authorized')
          setNotice('Instagram not authorized. This attempt expired or is unavailable. Review the photo to retry.')
          return
        }
      }
      checking = false
      if (active) timer = window.setTimeout(check, 2500)
    }
    function onReturn() {
      if (!authorizationStarted.current) return
      setNotice('Instagram not authorized yet. If Meta blocked the sign-in, choose “I couldn’t authorize.”')
      window.clearTimeout(timer)
      timer = window.setTimeout(check, 0)
    }
    window.addEventListener('focus', onReturn)
    timer = window.setTimeout(check, 2500)
    return () => {
      window.removeEventListener('focus', onReturn)
      active = false
      window.clearTimeout(timer)
    }
  }, [request, step])

  async function cancel() {
    if (step === 'authorization') {
      await request('/instagram/draft', { method: 'DELETE', credentials: 'include' })
    }
    onCancel()
  }

  return (
    <section aria-label="Instagram draft" className="suggestion-row">
      {photo && preview && <img src={preview} alt="Instagram photo preview" width="128" />}
      {step === 'image' && <>
        <label>Choose a JPEG <input type="file" accept="image/jpeg" disabled={busy} onChange={(event) => setPhoto(event.target.files?.[0] || null)} /></label>
        <button type="button" disabled={busy || !photo} onClick={() => setStep('caption')}>Attach photo</button>
      </>}
      {step === 'authorization' && <>
        <a className="voice-link" onClick={connect} href={authorizationUrl} target="_blank" rel="noopener noreferrer">Connect Instagram</a>
        <button type="button" onClick={() => setNotice('Instagram not authorized. If Meta says “App not active,” use an approved test account or contact the Meta app admin.')}>I couldn’t authorize</button>
        <p>Authorize the account you want to use. Your confirmed photo will be posted after authorization.</p>
      </>}
      {step === 'caption' && <>
        <label>Caption <textarea value={caption} maxLength={2200} rows={3} onChange={(event) => setCaption(event.target.value)} /></label>
        <button type="button" disabled={busy} onClick={() => void recordCaption()}>{recording ? 'Stop and transcribe' : 'Record caption'}</button>
        <label>Dictate from an audio file <input type="file" accept="audio/*" disabled={busy || recording} onChange={(event) => {
          const audio = event.target.files?.[0]
          if (!audio) return
          void run(() => transcribe(audio))
        }} /></label>
        <button type="button" disabled={busy || recording} onClick={() => setStep('review')}>Review post</button>
      </>}
      {step === 'review' && <>
        <p>{caption || 'No caption'}</p>
        <button type="button" onClick={() => setStep('caption')} disabled={busy}>Edit caption</button>
        <button type="button" onClick={() => void run(attach)} disabled={busy}>Confirm photo and caption</button>
      </>}
      {step === 'not_authorized' && <button type="button" onClick={() => setStep('review')}>Review and retry</button>}
      <button type="button" disabled={busy || recording} onClick={() => void run(cancel)}>{['published', 'failed', 'uncertain', 'not_authorized'].includes(step) ? 'Close draft' : 'Cancel draft'}</button>
      {notice && <p role="status">{notice}</p>}
    </section>
  )
}
