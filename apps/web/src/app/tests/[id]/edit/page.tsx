"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { TestCase, StepAction } from "@/lib/types";
import { StepEditor } from "@/components/step-editor/StepEditor";
import { ArrowLeft, Save, CheckCircle2, AlertCircle } from "lucide-react";

export default function EditTestPage() {
  const params = useParams();
  const router = useRouter();
  const testId = params.id as string;

  const [testCase, setTestCase] = useState<TestCase | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [steps, setSteps] = useState<StepAction[]>([]);

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [validationState, setValidationState] = useState<{
    tested: boolean;
    valid: boolean;
    errors: string[];
  }>({ tested: false, valid: false, errors: [] });

  useEffect(() => {
    if (testId) {
      api.getTestCase(testId)
        .then((tc) => {
          setTestCase(tc);
          setName(tc.name);
          setDescription(tc.description || "");
          setEnabled(tc.enabled);
          setSteps(tc.definition_json?.steps || []);
        })
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false));
    }
  }, [testId]);

  const handleValidate = async () => {
    try {
      const def = { name, steps };
      const res = await api.validateTestDefinition(def);
      setValidationState({ tested: true, valid: res.valid, errors: res.errors });
    } catch (err: any) {
      setValidationState({ tested: true, valid: false, errors: [err.message] });
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Test name is required");
      return;
    }

    try {
      setSubmitting(true);
      setError(null);

      const payload = {
        name,
        description: description || undefined,
        enabled,
        definition_json: {
          name,
          description: description || undefined,
          steps,
        },
      };

      await api.updateTestCase(testId, payload);
      router.push(`/projects/${testCase?.project_id}`);
    } catch (err: any) {
      setError(err.message || "Failed to update test case");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-xs font-mono text-zinc-400">Loading test case...</div>;
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <Link
          href={`/projects/${testCase?.project_id || ""}`}
          className="inline-flex items-center gap-1.5 text-xs font-mono text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Project</span>
        </Link>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">Edit Test Case</h1>
          <p className="mt-1 text-sm text-zinc-400">Modify steps, assertions, or target selectors.</p>
        </div>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {error && (
          <div className="rounded-xl border border-rose-900/60 bg-rose-950/20 p-4 text-xs font-mono text-rose-300 flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-5 space-y-4">
          <div>
            <label className="block text-xs font-mono text-zinc-300 mb-1">Test Case Name *</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 text-xs text-zinc-200 focus:border-purple-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-mono text-zinc-300 mb-1">Description</label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded-lg border border-zinc-800 bg-[#0a0a0c] px-3 py-2 text-xs text-zinc-200 focus:border-purple-500 focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="enabled-edit"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="rounded border-zinc-700 bg-zinc-900 text-purple-600 focus:ring-0"
            />
            <label htmlFor="enabled-edit" className="text-xs text-zinc-300 font-mono">
              Enabled
            </label>
          </div>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-[#0f0f12] p-5">
          <StepEditor steps={steps} onChange={setSteps} />
        </div>

        {validationState.tested && (
          <div
            className={`rounded-xl border p-4 text-xs font-mono flex items-start gap-2.5 ${
              validationState.valid
                ? "border-emerald-900/60 bg-emerald-950/20 text-emerald-300"
                : "border-rose-900/60 bg-rose-950/20 text-rose-300"
            }`}
          >
            {validationState.valid ? (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400 mt-0.5" />
            ) : (
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-400 mt-0.5" />
            )}
            <div>
              <div className="font-semibold">
                {validationState.valid ? "Validation Passed" : "Validation Failed:"}
              </div>
              {validationState.errors.map((err, i) => (
                <div key={i} className="mt-1">
                  - {err}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-center justify-between pt-2">
          <button
            type="button"
            onClick={handleValidate}
            className="px-4 py-2 rounded-lg border border-zinc-700 bg-zinc-800 text-xs font-medium text-zinc-200 hover:bg-zinc-700"
          >
            Validate Steps Schema
          </button>

          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center gap-2 px-5 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-xs font-medium text-white transition-colors shadow-sm disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            <span>{submitting ? "Saving Changes..." : "Save Changes"}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
