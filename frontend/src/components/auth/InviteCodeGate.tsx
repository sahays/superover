import { useState } from 'react'
import { KeyRound, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuthStore } from '@/store/useAuthStore'
import { authApi } from '@/lib/api-client'
import { toast } from 'sonner'

export function InviteCodeGate() {
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const login = useAuthStore((s) => s.login)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!code.trim()) return

    setLoading(true)
    setError('')

    try {
      const result = await authApi.validate(code.trim())
      if (result.valid) {
        login(code.trim(), result.is_master, result.is_admin)
        const greeting = result.is_master
          ? 'Welcome, master!'
          : result.is_admin
            ? 'Welcome, admin!'
            : 'Welcome!'
        toast.success(greeting)
      } else {
        setError('Invalid invite code')
      }
    } catch {
      setError('Failed to validate code. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <KeyRound className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-2xl font-heading">Super Over Alchemy</CardTitle>
          <CardDescription>Enter your invite code to continue</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              type="password"
              placeholder="Enter invite code"
              value={code}
              onChange={(e) => { setCode(e.target.value); setError('') }}
              autoFocus
              className={error ? 'border-red-500' : ''}
            />
            {error && <p className="text-sm text-red-500">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading || !code.trim()}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Continue
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
