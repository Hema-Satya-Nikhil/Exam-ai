"use client";

import { useCallback, useEffect, useState } from "react";
import { ClipboardList, FilePlus2, FileText, ListChecks, Plus, Users } from "lucide-react";

import { useAuth } from "@/contexts/auth-context";
import { AppShell } from "@/components/layout/app-shell";
import { fetchRecentPapers, type RecentPaper } from "@/lib/api";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton, SkeletonList } from "@/components/ui/skeleton";
import { GlassPanel, GlassSurface } from "@/components/ui/glass-surface";

type LoadState = "loading" | "error" | "ready";

function formatDate(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return "";
  }
}

function greetingFor(hour: number): string {
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

const WORKFLOW_STEPS = [
  { label: "Syllabus", detail: "Upload and confirm the unit scope" },
  { label: "Exam structure", detail: "Parts, sections and marks split" },
  { label: "Blueprint & Bloom", detail: "Question distribution and difficulty" },
  { label: "Generate", detail: "Deterministic paper generation" },
  { label: "Review", detail: "Validate, regenerate and lock" },
  { label: "Export", detail: "PDF / DOCX with clean metadata" }
] as const;

export default function DashboardPage() {
  const { user } = useAuth();
  const isAdmin = !!user?.roles?.includes("admin");
  const [state, setState] = useState<LoadState>("loading");
  const [papers, setPapers] = useState<RecentPaper[]>([]);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    fetchRecentPapers()
      .then((items) => {
        if (cancelled) return;
        setPapers(items);
        setState("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  // Greeting is set after mount to avoid server/client time drift.
  const [greeting, setGreeting] = useState("Welcome");
  useEffect(() => {
    setGreeting(greetingFor(new Date().getHours()));
  }, []);

  const displayName = user?.full_name?.trim() || user?.email?.split("@")[0] || "";

  const quickActions = [
    { label: "Create Question Paper", description: "Start from the syllabus", href: "/create", icon: FilePlus2 },
    { label: "Recent Papers", description: "Continue where you left off", href: "/dashboard#recent", icon: ClipboardList },
    { label: "Review Papers", description: "Validate and export", href: "/review", icon: ListChecks }
  ] as const;

  return (
    <AppShell>
      <main className="pb-16" aria-labelledby="dashboard-heading">
        <header className="animate-fade-in rounded-2xl border border-white/75 bg-white/55 p-6 shadow-glass-soft backdrop-blur-glass sm:p-8">
          {state === "loading" ? (
            <Skeleton className="h-8 w-80 max-w-full" />
          ) : (
            <h1 id="dashboard-heading" className="text-heading text-text-primary">
              {greeting}
              {displayName ? ", " + displayName : ""}
            </h1>
          )}
          <p className="mt-2 max-w-2xl text-body text-text-secondary">
            Create, review, and manage your examination papers.
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <ButtonLink href="/create" leadingIcon={<Plus aria-hidden="true" />}>
              Create Question Paper
            </ButtonLink>
            {isAdmin && (
              <ButtonLink
                href="/admin"
                data-testid="people-access-link"
                variant="secondary"
                leadingIcon={<Users aria-hidden="true" />}
              >
                People &amp; Access
              </ButtonLink>
            )}
          </div>
        </header>

        <section aria-labelledby="quick-actions-heading" className="mt-10 animate-fade-in">
          <h2 id="quick-actions-heading" className="text-metadata font-semibold uppercase tracking-[0.14em] text-text-muted">
            Quick actions
          </h2>
          <div className="mt-3 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {quickActions.map((action) => (
              <a
                key={action.href}
                href={action.href}
                className="group flex items-start gap-3 rounded-xl border border-white/75 bg-white/60 p-4 shadow-glass-soft backdrop-blur-sm transition-all duration-micro ease-standard hover:-translate-y-0.5 hover:bg-white/80 hover:shadow-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary-soft text-primary" aria-hidden="true">
                  <action.icon className="h-[18px] w-[18px]" />
                </span>
                <span className="min-w-0">
                  <span className="block text-small font-semibold text-text-primary">{action.label}</span>
                  <span className="mt-0.5 block text-metadata text-text-muted">{action.description}</span>
                </span>
              </a>
            ))}
            {isAdmin && (
              <a
                href="/admin"
                className="group flex items-start gap-3 rounded-xl border border-white/75 bg-white/60 p-4 shadow-glass-soft backdrop-blur-sm transition-all duration-micro ease-standard hover:-translate-y-0.5 hover:bg-white/80 hover:shadow-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary-soft text-primary" aria-hidden="true">
                  <Users className="h-[18px] w-[18px]" />
                </span>
                <span className="min-w-0">
                  <span className="block text-small font-semibold text-text-primary">People &amp; Access</span>
                  <span className="mt-0.5 block text-metadata text-text-muted">Approvals and audit</span>
                </span>
              </a>
            )}
          </div>
        </section>

        <div className="mt-10 grid gap-6 lg:grid-cols-[1.6fr_1fr]">
          <GlassSurface as="section" aria-labelledby="recent-papers-heading" className="p-0">
            <CardHeader>
              <CardTitle id="recent-papers-heading">Recent papers</CardTitle>
              <CardDescription>Your latest generated question papers</CardDescription>
            </CardHeader>
            <CardContent className="px-5 pb-5 sm:px-6">
              {state === "loading" && (
                <div role="status">
                  <p className="text-small text-text-secondary">Loading recent papers...</p>
                  <SkeletonList rows={3} className="mt-3" />
                </div>
              )}

              {state === "error" && (
                <div className="flex flex-col gap-4">
                  <Alert variant="error" title="Unable to load recent papers.">
                    Check your connection and try again.
                  </Alert>
                  <div>
                    <Button variant="outline" onClick={retry}>
                      Retry
                    </Button>
                  </div>
                </div>
              )}

              {state === "ready" && papers.length === 0 && (
                <EmptyState
                  icon={<FileText />}
                  title="No papers yet"
                  description="Create your first question paper to get started."
                  action={
                    <ButtonLink href="/create" leadingIcon={<Plus aria-hidden="true" />}>
                      Create Question Paper
                    </ButtonLink>
                  }
                />
              )}

              {state === "ready" && papers.length > 0 && (
                <ul data-testid="recent-papers-list" className="grid gap-3">
                  {papers.map((paper) => (
                    <li key={paper.id} className="flex flex-col gap-4 rounded-xl border border-white/75 bg-white/55 p-4 shadow-low transition-all duration-micro hover:-translate-y-0.5 hover:bg-white/80 hover:shadow-medium sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <p className="text-body font-semibold text-text-primary">{paper.subject || paper.title}</p>
                        <p className="mt-0.5 text-metadata text-text-secondary">
                          {paper.exam_type}
                          {typeof paper.total_marks === "number" ? " \u00b7 " + paper.total_marks + " Marks" : ""}
                          {typeof paper.duration_minutes === "number" ? " \u00b7 " + paper.duration_minutes + " Minutes" : ""}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          {paper.status ? <StatusBadge status={paper.status} /> : null}
                          {paper.created_at ? (
                            <span className="text-metadata text-text-muted">Generated {formatDate(paper.created_at)}</span>
                          ) : null}
                        </div>
                      </div>
                      <ButtonLink
                        href={"/review?paper_id=" + encodeURIComponent(paper.id)}
                        variant="outline"
                        size="sm"
                        className="shrink-0 self-start sm:self-center"
                      >
                        Open Review
                      </ButtonLink>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </GlassSurface>

          <GlassSurface as="section" aria-labelledby="workflow-heading" className="p-0">
            <CardHeader>
              <CardTitle id="workflow-heading">Your workflow</CardTitle>
              <CardDescription>Guidance &mdash; the standard path from syllabus to export.</CardDescription>
            </CardHeader>
            <CardContent>
              <ol className="flex flex-col gap-4">
                {WORKFLOW_STEPS.map((step, index) => (
                  <li key={step.label} className="flex items-start gap-3">
                    <span
                      aria-hidden="true"
                      className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-pill bg-slate-100 text-metadata font-semibold text-text-secondary"
                    >
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span>
                      <span className="block text-small font-medium text-text-primary">{step.label}</span>
                      <span className="mt-0.5 block text-metadata text-text-muted">{step.detail}</span>
                    </span>
                  </li>
                ))}
              </ol>
            </CardContent>
          </GlassSurface>
        </div>

        <GlassPanel className="mt-10 animate-fade-in">
          <CardContent className="flex flex-col items-start justify-between gap-4 py-6 sm:flex-row sm:items-center">
            <div>
              <p className="text-body font-medium text-text-primary">Need to create a new paper?</p>
              <p className="mt-0.5 text-small text-text-secondary">Start from the syllabus and let the blueprint do the heavy lifting.</p>
            </div>
            <ButtonLink href="/create" leadingIcon={<Plus aria-hidden="true" />} className="shrink-0">
              Create Question Paper
            </ButtonLink>
          </CardContent>
        </GlassPanel>
      </main>
    </AppShell>
  );
}
