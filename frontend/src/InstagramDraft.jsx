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
    body.append('caption', caption)
    body.append('confirmed', 'true')
    const draft = await request('/instagram/photo', { method: 'POST', body, credentials: 'include' })
    setAuthorizationUrl(draft.action.url)
    setStep('authorization')
  }

  useEffect(() => {
    if (step !== 'authorization') return
    let active = true
    let timer
    async function check() {
      try {
        const draft = await request('/instagram/status', { credentials: 'include' })
        if (!active) return
        if (['published', 'failed', 'uncertain'].includes(draft.step)) {
          setStep(draft.step)
          setNotice(draft.response)
          return
        }
        if (draft.step === 'publishing') setNotice('Instagram is processing your post.')
      } catch (error) {
        if (!active) return
        setNotice(error.message)
        if ([401, 404].includes(error.status)) {
          setStep('failed')
          return
        }
      }
      if (active) timer = window.setTimeout(check, 2500)
    }
    timer = window.setTimeout(check, 2500)
    return () => {
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
        <a className="voice-link" href={authorizationUrl} target="_blank" rel="noopener noreferrer">Connect Instagram</a>
        <p>Authorize the account you want to use. Your confirmed photo will be posted after authorization.</p>
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
        <button type="button" onClick={() => void run(attach)} disabled={busy}>Confirm photo and caption</button>
      </>}
      <button type="button" disabled={busy} onClick={() => void run(cancel)}>{['published', 'failed', 'uncertain'].includes(step) ? 'Close draft' : 'Cancel draft'}</button>
      {notice && <p role="status">{notice}</p>}
    </section>
  )
}
