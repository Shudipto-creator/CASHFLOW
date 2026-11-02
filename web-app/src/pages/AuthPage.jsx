import { useState } from 'react'
import { ArrowLeft, Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'

export default function AuthPage() {
  const { signIn, signUp } = useAuth()
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const creating = mode === 'register'

  async function submit(event) {
    event.preventDefault()
    setBusy(true); setError(''); setNotice('')
    try {
      if (creating) {
        await signUp({ email, password, name })
        setMode('login')
        setPassword('')
        setNotice('Account created. Sign in to continue.')
      } else await signIn(email, password)
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.')
    } finally { setBusy(false) }
  }

  return <main className="auth-screen">
    <a className="auth-brand" href="#home"><span className="brand-mark">F</span><span>FINN</span></a>
    <section className="auth-content">
      <button className="auth-back" onClick={()=>{setMode('login');setError('');setNotice('')}}><ArrowLeft size={16}/><span>Back</span></button>
      <p className="auth-eyebrow">YOUR FINANCES, IN FOCUS</p>
      <h1>{creating ? 'Create your account' : 'Welcome back.'}</h1>
      <p className="auth-subtitle">{creating ? 'Set up your personal FINN account.' : 'Sign in to continue to FINN.'}</p>
      <form className="auth-form" onSubmit={submit}>
        {creating&&<label>Your name<input autoComplete="name" required minLength={2} maxLength={100} value={name} onChange={e=>setName(e.target.value)} placeholder="Your name"/></label>}
        <label>Email<input type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@email.com"/></label>
        <label>Password<span className="password-wrap"><input type={showPassword?'text':'password'} autoComplete={creating?'new-password':'current-password'} required minLength={creating?8:1} value={password} onChange={e=>setPassword(e.target.value)} placeholder={creating?'At least 8 characters':'Your password'}/><button type="button" aria-label={showPassword?'Hide password':'Show password'} onClick={()=>setShowPassword(!showPassword)}>{showPassword?<EyeOff size={17}/>:<Eye size={17}/>}</button></span>{creating&&<small>Include uppercase and lowercase letters, and a number.</small>}</label>
        {error&&<p className="auth-error" role="alert">{error}</p>}{notice&&<p className="auth-success" role="status">{notice}</p>}
        <button className="auth-submit" type="submit" disabled={busy}>{busy?(creating?'Creating account…':'Signing in…'):(creating?'Create account':'Sign in')}</button>
      </form>
      <p className="auth-switch">{creating?'Already have an account?':'New to FINN?'} <button onClick={()=>{setMode(creating?'login':'register');setError('');setNotice('')}}>{creating?'Sign in':'Create account'}</button></p>
    </section>
    <p className="auth-footer">FINN · FINANCIAL CLARITY, WITH YOU IN CONTROL</p>
  </main>
}
