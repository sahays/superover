import { NextRequest, NextResponse } from 'next/server';
import { mockExecutions } from '@/mocks/data';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const execution = mockExecutions.find(e => e.id === id);

  if (!execution) {
    return NextResponse.json(
      { success: false, error: 'Execution not found' },
      { status: 404 }
    );
  }

  return NextResponse.json({ success: true, data: execution });
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  try {
    const body = await request.json();
    const { action } = body;

    const executionExists = mockExecutions.some(e => e.id === id);

    if (!executionExists) {
      return NextResponse.json(
        { success: false, error: 'Execution not found' },
        { status: 404 }
      );
    }

    if (!['pause', 'resume', 'cancel'].includes(action)) {
      return NextResponse.json(
        { success: false, error: 'Invalid action' },
        { status: 400 }
      );
    }

    // In real implementation, perform the action on the execution
    return NextResponse.json({
      success: true,
      message: `Execution ${action}${action.endsWith('e') ? 'd' : action === 'cancel' ? 'led' : 'ed'} successfully`
    });
  } catch {
    return NextResponse.json(
      { success: false, error: 'Failed to perform action' },
      { status: 500 }
    );
  }
}