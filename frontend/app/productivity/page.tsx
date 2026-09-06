'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Copy, FileClock, LayoutTemplate, RefreshCw, Search, Trash2 } from 'lucide-react';
import { AppShell } from '@/components/layout/app-shell';
import { Badge } from '@/components/ui/badge';
import { GlassPanel } from '@/components/ui/glass-surface';
import { clonePaper, createPaperTemplate, deletePaperTemplate, fetchRecentPapers, listPaperDownloads, listPaperTemplates, listProductivityJobs, retryProductivityJob } from '@/lib/api';
import type { PaperTemplate, ProductivityJob, RecentPaper } from '@/lib/api';

export default function ProductivityPage() {
  const [jobs, setJobs] = useState<ProductivityJob[]>([]);
  const [templates, setTemplates] = useState<PaperTemplate[]>([]);
  const [papers, setPapers] = useState<RecentPaper[]>([]);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [templateName, setTemplateName] = useState('');
  const [templateJson, setTemplateJson] = useState('{}');
  const [downloads, setDownloads] = useState<Record<string, string[]>>({});
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [jobResult, templateResult, recent] = await Promise.all([listProductivityJobs(), listPaperTemplates(), fetchRecentPapers()]);
      setJobs(jobResult.jobs);
      setTemplates(templateResult.templates);
      setPapers(recent);
      const downloadResults = await Promise.all(recent.slice(0, 10).map(async (paper) => [paper.id, (await listPaperDownloads(paper.id)).downloads.flatMap((item) => [item.pdf_available ? 'PDF' : '', item.docx_available ? 'DOCX' : ''].filter(Boolean))] as const));
      setDownloads(Object.fromEntries(downloadResults));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load productivity data.');
    }
  }

  useEffect(() => { void load(); }, []);

  return (
    <AppShell>
      <main className="mx-auto max-w-6xl space-y-8 p-4 sm:p-8">
        <header>
          <p className="text-sm font-medium text-slate-500">Workspace tools</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Productivity center</h1>
          <p className="mt-2 text-sm text-slate-500">Monitor generation, reuse paper settings, and keep version history auditable.</p>
        </header>
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        <section className="grid gap-5 lg:grid-cols-2">
          <GlassPanel className="p-5">
            <div className="mb-4 flex items-center gap-3"><FileClock className="h-5 w-5" /><h2 className="font-semibold">Generation center</h2></div>
            <form className="mb-4 flex gap-2" onSubmit={async (event) => { event.preventDefault(); if (!templateName.trim()) return; await createPaperTemplate({ name: templateName.trim(), template_json: JSON.parse(templateJson) }); setTemplateName(''); await load(); }}>
              <input aria-label="Template name" value={templateName} onChange={(event) => setTemplateName(event.target.value)} placeholder="New template name" className="min-w-0 flex-1 rounded-md border border-line bg-surface px-3 py-2 text-sm" />
              <button type="submit" className="rounded-md bg-primary px-3 py-2 text-xs font-semibold text-white">Save</button>
            </form>
            <div className="space-y-3">
              {jobs.length === 0 && <p className="text-sm text-slate-500">No generation jobs yet.</p>}
              {jobs.map((job) => (
                <div key={job.id} className="rounded-xl border border-white/20 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="truncate text-sm">{job.current_step || job.id}</span><Badge>{job.status}</Badge>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200/40"><div className="h-full bg-indigo-500 transition-all" style={{ width: `${job.progress_percent}%` }} /></div>
                  {job.status === 'failed' && <button className="mt-2 inline-flex items-center gap-1 text-sm text-indigo-600" onClick={async () => { await retryProductivityJob(job.id); await load(); }}><RefreshCw className="h-4 w-4" /> Retry</button>}
                </div>
              ))}
            </div>
          </GlassPanel>
          <GlassPanel className="p-5">
            <div className="mb-4 flex items-center gap-3"><LayoutTemplate className="h-5 w-5" /><h2 className="font-semibold">Paper templates</h2></div>
            <div className="space-y-3">
              {templates.length === 0 && <p className="text-sm text-slate-500">Save a configuration from the paper workflow to reuse it here.</p>}
              {templates.map((template) => <div key={template.id} className="flex items-center justify-between rounded-xl border border-white/20 p-3"><div><p className="text-sm font-medium">{template.name}</p><p className="text-xs text-slate-500">{template.description || `Version ${template.version ?? 1}`}</p></div><button aria-label={`Delete ${template.name}`} className="text-slate-500 hover:text-red-600" onClick={async () => { await deletePaperTemplate(template.id); await load(); }}><Trash2 className="h-4 w-4" /></button></div>)}
            </div>
          </GlassPanel>
        </section>
        <GlassPanel className="p-5" data-testid="recent-productivity-papers">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><h2 className="font-semibold">Recent papers</h2><p className="text-xs text-slate-500">Search, clone, and inspect available exports without changing the source paper.</p></div>
            <div className="flex gap-2">
              <label className="relative"><Search className="pointer-events-none absolute left-2 top-2.5 h-4 w-4 text-slate-400" /><input aria-label="Search papers" value={query} onChange={(event) => setQuery(event.target.value)} className="w-40 rounded-md border border-line bg-surface py-2 pl-8 pr-2 text-sm" placeholder="Search" /></label>
              <select aria-label="Filter paper status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="rounded-md border border-line bg-surface px-2 text-sm"><option value="">All statuses</option><option value="draft">Draft</option><option value="approved">Approved</option></select>
            </div>
          </div>
          <div className="mt-4 space-y-2">
            {papers.filter((paper) => (!statusFilter || paper.status === statusFilter) && (!query || `${paper.title} ${paper.subject ?? ''} ${paper.exam_type ?? ''}`.toLowerCase().includes(query.toLowerCase()))).map((paper) => (
              <div key={paper.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line p-3">
                <div><Link href={`/review?paper_id=${paper.id}`} className="text-sm font-medium text-primary hover:underline">{paper.title}</Link><p className="text-xs text-slate-500">{paper.status} · {downloads[paper.id]?.join(' · ') || 'No exports'}</p></div>
                <button type="button" className="inline-flex items-center gap-1 rounded-md border border-line px-3 py-1.5 text-xs font-semibold" onClick={async () => { const result = await clonePaper(paper.id); window.location.href = `/review?paper_id=${result.paper_id}`; }}><Copy className="h-3.5 w-3.5" /> Clone</button>
              </div>
            ))}
            {papers.length === 0 && <p className="text-sm text-slate-500">No recent papers found.</p>}
          </div>
        </GlassPanel>
        <Link className="text-sm text-indigo-600 hover:underline" href="/dashboard">Back to dashboard</Link>
      </main>
    </AppShell>
  );
}
