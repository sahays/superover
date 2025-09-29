import { NextRequest, NextResponse } from 'next/server';
import { mockExecutions } from '@/mocks/data';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const page = parseInt(searchParams.get('page') || '1');
  const limit = parseInt(searchParams.get('limit') || '10');
  const status = searchParams.get('status');
  const pipelineId = searchParams.get('pipelineId');

  let filteredExecutions = [...mockExecutions];

  // Apply filters
  if (status) {
    filteredExecutions = filteredExecutions.filter(execution => execution.status === status);
  }

  if (pipelineId) {
    filteredExecutions = filteredExecutions.filter(execution => execution.pipelineId === pipelineId);
  }

  // Apply pagination
  const start = (page - 1) * limit;
  const end = start + limit;
  const paginatedData = filteredExecutions.slice(start, end);
  const total = filteredExecutions.length;
  const totalPages = Math.ceil(total / limit);

  const response = {
    success: true,
    data: paginatedData,
    pagination: {
      page,
      limit,
      total,
      totalPages,
      hasNext: page < totalPages,
      hasPrev: page > 1,
    },
  };

  return NextResponse.json(response);
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { pipelineId, fileIds } = body;

    if (!pipelineId || !fileIds || !Array.isArray(fileIds)) {
      return NextResponse.json(
        { success: false, error: 'Pipeline ID and file IDs are required' },
        { status: 400 }
      );
    }

    // In real implementation, trigger workflow execution
    const newExecution = {
      id: `execution-${Date.now()}`,
      pipelineId,
      fileIds,
      status: 'running' as const,
      startedAt: new Date().toISOString(),
      progress: 0,
      steps: [],
    };

    return NextResponse.json({
      success: true,
      data: newExecution,
      message: 'Workflow execution started successfully'
    });
  } catch {
    return NextResponse.json(
      { success: false, error: 'Failed to start execution' },
      { status: 500 }
    );
  }
}