import { useCallback, useEffect, useState } from 'react'
import ChatWorkspace from './ChatWorkspace.jsx'

const languages = [
  { name: 'English', native: 'English', region: 'Available now', mark: 'EN' },
  { name: 'Hindi', native: 'हिन्दी', region: 'अब उपलब्ध', mark: 'हि' },
]

function Brand({ light = false }) {
  return (
    <a className={`brand ${light ? 'brand-light' : ''}`} href="#home" aria-label="ApnaSathi home">
      <span className="brand-mark">a</span>
      <span>apnasathi<span className="brand-dot">.</span></span>
    </a>
  )
}

function ArrowIcon() {
  return <svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M4 10h12m-5-5 5 5-5 5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>
}

function LanguageStep({ selected, onSelect, onContinue }) {
  return (
    <>
      <div className="step-note"><span className="step-number">01</span><span>FIRST, THE LITTLE THINGS</span></div>
      <h2 className="form-title">What language<br />feels like <em>home?</em></h2>
      <p className="form-description">We’ll make sure every hello feels familiar.</p>
      <div className="language-list" role="radiogroup" aria-label="Choose your language">
        {languages.map((language) => (
          <button
            key={language.name}
            className={`language-option ${selected === language.name ? 'language-selected' : ''}`}
            onClick={() => onSelect(language.name)}
            role="radio"
            aria-checked={selected === language.name}
            type="button"
          >
            <span className="language-mark">{language.mark}</span>
            <span className="language-copy"><span className="language-name">{language.native}</span><span className="language-region">{language.name}</span></span>
            <span className="radio-dot" />
          </button>
        ))}
      </div>
      <button className="primary-button" onClick={onContinue} type="button">Continue <ArrowIcon /></button>
      <p className="fine-print">You can always change this later.</p>
    </>
  )
}

function LoginStep({ selected, onBack, onSignIn }) {
  const [notice, setNotice] = useState('')
  const googleButton = useRef(null)

  useEffect(() => {
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
    if (!clientId) {
      setNotice('Google sign-in is not configured yet. Add VITE_GOOGLE_CLIENT_ID to the frontend environment.')
      return undefined
    }
    let cancelled = false
    const render = () => {
      if (cancelled || !window.google?.accounts?.id || !googleButton.current) return
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: (response) => {
          if (response.credential) onSignIn(response.credential)
          else setNotice('Google sign-in did not return an ID token. Please try again.')
        },
      })
      window.google.accounts.id.renderButton(googleButton.current, { theme: 'outline', size: 'large', shape: 'rect', width: 320, text: 'continue_with' })
    }
    if (window.google?.accounts?.id) render()
    else {
      const script = document.createElement('script')
      script.src = 'https://accounts.google.com/gsi/client'
      script.async = true
      script.defer = true
      script.onload = render
      script.onerror = () => setNotice('Google sign-in could not load. Check your connection and try again.')
      document.head.appendChild(script)
    }
    return () => { cancelled = true }
  }, [onSignIn])

  return (
    <>
      <button className="back-button" onClick={onBack} type="button"><span>←</span> Back to languages</button>
      <div className="step-note"><span className="step-number">02</span><span>MAKE YOURSELF AT HOME</span></div>
      <h2 className="form-title">Your people<br />are <em>right here.</em></h2>
      <p className="form-description">Sign in securely to keep your conversations and personal guidance together.</p>
      <div className="google-signin-wrap"><div ref={googleButton} /></div>
      {notice && <p className="form-notice" role="status">{notice}</p>}
      <div className="chosen-language"><span>YOUR LANGUAGE</span><strong>{languages.find((language) => language.name === selected)?.native ?? 'English'}</strong></div>
    </>
  )
}

function App() {
  const [step, setStep] = useState('language')
  const [selectedLanguage, setSelectedLanguage] = useState(() => sessionStorage.getItem('apnasathiLanguage') || 'English')
  const [googleToken, setGoogleToken] = useState(() => sessionStorage.getItem('apnasathiGoogleToken') || '')
  const [page, setPage] = useState(() => (
    window.location.pathname === '/record' && Boolean(sessionStorage.getItem('apnasathiGoogleToken'))
      ? 'recorder'
      : 'welcome'
  ))

  useEffect(() => {
    function handleHistoryChange() {
      const signedIn = Boolean(sessionStorage.getItem('apnasathiGoogleToken'))
      setPage(window.location.pathname === '/record' && signedIn ? 'recorder' : 'welcome')
      if (signedIn) setGoogleToken(sessionStorage.getItem('apnasathiGoogleToken') || '')
    }

    window.addEventListener('popstate', handleHistoryChange)
    return () => window.removeEventListener('popstate', handleHistoryChange)
  }, [])

  function navigate(nextPage) {
    const path = nextPage === 'recorder' ? '/record' : '/'
    window.history.pushState({}, '', path)
    setPage(nextPage)
  }

  const signIn = useCallback(async (credential) => {
    try {
      const base = import.meta.env.VITE_API_BASE_URL || '/api/v1'
      const response = await fetch(`${base}/auth/google`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id_token: credential }) })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data?.detail || 'Google sign-in failed. Please try again.')
      const language = selectedLanguage === 'Hindi' ? 'hi' : 'en'
      const profile = await fetch(`${base}/users/me/profile`, { method: 'PATCH', headers: { Authorization: `Bearer ${credential}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ preferred_language: language }) })
      if (!profile.ok) throw new Error('Signed in, but we could not save your language preference.')
      sessionStorage.setItem('apnasathiGoogleToken', credential)
      sessionStorage.setItem('apnasathiLanguage', selectedLanguage)
      setGoogleToken(credential)
      navigate('recorder')
    } catch (error) { window.alert(error.message) }
  }, [selectedLanguage])

  function signOut() {
    localStorage.removeItem('apnasathiSignedIn')
    sessionStorage.removeItem('apnasathiGoogleToken')
    sessionStorage.removeItem('apnasathiLanguage')
    setGoogleToken('')
    setStep('login')
    navigate('welcome')
  }

  if (page === 'recorder') {
    return <ChatWorkspace onSignOut={signOut} token={googleToken} language={selectedLanguage === 'Hindi' ? 'hi' : 'en'} />
  }

  return (
    <main className="page-shell" id="home">
      <section className="welcome-panel">
        <div className="welcome-top"><Brand light /><span className="welcome-caption">A COMMUNITY THAT GETS YOU</span></div>
        <div className="welcome-content">
          <span className="eyebrow"><span className="eyebrow-dot" /> YOUR NEXT CHAPTER STARTS HERE</span>
          <h1>A little help.<br />A lot <em>closer.</em></h1>
          <p>Good people, familiar faces, and the kind of support that makes a new place feel like your own.</p>
          <div className="community-proof">
            <div className="avatar-stack" aria-hidden="true"><span>अ</span><span>R</span><span>வ</span><span>ন</span></div>
            <span>Finding their people, every day.</span>
          </div>
        </div>
        <div className="welcome-bottom"><span>MADE FOR EVERY KIND OF BEGINNING</span><span>01 — 02</span></div>
        <span className="decor decor-one" aria-hidden="true">✳</span><span className="decor decor-two" aria-hidden="true">✳</span>
      </section>

      <section className="form-panel" aria-label={step === 'language' ? 'Choose a language' : 'Sign in'}>
        <div className="form-top"><span className="mobile-brand"><Brand /></span><span className="already-here">{step === 'language' ? <>Already a member? <button type="button" onClick={() => setStep('login')}>Sign in</button></> : <>New to ApnaSathi? <button type="button" onClick={() => setStep('language')}>Get started</button></>}</span></div>
        <div className="form-content" key={step}>
          {step === 'language'
            ? <LanguageStep selected={selectedLanguage} onSelect={setSelectedLanguage} onContinue={() => setStep('login')} />
            : <LoginStep selected={selectedLanguage} onBack={() => setStep('language')} onSignIn={signIn} />}
        </div>
        <footer className="form-footer"><span>© 2025 ApnaSathi</span><div><a href="#privacy">Privacy</a><a href="#help">Need help?</a></div></footer>
      </section>
    </main>
  )
}

export default App
