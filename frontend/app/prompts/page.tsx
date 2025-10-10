'use client'

import { useQuery } from '@tanstack/react-query'
import { BotMessageSquare, ArrowLeft, FileText } from 'lucide-react'
import Link from 'next/link'
import { promptApi } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDistanceToNow } from 'date-fns'

interface Prompt {
  prompt_id: string
  prompt_name: string
  prompt_type: string
  updated_at: string
}

export default function PromptsPage() {
  const { data: prompts, isLoading } = useQuery<Prompt[]>({
    queryKey: ['prompts'],
    queryFn: () => promptApi.listPrompts(),
  })

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      {/* Header */}
      <header className="border-b bg-white/50 backdrop-blur-sm dark:bg-slate-900/50">
        <div className="container mx-auto max-w-6xl px-4 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-green-600 text-white">
                <BotMessageSquare className="h-6 w-6" />
              </div>
              <div>
                <h1 className="text-2xl font-bold">Prompt Management</h1>
                <p className="text-sm text-muted-foreground">
                  Manage the Gemini prompts used for analysis
                </p>
              </div>
            </div>
            <Link href="/">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Home
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto max-w-6xl px-4 py-8">
        <Card>
          <CardHeader>
            <CardTitle>Available Prompts</CardTitle>
            <CardDescription>
              Select a prompt to view and edit its content.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="text-center text-muted-foreground">Loading prompts...</div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {prompts?.map((prompt) => (
                  <Link href={`/prompts/${prompt.prompt_id}`} key={prompt.prompt_id}>
                    <Card className="hover:shadow-md transition-shadow">
                      <CardHeader>
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <CardTitle>{prompt.prompt_name}</CardTitle>
                            <CardDescription>Type: {prompt.prompt_type}</CardDescription>
                          </div>
                          <FileText className="h-6 w-6 text-muted-foreground" />
                        </div>
                      </CardHeader>
                      <CardContent>
                        <p className="text-xs text-muted-foreground">
                          Last updated:{' '}
                          {formatDistanceToNow(new Date(prompt.updated_at), { addSuffix: true })}
                        </p>
                      </CardContent>
                    </Card>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
