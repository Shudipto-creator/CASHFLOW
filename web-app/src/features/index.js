import { Bot, Users, Home, Activity, UserRound, FileText, Repeat2 } from 'lucide-react'

// Add future scenarios here; the dashboard renders this list as feature cards.
export const personalTools = [
  { id: 'bills-analysis', title: 'Bills Analysis', description: 'Review bills, understand changes, and spot unusual charges.', icon: FileText },
  { id: 'subscriptions', title: 'Subscriptions & Direct Debit', description: 'See recurring payments and keep upcoming debits in view.', icon: Repeat2 },
]

export const navigation = [
  { id: 'home', label: 'Home', icon: Home },
  { id: 'contacts', label: 'Contact', icon: Users },
  { id: 'cfo-ai', label: 'FINN AI', icon: Bot },
  { id: 'activity', label: 'Activity', icon: Activity },
  { id: 'me', label: 'Me', icon: UserRound },
]


