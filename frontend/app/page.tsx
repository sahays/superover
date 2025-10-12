'use client'

import { Video as VideoIcon, Film, Sparkles, ArrowRight, BotMessageSquare } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export default function HomePage() {
  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      <div className="text-center mb-12">
        <h2 className="text-4xl font-bold mb-4">Choose Your Workflow</h2>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
          Select the video processing workflow that fits your needs
        </p>
      </div>

      <div className="grid gap-8 md:grid-cols-2 max-w-5xl mx-auto">
        {/* Scene Analysis Workflow */}
        <Card className="relative overflow-hidden transition hover:shadow-lg">
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-purple-500/20 to-transparent rounded-bl-full" />
          <CardHeader>
            <div className="flex items-center gap-3 mb-2">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-purple-100 text-purple-600 dark:bg-purple-900 dark:text-purple-300">
                <Sparkles className="h-6 w-6" />
              </div>
              <CardTitle className="text-2xl">Scene Analysis</CardTitle>
            </div>
            <CardDescription className="text-base">
              AI-powered scene analysis with Gemini
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul className="space-y-3 text-sm text-muted-foreground">
              <li className="flex items-start gap-2">
                <ArrowRight className="h-4 w-4 mt-0.5 text-purple-600 flex-shrink-0" />
                <span>Upload videos for intelligent scene analysis</span>
              </li>
              <li className="flex items-start gap-2">
                <ArrowRight className="h-4 w-4 mt-0.5 text-purple-600 flex-shrink-0" />
                <span>Automatic video chunking and processing</span>
              </li>
              <li className="flex items-start gap-2">
                <ArrowRight className="h-4 w-4 mt-0.5 text-purple-600 flex-shrink-0" />
                <span>Gemini AI analyzes each scene for content</span>
              </li>
              <li className="flex items-start gap-2">
                <ArrowRight className="h-4 w-4 mt-0.5 text-purple-600 flex-shrink-0" />
                <span>Get structured scene analysis results</span>
              </li>
            </ul>
            <Link href="/scene-analysis" className="block">
              <Button className="w-full mt-4" size="lg">
                Start Scene Analysis
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>

        {/* Media Processing Workflow */}
        <Card className="relative overflow-hidden transition hover:shadow-lg">
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-blue-500/20 to-transparent rounded-bl-full" />
          <CardHeader>
            <div className="flex items-center gap-3 mb-2">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-300">
                <Film className="h-6 w-6" />
              </div>
              <CardTitle className="text-2xl">Media Processing</CardTitle>
            </div>
            <CardDescription className="text-base">
              Professional video compression and audio extraction
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul className="space-y-3 text-sm text-muted-foreground">
              <li className="flex items-start gap-2">
                <ArrowRight className="h-4 w-4 mt-0.5 text-blue-600 flex-shrink-0" />
                <span>Extract comprehensive video metadata</span>
              </li>
              <li className="flex items-start gap-2">
                <ArrowRight className="h-4 w-4 mt-0.5 text-blue-600 flex-shrink-0" />
                <span>Compress videos to multiple resolutions (480p, 720p, 1080p)</span>
              </li>
              <li className="flex items-start gap-2">
                <ArrowRight className="h-4 w-4 mt-0.5 text-blue-600 flex-shrink-0" />
                <span>Extract audio in MP3, AAC, or WAV format</span>
              </li>
              <li className="flex items-start gap-2">
                <ArrowRight className="h-4 w-4 mt-0.5 text-blue-600 flex-shrink-0" />
                <span>Track processing jobs with real-time progress</span>
              </li>
            </ul>
            <Link href="/media" className="block">
              <Button className="w-full mt-4" size="lg" variant="outline">
                Start Media Processing
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* Prompt Management Card */}
      <div className="max-w-5xl mx-auto mt-8">
        <Card className="relative overflow-hidden transition hover:shadow-lg">
          <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-green-500/20 to-transparent rounded-bl-full" />
          <CardHeader>
            <div className="flex items-center gap-3 mb-2">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-300">
                <BotMessageSquare className="h-6 w-6" />
              </div>
              <CardTitle className="text-2xl">Prompt Management</CardTitle>
            </div>
            <CardDescription className="text-base">
              Configure the prompts used by the Gemini AI models
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">
              Centrally manage the prompts for different analysis types to ensure consistency and allow for easy experimentation and tuning.
            </p>
            <Link href="/prompts" className="block">
              <Button className="w-full mt-4" size="lg" variant="outline">
                Manage Prompts
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>


    </div>
  )
}
