import { useCallback, useState } from 'react'
import { CognitoIdentityProviderClient, SignUpCommand, ConfirmSignUpCommand, ForgotPasswordCommand, ConfirmForgotPasswordCommand } from '@aws-sdk/client-cognito-identity-provider'
import { signInWithSrp } from './cognito.js'
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
  const [showLanguageNotice, setShowLanguageNotice] = useState(false)
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
      <button className="back-button" onClick={() => setShowLanguageNotice(true)} type="button">Looking for another language?</button>
      {showLanguageNotice && <p className="form-notice" role="status">We are about to launch support for this language.</p>}
    </>
  )
}

function LoginStep({ selected, onBack, onSignIn }) {
  const [mode, setMode] = useState('login')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const region = import.meta.env.VITE_COGNITO_REGION || 'ap-south-1'
  const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID
  const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID
  const cognito = new CognitoIdentityProviderClient({ region })
  const language = selected === 'Hindi' ? 'hi' : 'en'

  async function submit(event) {
    event.preventDefault()
    setNotice('')
    if (!clientId || !userPoolId) { setNotice('Cognito is not configured. Set VITE_COGNITO_CLIENT_ID in frontend/.env.local.'); return }
    setBusy(true)
    try {
      if (mode === 'signup') {
        const name = fullName.trim()
        if (!name) { setNotice('Enter your full name.'); return }
        const emailAddress = email.trim().toLowerCase()
        await cognito.send(new SignUpCommand({
          ClientId: clientId,
          Username: emailAddress,
          Password: password,
          UserAttributes: [
            { Name: 'email', Value: emailAddress },
            { Name: 'name', Value: name },
          ],
        }))
        setMode('confirm')
        setNotice('We sent a verification code to your email address.')
      } else if (mode === 'confirm') {
        await cognito.send(new ConfirmSignUpCommand({ ClientId: clientId, Username: email.trim().toLowerCase(), ConfirmationCode: code.trim() }))
        setMode('login')
        setNotice('Email verified. You can now sign in.')
      } else if (mode === 'login') {
        const idToken = await signInWithSrp({ userPoolId, clientId, email: email.trim().toLowerCase(), password })
        await onSignIn(idToken, language)
      } else if (mode === 'forgot') {
        await cognito.send(new ForgotPasswordCommand({ ClientId: clientId, Username: email.trim().toLowerCase() }))
        setMode('reset')
        setNotice('We sent a password reset code to your email.')
      } else if (mode === 'reset') {
        await cognito.send(new ConfirmForgotPasswordCommand({ ClientId: clientId, Username: email.trim().toLowerCase(), ConfirmationCode: code.trim(), Password: newPassword }))
        setMode('login')
        setNotice('Password reset successfully. Please sign in.')
      }
    } catch (error) {
      const messages = {
        UserNotFoundException: 'No account found for this email.',
        NotAuthorizedException: 'Incorrect email or password, or the account is not confirmed.',
        UsernameExistsException: 'An account already exists for this email. Please sign in.',
        CodeMismatchException: 'The verification code is incorrect.',
        ExpiredCodeException: 'The code has expired. Request a new one.',
        UserNotConfirmedException: 'Please verify your email before signing in.',
        InvalidPasswordException: 'Password does not meet the user pool policy.',
      }
      setNotice(messages[error.name] || error.message || 'Authentication failed. Please try again.')
    } finally { setBusy(false) }
  }

  const heading = ({ signup: 'Create your account', confirm: 'Verify your email', login: 'Welcome back', forgot: 'Reset your password', reset: 'Choose a new password' })[mode]
  return (
    <>
      <button className="back-button" onClick={onBack} type="button">← Back to languages</button>
      <div className="step-note"><span className="step-number">02</span><span>YOUR APNASATHI ACCOUNT</span></div>
      <h2 className="form-title">{heading}</h2>
      <p className="form-description">Sign in securely to keep your conversations and personal guidance together.</p>
      <form className="cognito-form" onSubmit={submit}>
        {mode === 'signup' && <>
          <label htmlFor="account-name">Full name</label>
          <input id="account-name" type="text" autoComplete="name" required value={fullName} onChange={(event) => setFullName(event.target.value)} />
        </>}
        <label htmlFor="account-email">Email address</label>
        <input id="account-email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" disabled={mode === 'confirm' || mode === 'reset'} />
        {['signup','login'].includes(mode) && <><label htmlFor="account-password">Password</label><input id="account-password" type="password" required minLength={8} autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="At least 8 characters" /></>}
        {['confirm','reset'].includes(mode) && <><label htmlFor="account-code">Email verification code</label><input id="account-code" required value={code} onChange={(event) => setCode(event.target.value)} placeholder="Enter code from email" /></>}
        {mode === 'reset' && <><label htmlFor="account-new-password">New password</label><input id="account-new-password" type="password" required minLength={8} autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></>}
        <button className="primary-button" type="submit" disabled={busy}>{busy ? 'Please wait…' : ({ signup: 'Create account', confirm: 'Verify email', login: 'Sign in', forgot: 'Send reset code', reset: 'Reset password' })[mode]}</button>
      </form>
      {notice && <p className="form-notice" role="status">{notice}</p>}
      <div className="cognito-links">
        {mode === 'login' && <><button type="button" onClick={() => setMode('signup')}>Create account</button><button type="button" onClick={() => setMode('forgot')}>Forgot password?</button></>}
        {mode === 'signup' && <button type="button" onClick={() => setMode('login')}>Already have an account? Sign in</button>}
        {mode === 'confirm' && <button type="button" onClick={() => setMode('signup')}>Back to sign up</button>}
        {mode === 'forgot' && <button type="button" onClick={() => setMode('login')}>Back to sign in</button>}
        {mode === 'reset' && <button type="button" onClick={() => setMode('forgot')}>Request another code</button>}
      </div>
      <div className="chosen-language"><span>YOUR LANGUAGE</span><strong>{selected}</strong></div>
    </>
  )
}

function App() {
  const [step, setStep] = useState('language')
  const [selectedLanguage, setSelectedLanguage] = useState(() => sessionStorage.getItem('apnasathiLanguage') || 'English')
  const [cognitoToken, setCognitoToken] = useState(() => sessionStorage.getItem('apnasathiCognitoToken') || '')
  const [page, setPage] = useState(() => window.location.pathname === '/record' && Boolean(sessionStorage.getItem('apnasathiCognitoToken')) ? 'recorder' : 'welcome')

  const signIn = useCallback(async (idToken, language) => {
    const base = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    const response = await fetch(`${base}/auth/cognito`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id_token: idToken }) })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(data?.detail || 'ApnaSathi account setup failed.')
    const profile = await fetch(`${base}/users/me/profile`, { method: 'PATCH', headers: { Authorization: `Bearer ${idToken}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ preferred_language: language }) })
    if (!profile.ok) throw new Error('Signed in, but we could not save your language preference.')
    sessionStorage.setItem('apnasathiCognitoToken', idToken)
    sessionStorage.setItem('apnasathiLanguage', language === 'hi' ? 'Hindi' : 'English')
    setCognitoToken(idToken)
    window.history.pushState({}, '', '/record')
    setPage('recorder')
  }, [])


  const signOut = useCallback(() => {
    sessionStorage.removeItem('apnasathiCognitoToken')
    setCognitoToken('')
    setStep('login')
    window.history.replaceState({}, '', '/')
    setPage('welcome')
  }, [])

  if (page === 'recorder') {
    return <ChatWorkspace onSignOut={signOut} token={cognitoToken} language={sessionStorage.getItem('apnasathiLanguage') === 'Hindi' ? 'hi' : 'en'} />
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
            ? <LanguageStep selected={selectedLanguage} onSelect={(language) => { sessionStorage.setItem('apnasathiLanguage', language); setSelectedLanguage(language) }} onContinue={() => setStep('login')} />
            : <LoginStep selected={selectedLanguage} onBack={() => setStep('language')} onSignIn={signIn} />}
        </div>
        <footer className="form-footer"><span>© 2025 ApnaSathi</span><div><a href="#privacy">Privacy</a><a href="#help">Need help?</a></div></footer>
      </section>
    </main>
  )
}

export default App
