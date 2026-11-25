import { useEffect, useState } from 'react'
import AudioRecorder from './AudioRecorder.jsx'

const languages = [
  { name: 'English', native: 'English', region: 'A little bit of everywhere', mark: 'EN' },
  { name: 'Hindi', native: 'हिन्दी', region: 'Across North India', mark: 'हि' },
  { name: 'Bengali', native: 'বাংলা', region: 'West Bengal & beyond', mark: 'বা' },
  { name: 'Tamil', native: 'தமிழ்', region: 'Tamil Nadu & beyond', mark: 'த' },
  { name: 'Telugu', native: 'తెలుగు', region: 'Andhra Pradesh & Telangana', mark: 'తె' },
  { name: 'Marathi', native: 'मराठी', region: 'Maharashtra & beyond', mark: 'म' },
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
  const [showPassword, setShowPassword] = useState(false)
  const [notice, setNotice] = useState('')

  function handleSubmit(event) {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    const email = formData.get('email')
    const password = formData.get('password')

    if (email === 'rohan@gmail.com' && password === '123456') {
      onSignIn()
      return
    }

    setNotice('That email and password do not match. Please try again.')
  }

  return (
    <>
      <button className="back-button" onClick={onBack} type="button"><span>←</span> Back to languages</button>
      <div className="step-note"><span className="step-number">02</span><span>MAKE YOURSELF AT HOME</span></div>
      <h2 className="form-title">Your people<br />are <em>right here.</em></h2>
      <p className="form-description">Sign in to find a little more connection, every day.</p>
      <form className="login-form" onSubmit={handleSubmit}>
        <label htmlFor="email">Email address</label>
        <input id="email" name="email" type="email" autoComplete="email" placeholder="you@example.com" required />
        <div className="password-label"><label htmlFor="password">Password</label><a href="#forgot" onClick={(event) => { event.preventDefault(); setNotice('Password reset will be available when sign-in is connected.') }}>Forgot password?</a></div>
        <div className="password-wrap"><input id="password" name="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" placeholder="Enter your password" required /><button type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} onClick={() => setShowPassword(!showPassword)}>{showPassword ? 'Hide' : 'Show'}</button></div>
        <button className="primary-button" type="submit">Sign in <ArrowIcon /></button>
        {notice && <p className="form-notice" role="status">{notice}</p>}
      </form>
      <div className="signup-line">New around here? <a href="#signup" onClick={(event) => { event.preventDefault(); setNotice('Account creation will be available soon.') }}>Create an account <span>↗</span></a></div>
      <div className="chosen-language"><span>YOUR LANGUAGE</span><strong>{languages.find((language) => language.name === selected)?.native ?? 'English'}</strong></div>
    </>
  )
}

function App() {
  const [step, setStep] = useState('language')
  const [selectedLanguage, setSelectedLanguage] = useState('English')
  const [page, setPage] = useState(() => (
    window.location.pathname === '/record' && localStorage.getItem('apnasathiSignedIn') === 'true'
      ? 'recorder'
      : 'welcome'
  ))

  useEffect(() => {
    function handleHistoryChange() {
      const signedIn = localStorage.getItem('apnasathiSignedIn') === 'true'
      setPage(window.location.pathname === '/record' && signedIn ? 'recorder' : 'welcome')
    }

    window.addEventListener('popstate', handleHistoryChange)
    return () => window.removeEventListener('popstate', handleHistoryChange)
  }, [])

  function navigate(nextPage) {
    const path = nextPage === 'recorder' ? '/record' : '/'
    window.history.pushState({}, '', path)
    setPage(nextPage)
  }

  function signIn() {
    localStorage.setItem('apnasathiSignedIn', 'true')
    navigate('recorder')
  }

  function signOut() {
    localStorage.removeItem('apnasathiSignedIn')
    setStep('login')
    navigate('welcome')
  }

  if (page === 'recorder') {
    return <AudioRecorder onSignOut={signOut} />
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
