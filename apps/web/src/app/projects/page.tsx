"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Project } from "@/lib/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { Modal } from "@/components/ui/Modal";
import { 
  FolderKanban, 
  Plus, 
  ExternalLink, 
  Trash2, 
  Globe, 
  Calendar,
  AlertCircle,
  Search
} from "lucide-react";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  // Modal create state
  const [modalOpen, setModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [description, setDescription] = useState("");
  const [sourceCodePath, setSourceCodePath] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const loadProjects = async (searchQuery?: string) => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getProjects(searchQuery);
      setProjects(data);
    } catch (err: any) {
      setError(err.message || "Failed to load projects");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadProjects(search);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      setFormError(null);
      await api.createProject({
        name: name.trim(),
        base_url: baseUrl.trim(),
        description: description.trim() || undefined,
        source_code_path: sourceCodePath.trim() || undefined,
      });
      setModalOpen(false);
      setName("");
      setBaseUrl("");
      setDescription("");
      setSourceCodePath("");
      await loadProjects();
    } catch (err: any) {
      setFormError(err.message || "Failed to create project");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string, projectName: string) => {
    if (!confirm(`Are you sure you want to delete project "${projectName}"? All related test cases and run history will be removed.`)) {
      return;
    }
    try {
      await api.deleteProject(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
    } catch (err: any) {
      alert(`Failed to delete project: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-zinc-100">Projects</h1>
          <p className="mt-1 text-xs text-zinc-400">
            Define target websites, authorized origins, and user testing suites.
          </p>
        </div>

        <button
          onClick={() => {
            setFormError(null);
            setModalOpen(true);
          }}
          className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-zinc-100 hover:bg-white text-xs font-semibold text-zinc-950 transition-all active:scale-[0.98] shadow-sm"
        >
          <Plus className="h-4 w-4" />
          <span>New Project</span>
        </button>
      </div>

      {/* Filter bar */}
      <form onSubmit={handleSearch} className="flex gap-2 max-w-md">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search projects by name..."
            className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-[#232630] bg-[#13151b] text-zinc-200 placeholder-zinc-500 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500/30 transition-colors"
          />
        </div>
        <button
          type="submit"
          className="px-3.5 py-2 rounded-lg border border-[#232630] bg-zinc-900/90 text-xs font-mono text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 transition-colors"
        >
          Search
        </button>
      </form>

      {/* Project Cards Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-44 bg-[#13151b] border border-[#232630] rounded-xl animate-pulse"></div>
          ))}
        </div>
      ) : projects.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((proj) => (
            <div
              key={proj.id}
              className="relative rounded-xl border border-[#232630] bg-[#13151b] p-5 flex flex-col justify-between hover:border-[#2f3442] shadow-subtle transition-colors overflow-hidden group"
            >
              <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.08] to-transparent" />
              
              <div>
                <div className="flex items-start justify-between gap-2">
                  <Link
                    href={`/projects/${proj.id}`}
                    className="font-semibold text-sm text-zinc-100 hover:text-white transition-colors"
                  >
                    {proj.name}
                  </Link>
                  <button
                    onClick={() => handleDelete(proj.id, proj.name)}
                    className="text-zinc-500 hover:text-rose-400 transition-colors p-1"
                    title="Delete Project"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>

                <div className="mt-2 flex items-center gap-1.5 text-xs font-mono text-zinc-400">
                  <Globe className="h-3.5 w-3.5 shrink-0 text-zinc-400" />
                  <span className="truncate">{proj.base_url}</span>
                </div>

                {proj.description && (
                  <p className="mt-2 text-xs text-zinc-400 line-clamp-2 leading-relaxed">
                    {proj.description}
                  </p>
                )}
              </div>

              <div className="mt-5 pt-3 border-t border-[#232630] flex items-center justify-between text-[11px] font-mono text-zinc-400">
                <span className="flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5 text-zinc-400" />
                  {new Date(proj.created_at).toLocaleDateString()}
                </span>
                <Link
                  href={`/projects/${proj.id}`}
                  className="text-zinc-300 hover:text-white font-medium flex items-center gap-1 transition-colors"
                >
                  <span>View Details</span>
                  <ExternalLink className="h-3 w-3" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={FolderKanban}
          title="No projects configured"
          description="Create your first project to define an authorized base website origin for autonomous browser testing."
          actionLabel="Create Project"
          onAction={() => setModalOpen(true)}
        />
      )}

      {/* Create Modal */}
      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Create Testing Project"
        description="Configure target domain and authorized scope for tests."
      >
        <form onSubmit={handleCreate} className="space-y-4">
          {formError && (
            <div className="rounded-lg border border-rose-900/60 bg-rose-950/20 p-3 text-xs font-mono text-rose-300 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
              <span>{formError}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-mono text-zinc-300 mb-1">
              Project Name *
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. My SaaS Production"
              className="w-full rounded-lg border border-[#232630] bg-[#0c0d10] px-3 py-2 text-xs text-zinc-200 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500/30 font-sans"
            />
          </div>

          <div>
            <label className="block text-xs font-mono text-zinc-300 mb-1">
              Base URL * (Authorized Origin)
            </label>
            <input
              type="url"
              required
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://example.com"
              className="w-full rounded-lg border border-[#232630] bg-[#0c0d10] px-3 py-2 text-xs text-zinc-200 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500/30 font-mono"
            />
            <p className="mt-1 text-[11px] text-zinc-400">
              Only journeys operating within this domain will be executed.
            </p>
          </div>

          <div>
            <label className="block text-xs font-mono text-zinc-300 mb-1">
              Local Source Directory Path (Optional)
            </label>
            <input
              type="text"
              value={sourceCodePath}
              onChange={(e) => setSourceCodePath(e.target.value)}
              placeholder="e.g. D:\\code\\my-app or /home/user/project"
              className="w-full rounded-lg border border-[#232630] bg-[#0c0d10] px-3 py-2 text-xs text-zinc-200 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500/30 font-mono"
            />
            <p className="mt-1 text-[11px] text-zinc-400">
              Enables automatic AST route inspection, background dev server launch (Mode B), and UI test synthesis.
            </p>
          </div>

          <div>
            <label className="block text-xs font-mono text-zinc-300 mb-1">
              Description (Optional)
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Primary staging or production environment..."
              className="w-full rounded-lg border border-[#232630] bg-[#0c0d10] px-3 py-2 text-xs text-zinc-200 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500/30 font-sans"
            />
          </div>

          <div className="pt-3 flex justify-end gap-2 border-t border-[#232630]">
            <button
              type="button"
              onClick={() => setModalOpen(false)}
              className="px-3.5 py-1.5 rounded-lg border border-[#232630] bg-zinc-900 text-xs font-medium text-zinc-300 hover:bg-zinc-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-1.5 rounded-lg bg-zinc-100 hover:bg-white text-xs font-semibold text-zinc-950 shadow-sm disabled:opacity-50 active:scale-[0.98] transition-all"
            >
              {submitting ? "Saving..." : "Create Project"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
