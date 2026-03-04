import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'

interface SceneManifestCardProps {
  manifest: {
    chunks?: {
      count: number
      duration_per_chunk: number
      items?: Array<{ filename: string }>
    }
    compressed?: { gcs_path: string }
    audio?: { gcs_path: string }
  }
}

export function SceneManifestCard({ manifest }: SceneManifestCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Processing Info</CardTitle>
      </CardHeader>
      <CardContent>
        <Accordion type="single" collapsible className="w-full">
          {manifest.chunks && (
            <AccordionItem value="chunks">
              <AccordionTrigger>
                Chunks ({manifest.chunks.count})
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">
                    <span className="font-mono">{manifest.chunks.count}</span> chunks x <span className="font-mono">{manifest.chunks.duration_per_chunk}s</span> each
                  </p>
                  {manifest.chunks.items && (
                    <div className="space-y-1">
                      {manifest.chunks.items.map((chunk, idx) => (
                        <div key={idx} className="text-xs font-mono text-muted-foreground">
                          Chunk {idx}: {chunk.filename}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </AccordionContent>
            </AccordionItem>
          )}
          {manifest.compressed && (
            <AccordionItem value="compressed">
              <AccordionTrigger>Compressed Video</AccordionTrigger>
              <AccordionContent>
                <p className="text-sm text-muted-foreground font-mono break-all">
                  {manifest.compressed.gcs_path}
                </p>
              </AccordionContent>
            </AccordionItem>
          )}
          {manifest.audio && (
            <AccordionItem value="audio">
              <AccordionTrigger>Audio</AccordionTrigger>
              <AccordionContent>
                <p className="text-sm text-muted-foreground font-mono break-all">
                  {manifest.audio.gcs_path}
                </p>
              </AccordionContent>
            </AccordionItem>
          )}
        </Accordion>
      </CardContent>
    </Card>
  )
}
