'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { X, Eye, Download, FileVideo, FileText, Calendar } from 'lucide-react';
import { Portal } from '@/components/ui/portal';

interface Pipeline {
  id: string;
  name: string;
  outputs: Array<{
    id: string;
    name: string;
    size: string;
    type: string;
  }>;
}

interface ViewOutputsModalProps {
  open: boolean;
  onClose: () => void;
  pipeline: Pipeline;
}

export function ViewOutputsModal({ open, onClose, pipeline }: ViewOutputsModalProps) {
  const handleDownload = (outputId: string, filename: string) => {
    // TODO: Implement actual download
    console.log('Downloading:', outputId, filename);
    alert(`Downloading ${filename}...`);
  };

  if (!open) return null;

  return (
    <Portal>
      <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black bg-opacity-50">
      <Card className="w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Eye className="h-5 w-5 text-blue-600" />
            </div>
            <CardTitle>Pipeline Outputs</CardTitle>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Pipeline Info */}
          <div>
            <h3 className="text-lg font-medium mb-2">{pipeline.name}</h3>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Calendar className="h-4 w-4" />
              <span>Generated outputs</span>
            </div>
          </div>

          {/* Outputs List */}
          {pipeline.outputs.length === 0 ? (
            <div className="text-center py-8">
              <FileText className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">No outputs available</p>
              <p className="text-xs text-muted-foreground">Run the pipeline to generate outputs</p>
            </div>
          ) : (
            <div className="space-y-3">
              {pipeline.outputs.map((output) => (
                <Card key={output.id} className="border border-gray-200">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-gray-100 rounded">
                          {output.type === 'video chunks' ? (
                            <FileVideo className="h-4 w-4 text-gray-600" />
                          ) : (
                            <FileText className="h-4 w-4 text-gray-600" />
                          )}
                        </div>
                        <div>
                          <p className="font-medium text-sm">{output.name}</p>
                          <div className="flex items-center gap-3 text-xs text-muted-foreground">
                            <span>{output.size}</span>
                            <Badge variant="outline" className="text-xs">
                              {output.type}
                            </Badge>
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
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <Button variant="outline" onClick={onClose} className="flex-1">
              Close
            </Button>
            {pipeline.outputs.length > 0 && (
              <Button className="flex-1">
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