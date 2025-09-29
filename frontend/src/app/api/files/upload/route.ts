import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File;

    if (!file) {
      return NextResponse.json(
        { success: false, error: 'No file provided' },
        { status: 400 }
      );
    }

    // In real implementation:
    // 1. Upload file to GCS
    // 2. Trigger media-inspector service
    // 3. Return file metadata

    const newFile = {
      id: `file-${Date.now()}`,
      name: file.name,
      size: file.size,
      type: file.type,
      gcsPath: `gs://super-over-alchemy/raw/${file.name}`,
      uploadedAt: new Date().toISOString(),
      status: 'uploaded' as const,
    };

    return NextResponse.json({
      success: true,
      data: newFile,
      message: 'File uploaded successfully'
    });
  } catch {
    return NextResponse.json(
      { success: false, error: 'Upload failed' },
      { status: 500 }
    );
  }
}