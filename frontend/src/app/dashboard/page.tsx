'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useFiles } from '@/hooks/useFiles';
import { useExecutions } from '@/hooks/useExecutions';
import {
  FileText,
  Play,
  Activity,
  Download,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import Link from 'next/link';

export default function DashboardPage() {
  const { data: filesData } = useFiles({ limit: 5 });
  const { data: executionsData } = useExecutions({ limit: 5 });

  const executions = executionsData?.data || [];

  // Calculate stats
  const completedExecutions = executions.filter(e => e.status === 'completed').length;
  const runningExecutions = executions.filter(e => e.status === 'running').length;
  const failedExecutions = executions.filter(e => e.status === 'failed').length;
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-2 text-gray-600">
          Overview of your video processing workflows and analytics
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Files</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{filesData?.pagination?.total || 0}</div>
            <p className="text-xs text-muted-foreground">
              Media files uploaded
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Running</CardTitle>
            <Activity className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{runningExecutions}</div>
            <p className="text-xs text-muted-foreground">
              Active executions
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Completed</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{completedExecutions}</div>
            <p className="text-xs text-muted-foreground">
              Successful executions
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Failed</CardTitle>
            <AlertCircle className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{failedExecutions}</div>
            <p className="text-xs text-muted-foreground">
              Failed executions
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Link href="/files">
              <Button className="h-20 flex-col w-full" variant="outline">
                <FileText className="h-6 w-6 mb-2" />
                Upload Files
              </Button>
            </Link>
            <Link href="/workflows">
              <Button className="h-20 flex-col w-full" variant="outline">
                <Play className="h-6 w-6 mb-2" />
                Create Workflow
              </Button>
            </Link>
            <Link href="/executions">
              <Button className="h-20 flex-col w-full" variant="outline">
                <Activity className="h-6 w-6 mb-2" />
                Monitor Executions
              </Button>
            </Link>
            <Link href="/outputs">
              <Button className="h-20 flex-col w-full" variant="outline">
                <Download className="h-6 w-6 mb-2" />
                View Outputs
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}