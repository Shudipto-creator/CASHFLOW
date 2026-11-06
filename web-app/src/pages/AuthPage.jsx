import { useState } from 'react'
import { ArrowLeft, Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { useLanguage } from '../context/LanguageContext.jsx'
import { completePasswordRecovery, requestPasswordRecovery } from '../services/api.js'

export default function AuthPage() {
  const { signIn, signUp } = useAuth()
  const { t } = useLanguage()
  const [mode, setMode] = useState('login')
  const [recoveryStep, setRecoveryStep] = useState('request')
  const [challengeId, setChallengeId] = useState('')
  const [recoveryCode, setRecoveryCode] = useState('')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirmation, setPasswordConfirmation] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const creating = mode === 'register'
  const recovering = mode === 'recovery'

  async function submit(event) {
    event.preventDefault()
    setBusy(true); setError(''); setNotice('')
    try {
      if (recovering && recoveryStep === 'request') {
        const result = await requestPasswordRecovery(email)
        setChallengeId(result.challenge_id)
        setRecoveryStep('complete')
        setNotice(result.message)
      } else if (recovering) {
        if (password !== passwordConfirmation) throw new Error(t('Passwords do not match.'))
        const result = await completePasswordRecovery({
          email,
          challenge_id: challengeId,
          code: recoveryCode,
          new_password: password,
        })
        setMode('login')
        setPassword('')
        setPasswordConfirmation('')
        setRecoveryCode('')
        setChallengeId('')
        setNotice(result.message)
      } else if (creating) {
        await signUp({ email, password, name })
        setMode('login')
        setPassword('')
        setNotice(t('Account created. Sign in to continue.'))
      } else await signIn(email, password)
    } catch (err) {
      setError(err.message || t('Something went wrong. Please try again.'))
    } finally { setBusy(false) }
  }

  return <main className="auth-screen">
    <a className="auth-brand" href="#home"><span className="brand-mark">F</span><span>FINN</span></a>
    <section className="auth-content">
      <button className="auth-back" onClick={()=>{setMode('login');setError('');setNotice('')}}><ArrowLeft size={16}/><span>{t('Back')}</span></button>
      <p className="auth-eyebrow">{t('YOUR FINANCES, IN FOCUS')}</p>
      <h1>{t(recovering ? (recoveryStep === 'request' ? 'Recover your password' : 'Choose a new password') : creating ? 'Create your account' : 'Welcome back.')}</h1>
      <p className="auth-subtitle">{t(recovering ? (recoveryStep === 'request' ? 'Enter your email to receive a recovery code.' : 'Enter the code from the backend terminal and choose a new password.') : creating ? 'Set up your personal FINN account.' : 'Sign in to continue to FINN.')}</p>
      <form className="auth-form" onSubmit={submit}>
        {creating&&<label>{t('Your name')}<input autoComplete="name" required minLength={2} maxLength={100} value={name} onChange={e=>setName(e.target.value)} placeholder={t('Your name')}/></label>}
        <label>{t('Email')}<input type="email" autoComplete="email" required readOnly={recovering&&recoveryStep==='complete'} value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@email.com"/></label>
        {recovering&&recoveryStep==='complete'&&<label>{t('6-digit recovery code')}<input inputMode="numeric" autoComplete="one-time-code" required minLength={6} maxLength={6} pattern="[0-9]{6}" value={recoveryCode} onChange={e=>setRecoveryCode(e.target.value)} placeholder="000000"/></label>}
        {(!recovering||recoveryStep==='complete')&&<label>{t(recovering?'New password':'Password')}<span className="password-wrap"><input type={showPassword?'text':'password'} autoComplete={creating||recovering?'new-password':'current-password'} required minLength={creating||recovering?8:1} value={password} onChange={e=>setPassword(e.target.value)} placeholder={t(creating||recovering?'At least 8 characters':'Your password')}/><button type="button" aria-label={t(showPassword?'Hide password':'Show password')} onClick={()=>setShowPassword(!showPassword)}>{showPassword?<EyeOff size={17}/>:<Eye size={17}/>}</button></span>{(creating||recovering)&&<small>{t('Include uppercase and lowercase letters, and a number.')}</small>}</label>}
        {recovering&&recoveryStep==='complete'&&<label>{t('Confirm new password')}<input type="password" autoComplete="new-password" required minLength={8} value={passwordConfirmation} onChange={e=>setPasswordConfirmation(e.target.value)}/></label>}
        {error&&<p className="auth-error" role="alert">{error}</p>}{notice&&<p className="auth-success" role="status">{notice}</p>}
        <button className="auth-submit" type="submit" disabled={busy}>{t(busy?(recovering?'Processing…':creating?'Creating account…':'Signing in…'):recovering?(recoveryStep==='request'?'Send recovery code':'Update password'):creating?'Create account':'Sign in')}</button>
      </form>
      {mode==='login'&&<p className="auth-switch"><button onClick={()=>{setMode('recovery');setRecoveryStep('request');setError('');setNotice('')}}>{t('Forgot password?')}</button></p>}
      {recovering&&<p className="auth-switch"><button onClick={()=>{setMode('login');setRecoveryStep('request');setError('');setNotice('')}}>{t('Back to sign in')}</button></p>}
      {!recovering&&<p className="auth-switch">{t(creating?'Already have an account?':'New to FINN?')} <button onClick={()=>{setMode(creating?'login':'register');setError('');setNotice('')}}>{t(creating?'Sign in':'Create account')}</button></p>}
    </section>
    <p className="auth-footer">{t('FINN · FINANCIAL CLARITY, WITH YOU IN CONTROL')}</p>
  </main>
}
