 'use client';

import {
  ArrowRight,
  BookOpenCheck,
  ClipboardList,
  Download,
  FileText,
  ListChecks,
  ShieldCheck,
  Workflow,
  Moon,
  Sun,
} from 'lucide-react';

import { ButtonLink } from '@/components/ui/button';
import { LandingFooter } from '@/components/landing/landing-footer';
import { useTheme } from '@/contexts/theme-context';
import { BrandLogo } from '@/components/brand/brand-logo';

const VALUE_PROPS = [
  {
    icon: BookOpenCheck,
    title: 'Syllabus-aware',
    description: 'Questions are generated from the topics in your uploaded syllabus — not generic templates.',
  },
  {
    icon: ClipboardList,
    title: 'Structured',
    description: 'Configure exam structures, Bloom levels, marks distribution, and internal choices.',
  },
  {
    icon: ListChecks,
    title: 'Reviewable',
    description: 'Edit, regenerate, and lock individual questions before the paper is finalised.',
  },
  {
    icon: Download,
    title: 'Exportable',
    description: 'Download clean, validated examination papers as PDF or DOCX.',
  },
] as const;

const WORKFLOW_STEPS = [
  { number: '01', title: 'Upload syllabus', description: 'PDF, DOCX, or an image — parsed into atomic topics you confirm.' },
  { number: '02', title: 'Configure exam', description: 'Set parts, sections, marks, duration, and internal choices.' },
  { number: '03', title: 'Generate questions', description: 'Questions are drafted against your structure and constraints.' },
  { number: '04', title: 'Review & export', description: 'Refine the wording, validate the rules, export the paper.' },
] as const;

export default function HomePage() {
  const { theme, toggleTheme } = useTheme();
  return (
    <main className="public-ambient min-h-screen bg-background text-text-primary">
      <header className="mx-auto flex max-w-7xl items-center justify-between px-6 pt-5 lg:px-10">
        <BrandLogo className="h-20 w-20 sm:h-24 sm:w-24" priority />
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
          className="public-control inline-flex items-center gap-2 rounded-pill px-3 py-2 text-small font-medium text-text-secondary transition-colors hover:border-primary/50 hover:text-primary"
        >
          {theme === 'light' ? <Moon className="h-4 w-4" aria-hidden /> : <Sun className="h-4 w-4" aria-hidden />}
          <span className="hidden sm:inline">{theme === 'light' ? 'Dark appearance' : 'Light appearance'}</span>
        </button>
      </header>
      {/* Hero */}
      <section className="mx-auto max-w-7xl px-6 pb-20 pt-14 lg:px-10 lg:pt-20">
        <div className="grid items-center gap-12 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="animate-fade-in space-y-7">
            <span className="public-glass-subtle inline-flex items-center gap-2 rounded-pill px-4 py-1.5 text-label font-medium text-text-secondary">
              <ShieldCheck className="h-4 w-4 text-primary" aria-hidden />
              ExamCraft AI
            </span>
            <div className="space-y-4">
              <h1 className="max-w-2xl text-display font-semibold leading-[1.04] tracking-[-0.04em]">
                Create better question papers with AI, calmly.
              </h1>
              <p className="max-w-xl text-body leading-7 text-text-secondary">
                Upload your syllabus, configure the exam structure, and generate validated
                questions — then review, refine, and export a clean paper for your students.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-4">
              <ButtonLink href="/create" variant="primary" size="lg" trailingIcon={<ArrowRight className="h-4 w-4" aria-hidden />}>
                Create Question Paper
              </ButtonLink>
              <ButtonLink href="#how-it-works" variant="outline" size="lg">
                Explore how it works
              </ButtonLink>
            </div>
          </div>

          {/* Exam structure highlight — clearly labelled as an example */}
          <aside
            aria-label="Example exam structure"
            className="public-glass animate-fade-in rounded-2xl p-5 sm:p-6"
          >
            <div className="flex items-center gap-2 text-label font-semibold uppercase tracking-wide text-text-muted">
              <Workflow className="h-4 w-4 text-primary" aria-hidden />
              Example structure
            </div>
            <div className="mt-5 space-y-4">
              <div className="public-glass-subtle rounded-xl p-4">
                <p className="text-label font-semibold uppercase tracking-wide text-primary">Part A</p>
                <p className="mt-1 text-small text-text-secondary">Short answer · 10 × 2 marks</p>
                <p className="mt-1 text-small font-semibold text-text-primary">20 Marks · 20 Minutes</p>
              </div>
              <div className="public-glass-subtle rounded-xl p-4">
                <p className="text-label font-semibold uppercase tracking-wide text-primary">Part B</p>
                <p className="mt-1 text-small text-text-secondary">Main paper · internal choices</p>
                <p className="mt-1 text-small font-semibold text-text-primary">30 Marks · 90 Minutes</p>
                <div className="mt-3 flex items-center gap-2" aria-hidden>
                  <span className="h-px flex-1 bg-line" />
                  <span className="text-metadata font-bold text-text-muted">OR</span>
                  <span className="h-px flex-1 bg-line" />
                </div>
                <p className="mt-3 text-metadata text-text-muted">
                  2(a) or 2(b) — faculty confirm every choice relationship.
                </p>
              </div>
            </div>
            <p className="mt-5 text-metadata text-text-muted">
              Illustrative example — you configure the structure your institution requires.
            </p>
          </aside>
        </div>
      </section>

      {/* Value proposition */}
      <section aria-labelledby="value-heading" className="border-y border-line bg-surface/55">
        <div className="mx-auto max-w-7xl px-6 py-16 lg:px-10">
          <h2 id="value-heading" className="text-heading font-semibold tracking-tight">
            Built around the faculty workflow
          </h2>
          <p className="mt-2 max-w-2xl text-body text-text-secondary">
            Everything in ExamCraft exists to take a syllabus from upload to a validated,
            exportable examination paper.
          </p>
          <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {VALUE_PROPS.map(({ icon: Icon, title, description }) => (
              <div
                key={title}
                className="public-glass-subtle rounded-2xl p-5 transition-all duration-micro hover:-translate-y-0.5 hover:shadow-medium"
              >
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-md bg-primary-soft text-primary">
                  <Icon className="h-5 w-5" aria-hidden />
                </span>
                <h3 className="mt-4 text-body font-semibold">{title}</h3>
                <p className="mt-1.5 text-small leading-6 text-text-secondary">{description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" aria-labelledby="how-heading" className="mx-auto max-w-7xl px-6 py-16 lg:px-10">
        <h2 id="how-heading" className="text-heading font-semibold tracking-tight">
          How it works
        </h2>
        <p className="mt-2 max-w-2xl text-body text-text-secondary">
          Four steps from syllabus to a downloadable paper.
        </p>
        <ol className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {WORKFLOW_STEPS.map(({ number, title, description }) => (
            <li
              key={number}
              className="public-glass-subtle rounded-2xl p-5 transition-all duration-micro hover:-translate-y-0.5 hover:shadow-medium"
            >
              <p className="text-metadata font-bold tracking-wide text-primary">{number}</p>
              <h3 className="mt-2 text-body font-semibold">{title}</h3>
              <p className="mt-1.5 text-small leading-6 text-text-secondary">{description}</p>
            </li>
          ))}
        </ol>

        {/* Closing CTA */}
        <div className="public-glass mt-14 flex flex-col items-start justify-between gap-6 rounded-2xl p-7 sm:flex-row sm:items-center sm:p-8">
          <div className="flex items-start gap-4">
            <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-primary-soft text-primary">
              <FileText className="h-5 w-5" aria-hidden />
            </span>
            <div>
              <h3 className="text-body font-semibold">Ready to build your next paper?</h3>
              <p className="mt-1 text-small text-text-secondary">
                Start from your syllabus and have a validated draft in minutes.
              </p>
            </div>
          </div>
          <ButtonLink href="/create" variant="primary" trailingIcon={<ArrowRight className="h-4 w-4" aria-hidden />}>
            Create Question Paper
          </ButtonLink>
        </div>
      </section>

      <section id="contact" aria-labelledby="contact-heading" className="mx-auto max-w-7xl px-6 pb-16 lg:px-10">
        <div className="public-glass-subtle rounded-2xl p-7 sm:p-8">
          <p className="text-metadata font-medium uppercase tracking-wide text-primary">Contact</p>
          <h2 id="contact-heading" className="mt-2 text-heading font-semibold tracking-tight">Get in touch</h2>
          <p className="mt-2 text-body text-text-secondary">
            For questions, feedback, or collaboration:{' '}
            <a className="font-medium text-primary hover:underline" href="mailto:hemasatyanikhil@gmail.com">
              hemasatyanikhil@gmail.com
            </a>
          </p>
        </div>
      </section>
      <LandingFooter />
    </main>
  );
}
