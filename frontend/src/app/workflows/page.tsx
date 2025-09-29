'use client';

import { useState } from 'react';
import { Plus, Play, Pause, Trash2, Edit2, Copy, Search } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { workflowsApi } from '@/lib/api';
import { Pipeline } from '@/types';
import { formatDistanceToNow } from 'date-fns';

export default function WorkflowsPage() {
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
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">Workflows</h1>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Workflows</h1>
          <p className="text-muted-foreground">Manage your processing pipelines</p>
        </div>
        <Button>
          <Plus className="h-4 w-4 mr-2" />
          Create Pipeline
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center">
              <div className="p-2 bg-blue-100 rounded-md">
                <Play className="h-4 w-4 text-blue-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-muted-foreground">Total Pipelines</p>
                <p className="text-2xl font-bold">{pipelines.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center">
              <div className="p-2 bg-green-100 rounded-md">
                <Play className="h-4 w-4 text-green-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-muted-foreground">Active</p>
                <p className="text-2xl font-bold">
                  {pipelines.filter((p: Pipeline) => p.status === 'active').length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center">
              <div className="p-2 bg-yellow-100 rounded-md">
                <Pause className="h-4 w-4 text-yellow-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-muted-foreground">Draft</p>
                <p className="text-2xl font-bold">
                  {pipelines.filter((p: Pipeline) => p.status === 'draft').length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center">
              <div className="p-2 bg-gray-100 rounded-md">
                <Pause className="h-4 w-4 text-gray-600" />
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-muted-foreground">Inactive</p>
                <p className="text-2xl font-bold">
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

      {/* Pipelines Table */}
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Steps</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Updated</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredPipelines.map((pipeline: Pipeline) => (
              <TableRow key={pipeline.id}>
                <TableCell className="font-medium">{pipeline.name}</TableCell>
                <TableCell className="text-muted-foreground max-w-xs truncate">
                  {pipeline.description}
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className={getStatusColor(pipeline.status)}>
                    {pipeline.status}
                  </Badge>
                </TableCell>
                <TableCell>{pipeline.steps.length} steps</TableCell>
                <TableCell>
                  {formatDistanceToNow(new Date(pipeline.createdAt), { addSuffix: true })}
                </TableCell>
                <TableCell>
                  {formatDistanceToNow(new Date(pipeline.updatedAt), { addSuffix: true })}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Button variant="ghost" size="sm">
                      <Play className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm">
                      <Copy className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm">
                      <Edit2 className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeletePipeline(pipeline.id)}
                      disabled={deletePipelineMutation.isPending}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}