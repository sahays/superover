import { NextResponse } from 'next/server';
import { mockPipelines } from '@/mocks/data';

export async function GET() {
  // In real implementation, fetch from your backend service
  return NextResponse.json({ success: true, data: mockPipelines });
}