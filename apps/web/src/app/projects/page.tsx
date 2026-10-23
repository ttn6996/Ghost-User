"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Project } from "@/lib/types";
import { Modal } from "@/components/ui/Modal";
import { EmptyState } from "@/components/ui/EmptyState";
import { 
  FolderKanban, 
  Plus, 
  Search, 
  ExternalLink, 
  Trash2, 
  Globe, 
  Calendar,
  AlertCircle
} from "lucide-react";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Form states
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [description, setDescription] = useState("");

  const loadProjects = async (query = "") => {
    try {
      setLoading(true);
      const data = await api.getProjects(query);
      setProjects(data);
    } catch (err: any) {
      console.error(err);
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
    setFormError(null);
    try {
      setSubmitting(true);
      await api.createProject({
        name,
        base_url: baseUrl,
        description: description || undefined,
      });
      setModalOpen(false);
      setName("");
      setBaseUrl("");
      setDescription("");
      await loadProjects();
    } catch (err: any) {
      setFormError(err.message || "Failed to create project");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Are you sure you want to delete project "${name}" and all its test cases?`)) {
      return;
    }
    try {
      await api.deleteProject(id);
      setProjects(projects.filter((p) => p.id !== id));
    } catch (err: any) {
      alert(`Could not delete project: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Projects</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Define target websites, authorized origins, and user testing suites.
          </p>
        </div>

        <button
          onClick={() => {
            setFormError(null);
            setModalOpen(true);
          }}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-xs font-medium text-white transition-colors shadow-sm"
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
            className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-zinc-800 bg-[#0f0f12] text-zinc-200 placeholder-zinc-500 focus:border-purple-500 focus:outline-none"
          />
        </div>
        <button
          type="submit"
          className="px-3.5 py-2 rounded-lg border border-zinc-800 bg-zinc-900 text-xs font-mono text-zinc-300 hover:bg-zinc-800 transition-colors"
        >
          Search
        </button>
      </form>

      {/* Project Cards Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-44 bg-zinc-900/40 border border-zinc-800 rounded-xl animate-pulse"></div>
          ))}
        </div>
      ) : projects.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((proj) => (
            <div
              key={proj.id}
              className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-5 flex flex-col justify-between hover:border-zinc-700 transition-colors"
            >
              <div>
                <div className="flex items-start justify-between gap-2">
                  <Link
                    href={`/projects/${proj.id}`}
                    className="font-semibold text-base text-zinc-100 hover:text-purple-400 transition-colors"
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

                <div className="mt-2 flex items-center gap-1.5 text-xs font-mono text-purple-400">
                  <Globe className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{proj.base_url}</span>
                </div>

                {proj.description && (
                  <p className="mt-2 text-xs text-zinc-400 line-clamp-2">
                    {proj.description}
                  </p>
                )}
              </div>

              <div className="mt-5 pt-3 border-t border-zinc-800/80 flex items-center justify-between text-[11px] font-mono text-zinc-400">
                <span className="flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5 text-zinc-400" />
                  {new Date(proj.created_at).toLocaleDateString()}
                </span>
                <Link
                  href={`/projects/${proj.id}`}
                  className="text-purple-400 hover:text-purple-300 font-medium flex items-center gap-1"
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
              className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 text-xs text-zinc-200 focus:border-purple-500 focus:outline-none"
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
              className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 text-xs text-zinc-200 focus:border-purple-500 focus:outline-none font-mono"
            />
            <p className="mt-1 text-[11px] text-zinc-400">
              Only journeys operating within this domain will be executed.
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
              className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 text-xs text-zinc-200 focus:border-purple-500 focus:outline-none"
            />
          </div>

          <div className="pt-3 flex justify-end gap-2 border-t border-zinc-800">
            <button
              type="button"
              onClick={() => setModalOpen(false)}
              className="px-3.5 py-1.5 rounded-lg border border-zinc-800 bg-zinc-900 text-xs font-medium text-zinc-300 hover:bg-zinc-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-xs font-medium text-white shadow-sm disabled:opacity-50"
            >
              {submitting ? "Saving..." : "Create Project"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
