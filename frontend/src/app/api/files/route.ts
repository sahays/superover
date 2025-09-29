import { NextRequest, NextResponse } from 'next/server';
import { mockFiles } from '@/mocks/data';

// For now, using mock data. Replace with actual API calls to your backend services
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const page = parseInt(searchParams.get('page') || '1');
  const limit = parseInt(searchParams.get('limit') || '10');
  const search = searchParams.get('search');
  const status = searchParams.get('status');
  const type = searchParams.get('type');

  let filteredFiles = [...mockFiles];

  // Apply filters
  if (search) {
    filteredFiles = filteredFiles.filter(file =>
      file.name.toLowerCase().includes(search.toLowerCase())
    );
  }

  if (status) {
    filteredFiles = filteredFiles.filter(file => file.status === status);
  }

  if (type) {
    filteredFiles = filteredFiles.filter(file => file.type.includes(type));
  }

  // Apply pagination
  const start = (page - 1) * limit;
  const end = start + limit;
  const paginatedData = filteredFiles.slice(start, end);
  const total = filteredFiles.length;
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

export async function POST() {
  // Handle file upload
  // For now, return mock success response
  // In real implementation, upload to GCS and call media-inspector service

  const newFile = {
    id: `file-${Date.now()}`,
    name: 'uploaded-file.mp4',
    size: 1024000,
    type: 'video/mp4',
    gcsPath: `gs://super-over-alchemy/raw/uploaded-file-${Date.now()}.mp4`,
    uploadedAt: new Date().toISOString(),
    status: 'uploaded' as const,
  };

  return NextResponse.json({
    success: true,
    data: newFile,
    message: 'File uploaded successfully'
  });
}