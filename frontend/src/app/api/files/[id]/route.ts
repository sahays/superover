import { NextRequest, NextResponse } from 'next/server';
import { mockFiles } from '@/mocks/data';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const file = mockFiles.find(f => f.id === id);

  if (!file) {
    return NextResponse.json(
      { success: false, error: 'File not found' },
      { status: 404 }
    );
  }

  return NextResponse.json({ success: true, data: file });
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const fileExists = mockFiles.some(f => f.id === id);

  if (!fileExists) {
    return NextResponse.json(
      { success: false, error: 'File not found' },
      { status: 404 }
    );
  }

  // In real implementation, delete from GCS
  return NextResponse.json({
    success: true,
    message: 'File deleted successfully'
  });
}