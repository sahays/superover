'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { X, Download, FileVideo, Calendar, BarChart } from 'lucide-react';
import { Portal } from '@/components/ui/portal';

interface Pipeline {
  id: string;
  name: string;
  outputs: Array<{
    id: string;
    name: string;
    size: string;
    type: string;
    vmafScore: number;
  }>;
}

interface ViewOutputsModalProps {
  open: boolean;
  onClose: () => void;
  pipeline: Pipeline;
}

export function ViewOutputsModal({ open, onClose, pipeline }: ViewOutputsModalProps) {
  const handleDownload = (outputId: string, filename: string) => {
    console.log('Downloading:', outputId, filename);
    alert(`Downloading ${filename}...`);
  };

  const handleDownloadAll = () => {
    console.log('Downloading all outputs for pipeline:', pipeline.id);
    alert('Downloading all outputs as ZIP...');
  };

  const getVmafColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 70) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getVmafLabel = (score: number) => {
    if (score >= 80) return 'Excellent';
    if (score >= 70) return 'Good';
    return 'Fair';
  };

  if (!open) return null;

  return (
    <Portal>
      <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black bg-opacity-50">
      <Card className="w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-100 rounded-lg">
              <Download className="h-5 w-5 text-purple-600" />
            </div>
            <CardTitle>Pipeline Outputs</CardTitle>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>

        <CardContent className="space-y-6">
          <div>
            <h3 className="text-lg font-medium mb-2">{pipeline.name}</h3>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Calendar className="h-4 w-4" />
              <span>Transcoded outputs with VMAF quality assessment</span>
            </div>
          </div>

          {pipeline.outputs.length === 0 ? (
            <div className="text-center py-8">
              <FileVideo className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">No outputs available</p>
              <p className="text-xs text-muted-foreground">Run the pipeline to generate transcoded videos</p>
            </div>
          ) : (
            <>
              {/* Quality Summary */}
              <div className="bg-gray-50 p-4 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <BarChart className="h-4 w-4 text-gray-600" />
                  <span className="text-sm font-medium">Quality Assessment</span>
                </div>
                <div className="text-sm text-muted-foreground">
                  Average VMAF Score: <span className={`font-medium ${getVmafColor(pipeline.outputs.reduce((sum, out) => sum + out.vmafScore, 0) / pipeline.outputs.length)}`}>
                    {(pipeline.outputs.reduce((sum, out) => sum + out.vmafScore, 0) / pipeline.outputs.length).toFixed(1)}
                  </span> ({getVmafLabel(pipeline.outputs.reduce((sum, out) => sum + out.vmafScore, 0) / pipeline.outputs.length)})
                </div>
              </div>

              {/* Outputs List */}
              <div className="space-y-3">
                {pipeline.outputs.map((output) => (
                  <Card key={output.id} className="border border-gray-200">
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-purple-100 rounded">
                            <FileVideo className="h-4 w-4 text-purple-600" />
                          </div>
                          <div>
                            <p className="font-medium text-sm">{output.name}</p>
                            <div className="flex items-center gap-3 text-xs text-muted-foreground">
                              <span>{output.size}</span>
                              <Badge variant="outline" className="text-xs">
                                {output.type}
                              </Badge>
                              <div className="flex items-center gap-1">
                                <BarChart className="h-3 w-3" />
                                <span className={`font-medium ${getVmafColor(output.vmafScore)}`}>
                                  VMAF: {output.vmafScore}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDownload(output.id, output.name)}
                        >
                          <Download className="h-3 w-3 mr-1" />
                          Download
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </>
          )}

          <div className="flex gap-3 pt-4">
            <Button variant="outline" onClick={onClose} className="flex-1">
              Close
            </Button>
            {pipeline.outputs.length > 0 && (
              <Button onClick={handleDownloadAll} className="flex-1">
                <Download className="h-4 w-4 mr-2" />
                Download All
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
      </div>
    </Portal>
  );
}