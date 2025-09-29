'use client';

import { useState } from 'react';
import { Plus, Play, Pause, Trash2, Edit2, Copy, Search, MoreVertical } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import Link from 'next/link';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { workflowsApi } from '@/lib/api';
import { Pipeline } from '@/types';
import { formatDistanceToNow } from 'date-fns';

export default function PipelinesPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const queryClient = useQueryClient();

  const { data: pipelinesData, isLoading } = useQuery({
    queryKey: ['workflows', 'pipelines'],
    queryFn: () => workflowsApi.getPipelines(),
  });

  const deletePipelineMutation = useMutation({
    mutationFn: workflowsApi.deletePipeline,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows', 'pipelines'] });
    },
  });

  const pipelines = pipelinesData?.data || [];

  const filteredPipelines = pipelines.filter((pipeline: Pipeline) => {
    const matchesSearch = pipeline.name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = !statusFilter || statusFilter === 'all' || pipeline.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const handleDeletePipeline = async (id: string) => {
    if (confirm('Are you sure you want to delete this pipeline?')) {
      try {
        await deletePipelineMutation.mutateAsync(id);
      } catch (error) {
        console.error('Failed to delete pipeline:', error);
      }
    }
  };

  const handleRunPipeline = (id: string) => {
    console.log('Run pipeline:', id);
  };

  const handleEditPipeline = (id: string) => {
    console.log('Edit pipeline:', id);
  };

  const handleDuplicatePipeline = (id: string) => {
    console.log('Duplicate pipeline:', id);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'draft':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'inactive':
        return 'bg-gray-100 text-gray-800 border-gray-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h1 className="text-3xl font-bold">Pipelines</h1>
          </div>

          {/* Stats Cards Skeleton */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <Card key={i} className="animate-pulse">
                <CardContent className="p-6">
                  <div className="flex items-center space-x-4">
                    <div className="h-8 w-8 bg-gray-200 rounded"></div>
                    <div className="space-y-2">
                      <div className="h-4 bg-gray-200 rounded w-24"></div>
                      <div className="h-6 bg-gray-200 rounded w-16"></div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Pipeline Cards Skeleton */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => (
              <Card key={i} className="animate-pulse">
                <CardHeader>
                  <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="h-3 bg-gray-200 rounded"></div>
                    <div className="h-3 bg-gray-200 rounded w-2/3"></div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold">Pipelines</h1>
            <p className="text-muted-foreground">Manage your processing pipelines</p>
          </div>
          <Link href="/pipelines/create">
            <Button className="w-full sm:w-auto">
              <Plus className="h-4 w-4 mr-2" />
              Create Pipeline
            </Button>
          </Link>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4 sm:p-6">
              <div className="flex items-center space-x-4">
                <div className="p-2 bg-blue-100 rounded-md">
                  <Play className="h-4 w-4 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Total Pipelines</p>
                  <p className="text-xl sm:text-2xl font-bold">{pipelines.length}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 sm:p-6">
              <div className="flex items-center space-x-4">
                <div className="p-2 bg-green-100 rounded-md">
                  <Play className="h-4 w-4 text-green-600" />
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Active</p>
                  <p className="text-xl sm:text-2xl font-bold">
                    {pipelines.filter((p: Pipeline) => p.status === 'active').length}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 sm:p-6">
              <div className="flex items-center space-x-4">
                <div className="p-2 bg-yellow-100 rounded-md">
                  <Pause className="h-4 w-4 text-yellow-600" />
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Draft</p>
                  <p className="text-xl sm:text-2xl font-bold">
                    {pipelines.filter((p: Pipeline) => p.status === 'draft').length}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 sm:p-6">
              <div className="flex items-center space-x-4">
                <div className="p-2 bg-gray-100 rounded-md">
                  <Pause className="h-4 w-4 text-gray-600" />
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Inactive</p>
                  <p className="text-xl sm:text-2xl font-bold">
                    {pipelines.filter((p: Pipeline) => p.status === 'inactive').length}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
            <Input
              placeholder="Search pipelines..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-full sm:w-48">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="inactive">Inactive</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Pipeline Cards */}
        {filteredPipelines.length === 0 ? (
          <Card className="text-center py-12">
            <CardContent>
              <Play className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No pipelines found</h3>
              <p className="text-muted-foreground mb-4">
                {search || statusFilter !== 'all' ? 'Try adjusting your filters' : 'Get started by creating your first pipeline'}
              </p>
              <Link href="/pipelines/create">
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Create Pipeline
                </Button>
              </Link>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredPipelines.map((pipeline: Pipeline) => (
              <Card key={pipeline.id} className="hover:shadow-md transition-shadow">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <CardTitle className="text-lg font-semibold truncate">
                        {pipeline.name}
                      </CardTitle>
                      <Badge variant="outline" className={`${getStatusColor(pipeline.status)} mt-2 w-fit`}>
                        {pipeline.status}
                      </Badge>
                    </div>

                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => handleRunPipeline(pipeline.id)}>
                          <Play className="mr-2 h-4 w-4" />
                          Run Pipeline
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleEditPipeline(pipeline.id)}>
                          <Edit2 className="mr-2 h-4 w-4" />
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleDuplicatePipeline(pipeline.id)}>
                          <Copy className="mr-2 h-4 w-4" />
                          Duplicate
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onClick={() => handleDeletePipeline(pipeline.id)}
                          className="text-destructive focus:text-destructive"
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </CardHeader>

                <CardContent className="pt-0">
                  <div className="space-y-3">
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {pipeline.description}
                    </p>

                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>{pipeline.steps.length} steps</span>
                      <span>{pipeline.category}</span>
                    </div>

                    <div className="text-xs text-muted-foreground">
                      <div>Created {formatDistanceToNow(new Date(pipeline.createdAt), { addSuffix: true })}</div>
                      <div>Updated {formatDistanceToNow(new Date(pipeline.updatedAt), { addSuffix: true })}</div>
                    </div>

                    {pipeline.estimatedDuration && (
                      <div className="text-xs text-muted-foreground">
                        Est. duration: {Math.round(pipeline.estimatedDuration / 60)} min
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}