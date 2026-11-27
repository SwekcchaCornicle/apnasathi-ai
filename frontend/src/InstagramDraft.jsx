import { useEffect, useState } from 'react'

export default function InstagramDraft({ request, onCancel }) {
  const [photo, setPhoto] = useState(null)
  const [preview, setPreview] = useState('')
  const [caption, setCaption] = useState('')
  const [authorizationUrl, setAuthorizationUrl] = useState('')
  const [step, setStep] = useState('image')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)

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
    const draft = await request('/instagram/photo', { method: 'POST', body, credentials: 'include' })
    setAuthorizationUrl(draft.action.url)
    setStep('authorization')
  }

  async function checkAuthorization() {
    const draft = await request('/instagram/status', { credentials: 'include' })
    if (draft.step !== 'caption') throw new Error(draft.step === 'failed' ? 'Instagram authorization failed.' : 'Complete Instagram authorization before continuing.')
    setStep('caption')
  }

  async function publish() {
    const body = new FormData()
    body.append('caption', caption)
    body.append('confirmed', 'true')
    const result = await request('/instagram/publish', { method: 'POST', body, credentials: 'include' })
    setNotice(result.response)
    setStep('published')
  }

  async function cancel() {
    if (authorizationUrl && step !== 'published') {
      await request('/instagram/draft', { method: 'DELETE', credentials: 'include' })
    }
    onCancel()
  }

  return (
    <section aria-label="Instagram draft" className="suggestion-row">
      {photo && preview && <img src={preview} alt="Instagram photo preview" width="128" />}
      {step === 'image' && <>
        <label>Choose a JPEG <input type="file" accept="image/jpeg" disabled={busy} onChange={(event) => setPhoto(event.target.files?.[0] || null)} /></label>
        <button type="button" disabled={busy || !photo} onClick={() => void run(attach)}>Attach photo</button>
      </>}
      {step === 'authorization' && <>
        <a className="voice-link" href={authorizationUrl} target="_blank" rel="noopener noreferrer">Connect Instagram</a>
        <button type="button" disabled={busy} onClick={() => void run(checkAuthorization)}>Check connection</button>
      </>}
      {step === 'caption' && <>
        <label>Caption <textarea value={caption} maxLength={2200} rows={3} onChange={(event) => setCaption(event.target.value)} /></label>
        <label>Dictate from an audio file <input type="file" accept="audio/*" disabled={busy} onChange={(event) => {
          const audio = event.target.files?.[0]
          if (!audio) return
          void run(async () => {
            const body = new FormData()
            body.append('audio', audio)
            const result = await request('/instagram/caption', { method: 'POST', body })
            setCaption(result.text.slice(0, 2200))
          })
        }} /></label>
        <button type="button" onClick={() => setStep('review')}>Review post</button>
      </>}
      {step === 'review' && <>
        <p>{caption || 'No caption'}</p>
        <button type="button" onClick={() => setStep('caption')} disabled={busy}>Edit caption</button>
        <button type="button" onClick={() => void run(publish)} disabled={busy}>Confirm and post to Instagram</button>
      </>}
      <button type="button" disabled={busy} onClick={() => void run(cancel)}>{step === 'published' ? 'Close draft' : 'Cancel draft'}</button>
      {notice && <p role="status">{notice}</p>}
    </section>
  )
}
