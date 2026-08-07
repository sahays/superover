import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus, Trash2, ShieldCheck, ShieldOff, Copy, Star } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { authApi } from '@/lib/api-client'
import { useAuthStore } from '@/store/useAuthStore'
import { toast } from 'sonner'

interface InviteCode {
  id: string
  code: string
  label: string
  is_active: boolean
  is_admin: boolean
  owner: string
  expires_at: string | null
  created_at: string | null
}

function generateRandomCode(): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789'
  let result = ''
  for (let i = 0; i < 16; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return result
}

export default function InviteCodesPage() {
  const queryClient = useQueryClient()
  const { isMaster } = useAuthStore()
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [newCode, setNewCode] = useState('')
  const [newLabel, setNewLabel] = useState('')
  // Studio slug scoping this code's search visibility. Blank = sees everything
  // (operator/master-style). Set e.g. "sony"/"zee" for a competitor's code.
  const [newOwner, setNewOwner] = useState('')
  // Admin checkbox is master-only since admins can't reach the create
  // endpoint anyway. Default off — most invitees are regular users.
  const [newIsAdmin, setNewIsAdmin] = useState(false)

  const { data: codes = [], isLoading } = useQuery<InviteCode[]>({
    queryKey: ['invite-codes'],
    queryFn: authApi.listCodes,
  })

  const createMutation = useMutation({
    mutationFn: authApi.createCode,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invite-codes'] })
      setCreateOpen(false)
      setNewCode('')
      setNewLabel('')
      setNewOwner('')
      setNewIsAdmin(false)
      toast.success('Invite code created')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to create code')
    },
  })

  const revokeMutation = useMutation({
    mutationFn: authApi.revokeCode,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invite-codes'] })
      toast.success('Code revoked')
    },
  })

  const activateMutation = useMutation({
    mutationFn: authApi.activateCode,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invite-codes'] })
      toast.success('Code activated')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: authApi.deleteCode,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invite-codes'] })
      setDeleteId(null)
      toast.success('Code deleted')
    },
  })

  const handleCreate = () => {
    if (!newCode.trim()) return
    createMutation.mutate({
      code: newCode.trim(),
      label: newLabel.trim(),
      owner: newOwner.trim(),
      is_admin: newIsAdmin,
    })
  }

  const copyCode = (code: string) => {
    navigator.clipboard.writeText(code)
    toast.success('Code copied to clipboard')
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold font-heading">Invite Codes</h1>
          <p className="text-muted-foreground">Manage access codes for the platform</p>
        </div>
        {/* Create is master-only. Admins reach this page (revoke/activate/
            delete) but cannot mint new codes — so they cannot escalate
            privileges. */}
        {isMaster && (
          <Button onClick={() => { setNewCode(generateRandomCode()); setCreateOpen(true) }}>
            <Plus className="mr-2 h-4 w-4" />
            Create Code
          </Button>
        )}
      </div>

      <div className="space-y-3">
        {codes.length === 0 && (
          <p className="text-center text-muted-foreground py-8">No invite codes yet. Create one to get started.</p>
        )}
        {codes.map((code) => (
          <div
            key={code.id}
            className="flex items-center justify-between rounded-lg border p-4"
          >
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <code className="rounded bg-muted px-2 py-0.5 text-sm font-mono">{code.code}</code>
                <button onClick={() => copyCode(code.code)} className="text-muted-foreground hover:text-foreground">
                  <Copy className="h-3.5 w-3.5" />
                </button>
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                  code.is_active
                    ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                    : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                }`}>
                  {code.is_active ? 'Active' : 'Revoked'}
                </span>
                {code.is_admin && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                    <Star className="h-3 w-3" /> Admin
                  </span>
                )}
                {code.owner && (
                  <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                    {code.owner}
                  </span>
                )}
              </div>
              {code.label && <p className="text-sm text-muted-foreground">{code.label}</p>}
              {code.expires_at && (
                <p className="text-xs text-muted-foreground">
                  Expires: {new Date(code.expires_at).toLocaleDateString()}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {code.is_active ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => revokeMutation.mutate(code.id)}
                  disabled={revokeMutation.isPending}
                >
                  <ShieldOff className="mr-1 h-3.5 w-3.5" />
                  Revoke
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => activateMutation.mutate(code.id)}
                  disabled={activateMutation.isPending}
                >
                  <ShieldCheck className="mr-1 h-3.5 w-3.5" />
                  Activate
                </Button>
              )}
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setDeleteId(code.id)}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        ))}
      </div>

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Invite Code</DialogTitle>
            <DialogDescription>Create a new invite code for platform access.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="code">Code</Label>
              <div className="flex gap-2">
                <Input
                  id="code"
                  value={newCode}
                  onChange={(e) => setNewCode(e.target.value)}
                  placeholder="Enter or generate a code"
                  maxLength={32}
                  className="font-mono"
                />
                <Button variant="outline" onClick={() => setNewCode(generateRandomCode())}>
                  Random
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="label">Label (optional)</Label>
              <Input
                id="label"
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
                placeholder="e.g., Team member name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="owner">Studio / owner (optional)</Label>
              <Input
                id="owner"
                value={newOwner}
                onChange={(e) => setNewOwner(e.target.value)}
                placeholder="e.g., sony or zee"
              />
              <p className="text-xs text-muted-foreground">
                Scopes search to one studio's content (plus shared/untagged). Blank = sees everything.
              </p>
            </div>
            <div className="flex items-start justify-between rounded-lg border p-3">
              <div>
                <Label htmlFor="admin-toggle" className="text-sm">Admin</Label>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Grants master-level access except creating new codes.
                </p>
              </div>
              <Switch
                id="admin-toggle"
                checked={newIsAdmin}
                onCheckedChange={setNewIsAdmin}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate} disabled={createMutation.isPending || !newCode.trim()}>
              {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteId} onOpenChange={(open) => { if (!open) setDeleteId(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete invite code?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. Users with this code will lose access.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteId && deleteMutation.mutate(deleteId)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
