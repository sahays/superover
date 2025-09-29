import { NextRequest, NextResponse } from 'next/server';
import { mockPipelines } from '@/mocks/data';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const pipeline = mockPipelines.find(p => p.id === id);

  if (!pipeline) {
    return NextResponse.json(
      { success: false, error: 'Pipeline not found' },
      { status: 404 }
    );
  }

  return NextResponse.json({ success: true, data: pipeline });
}