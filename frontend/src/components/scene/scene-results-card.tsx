import { Download, FileJson, FileSpreadsheet } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Accordion } from '@/components/ui/accordion'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { ResultChunkItem } from './result-chunk-item'

interface SceneResultsCardProps {
  results: any[]
  isSubtitleJob: boolean
  downloadAsJSON: () => void
  downloadAsCSV: () => void
  downloadAsSRT: () => void
}

export function SceneResultsCard({
  results,
  isSubtitleJob,
  downloadAsJSON,
  downloadAsCSV,
  downloadAsSRT,
}: SceneResultsCardProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>{isSubtitleJob ? 'Subtitles' : 'Scene Analysis'}</CardTitle>
            <CardDescription>
              {results.length} chunk(s) analyzed
              {isSubtitleJob && results.length > 0 && (
                <span className="ml-2">
                  • {results.reduce((sum: number, r: any) =>
                    sum + (r.result_data?.subtitle_text?.length || 0), 0).toLocaleString()} characters
                </span>
              )}
            </CardDescription>
          </div>
          {isSubtitleJob ? (
            <Button variant="outline" size="sm" onClick={downloadAsSRT}>
              <Download className="mr-2 h-4 w-4" />
              Download SRT
            </Button>
          ) : (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm">
                  <Download className="mr-2 h-4 w-4" />
                  Download All
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={downloadAsJSON}>
                  <FileJson className="mr-2 h-4 w-4" />
                  Download as JSON
                </DropdownMenuItem>
                <DropdownMenuItem onClick={downloadAsCSV}>
                  <FileSpreadsheet className="mr-2 h-4 w-4" />
                  Download as CSV
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <Accordion type="single" collapsible className="w-full">
          {results.map((result: any, idx: number) => (
            <ResultChunkItem key={result.result_id} result={result} index={idx} />
          ))}
        </Accordion>
      </CardContent>
    </Card>
  )
}
