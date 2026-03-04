import { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Palette, Loader2, RotateCcw } from 'lucide-react'
import { toast } from 'sonner'
import { brandingApi } from '@/lib/api-client'
import { useBranding, BRANDING_QUERY_KEY, BRANDING_DEFAULTS } from '@/hooks/use-branding'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export default function BrandingPage() {
  const queryClient = useQueryClient()
  const { data: branding, isLoading } = useBranding()

  const [appTitle, setAppTitle] = useState('')
  const [subtitle, setSubtitle] = useState('')
  const [logoUrl, setLogoUrl] = useState('')
  const [logoError, setLogoError] = useState(false)

  // Sync form state when branding data loads
  useEffect(() => {
    if (branding) {
      setAppTitle(branding.app_title)
      setSubtitle(branding.subtitle)
      setLogoUrl(branding.logo_url)
    }
  }, [branding])

  const hasChanges =
    branding &&
    (appTitle !== branding.app_title ||
      subtitle !== branding.subtitle ||
      logoUrl !== branding.logo_url)

  const isDefaults =
    appTitle === BRANDING_DEFAULTS.app_title &&
    subtitle === BRANDING_DEFAULTS.subtitle &&
    logoUrl === BRANDING_DEFAULTS.logo_url

  const updateMutation = useMutation({
    mutationFn: (data: { app_title?: string; subtitle?: string; logo_url?: string }) =>
      brandingApi.updateBranding(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: BRANDING_QUERY_KEY })
      toast.success('Branding updated')
    },
    onError: () => {
      toast.error('Failed to update branding')
    },
  })

  const handleSave = () => {
    if (!appTitle.trim()) {
      toast.error('App title cannot be empty')
      return
    }
    updateMutation.mutate({
      app_title: appTitle,
      subtitle: subtitle,
      logo_url: logoUrl,
    })
  }

  const handleReset = () => {
    setAppTitle(BRANDING_DEFAULTS.app_title)
    setSubtitle(BRANDING_DEFAULTS.subtitle)
    setLogoUrl(BRANDING_DEFAULTS.logo_url)
    setLogoError(false)
    updateMutation.mutate({
      app_title: BRANDING_DEFAULTS.app_title,
      subtitle: BRANDING_DEFAULTS.subtitle,
      logo_url: BRANDING_DEFAULTS.logo_url,
    })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="container mx-auto p-6 max-w-5xl">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <Palette className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold font-heading">Branding</h1>
            <p className="text-sm text-muted-foreground">
              Customize the app title, subtitle, and logo
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <Card>
          <CardHeader>
            <CardTitle>Settings</CardTitle>
            <CardDescription>
              Changes are reflected across the entire app
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="app-title">App Title</Label>
              <Input
                id="app-title"
                value={appTitle}
                onChange={(e) => setAppTitle(e.target.value)}
                placeholder="Superover"
                maxLength={100}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="subtitle">Subtitle</Label>
              <Input
                id="subtitle"
                value={subtitle}
                onChange={(e) => setSubtitle(e.target.value)}
                placeholder="Video Analysis Platform"
                maxLength={200}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="logo-url">Logo URL</Label>
              <Input
                id="logo-url"
                value={logoUrl}
                onChange={(e) => {
                  setLogoUrl(e.target.value)
                  setLogoError(false)
                }}
                placeholder="https://example.com/logo.svg"
                maxLength={2000}
              />
              {logoUrl && !logoError && (
                <div className="mt-2 flex items-center gap-2 rounded-md border p-2">
                  <img
                    src={logoUrl}
                    alt="Logo preview"
                    className="h-8 w-8 object-contain"
                    onError={() => setLogoError(true)}
                  />
                  <span className="text-xs text-muted-foreground">Logo preview</span>
                </div>
              )}
              {logoError && (
                <p className="text-xs text-destructive">
                  Could not load image. The default logo will be used.
                </p>
              )}
            </div>

            <div className="flex gap-2 pt-2">
              <Button
                onClick={handleSave}
                disabled={!hasChanges || updateMutation.isPending}
              >
                {updateMutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Save Changes
              </Button>
              <Button
                variant="outline"
                onClick={handleReset}
                disabled={isDefaults || updateMutation.isPending}
              >
                <RotateCcw className="mr-2 h-4 w-4" />
                Reset to Defaults
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Live Preview */}
        <Card>
          <CardHeader>
            <CardTitle>Live Preview</CardTitle>
            <CardDescription>
              How the sidebar will look with your changes
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* Mini sidebar header preview */}
            <div className="rounded-lg border bg-card p-4 space-y-4">
              <div className="flex items-center gap-2 border-b pb-3">
                {logoUrl && !logoError ? (
                  <img
                    src={logoUrl}
                    alt="Logo"
                    className="h-7 w-7 object-contain"
                    onError={() => setLogoError(true)}
                  />
                ) : (
                  <GoogleLogoPreview />
                )}
                <span className="text-lg font-bold font-heading">
                  {appTitle || 'Superover'}
                </span>
              </div>

              {/* Mini footer preview */}
              <div className="border-t pt-3">
                <p className="text-xs font-medium font-heading">
                  {appTitle || 'Superover'}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {subtitle || 'Video Analysis Platform'}
                </p>
              </div>

              {/* Browser tab preview */}
              <div className="border-t pt-3">
                <p className="text-xs text-muted-foreground mb-1">Browser tab title:</p>
                <div className="flex items-center gap-2 rounded bg-muted px-3 py-1.5">
                  <div className="h-3 w-3 rounded-full bg-muted-foreground/30" />
                  <span className="text-xs font-medium truncate">
                    {appTitle || 'Superover'} - {subtitle || 'Video Analysis Platform'}
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function GoogleLogoPreview() {
  return (
    <svg className="h-7 w-7" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18A10.96 10.96 0 0 0 1 12c0 1.77.42 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  )
}
