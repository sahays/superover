import { AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'

interface ResultChunkItemProps {
  result: any
  index: number
}

export function ResultChunkItem({ result, index, totalResults }: ResultChunkItemProps & { totalResults?: number }) {
  const isSubtitle = result.result_data?.prompt_type === 'subtitling' || result.result_data?.prompt_type === 'transcription'
  const subtitleText = result.result_data?.subtitle_text
  const rawText = result.result_data?.raw_text
  const hasFormattedText = isSubtitle && subtitleText ? true : !!rawText

  return (
    <AccordionItem value={`result-${index}`}>
      <AccordionTrigger>
        <div className="flex gap-2 items-center">
          <span>{(totalResults ?? 2) > 1 ? `Result ${index + 1}` : 'Result'}</span>
          {result.result_data?.token_usage?.estimated_cost_usd !== undefined && (
            <span className="text-xs font-normal text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
              <span className="font-mono">${result.result_data.token_usage.estimated_cost_usd.toFixed(4)}</span>
            </span>
          )}
          {isSubtitle && <span className="text-xs text-muted-foreground">(Subtitles)</span>}
        </div>
      </AccordionTrigger>
      <AccordionContent>
        {result.result_data?.token_usage && (
          <div className="mb-4 text-xs text-muted-foreground flex gap-4 border-b pb-2">
            <div>
              Prompt Tokens: <span className="font-mono">{result.result_data.token_usage.prompt_tokens?.toLocaleString()}</span>
              {result.result_data.token_usage.applied_input_rate && (
                <span className="ml-1 opacity-70 font-mono">(@ ${result.result_data.token_usage.applied_input_rate.toFixed(2)}/1M)</span>
              )}
            </div>
            <div>
              Output Tokens: <span className="font-mono">{result.result_data.token_usage.candidates_tokens?.toLocaleString()}</span>
              {result.result_data.token_usage.applied_output_rate && (
                <span className="ml-1 opacity-70 font-mono">(@ ${result.result_data.token_usage.applied_output_rate.toFixed(2)}/1M)</span>
              )}
            </div>
            <div>Total: <span className="font-mono">{result.result_data.token_usage.total_tokens?.toLocaleString()}</span></div>
          </div>
        )}
        {hasFormattedText ? (
          <div className="space-y-4">
            <div className="rounded bg-slate-100 p-4 dark:bg-slate-800 max-h-[500px] overflow-y-auto">
              <pre className="whitespace-pre-wrap text-sm font-mono">
                {subtitleText || rawText}
              </pre>
            </div>
            <details className="text-xs text-muted-foreground">
              <summary className="cursor-pointer hover:text-foreground">Show raw JSON</summary>
              <pre className="mt-2 overflow-x-auto rounded bg-slate-50 p-3 dark:bg-slate-900">
                {JSON.stringify(result.result_data, null, 2)}
              </pre>
            </details>
          </div>
        ) : (
          <pre className="overflow-x-auto rounded bg-slate-100 p-3 text-xs dark:bg-slate-800">
            {JSON.stringify(result.result_data, null, 2)}
          </pre>
        )}
      </AccordionContent>
    </AccordionItem>
  )
}
