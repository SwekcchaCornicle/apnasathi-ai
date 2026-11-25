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
      if (mediaRecorder.current?.state === 'recording') mediaRecorder.current.stop()
      audioStream.current?.getTracks().forEach((track) => track.stop())
      objectUrls.current.forEach((audioUrl) => URL.revokeObjectURL(audioUrl))
    }
  }, [])

  async function startRecording() {
    setMessage('')

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

        try {
          const id = await saveRecording(audioBlob)
          const audioUrl = URL.createObjectURL(audioBlob)
          objectUrls.current.set(id, audioUrl)
          setRecordings((current) => [{ id, audio: audioBlob, createdAt: Date.now(), mimeType: audioBlob.type, audioUrl }, ...current])
        } catch {
          setMessage('The recording finished, but could not be saved in this browser.')
          return
        }

        try {
          const formData = new FormData()
          formData.append('audio', audioBlob, `recording-${Date.now()}.${fileExtension(audioBlob.type)}`)
          const response = await fetch(`${API_BASE_URL}/upload-audio`, {
            method: 'POST',
            body: formData,
          })

          if (!response.ok) {
            const result = await response.json().catch(() => ({}))
            throw new Error(result.detail || 'Audio upload failed')
          }

          setBackendStatus('connected')
          setMessage('Recording saved on this device and sent to the backend.')
        } catch (error) {
          setBackendStatus('offline')
          setMessage(`Saved on this device, but the backend upload failed: ${error.message}`)
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
        <span className="step-note"><span className="step-number">03</span><span>A MOMENT TO YOURSELF</span></span>
        <h1 className="recorder-title">A little space<br />to <em>be heard.</em></h1>
        <p className="recorder-intro">Record a voice note and keep it on this device. Your audio stays in this browser.</p>

        <div className="record-card">
          <div className="record-symbol" aria-hidden="true">{isRecording ? '●' : '♫'}</div>
          <div className="record-copy">
            <strong>{isRecording ? 'Recording in progress' : 'Ready when you are'}</strong>
            <span>{isRecording ? 'Speak naturally. You can stop whenever you like.' : 'Allow microphone access to start a voice recording.'}</span>
          </div>
          <button className={`record-button ${isRecording ? 'record-button-active' : ''}`} onClick={isRecording ? stopRecording : startRecording} type="button">
            {isRecording ? 'Stop recording' : 'Start recording'}
          </button>
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
