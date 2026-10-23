import React, { useState } from "react";
import { StepAction, ActionType } from "@/lib/types";
import { 
  Plus, 
  Trash2, 
  ChevronUp, 
  ChevronDown, 
  Code2, 
  ListTree, 
  CheckCircle, 
  AlertCircle 
} from "lucide-react";

interface StepEditorProps {
  steps: StepAction[];
  onChange: (steps: StepAction[]) => void;
}

const ACTION_TYPES: { value: ActionType; label: string; description: string }[] = [
  { value: "goto", label: "Navigate (goto)", description: "Open a relative path or authorized URL" },
  { value: "click", label: "Click", description: "Click an interactive element" },
  { value: "fill", label: "Fill Input", description: "Type text into a form input or textarea" },
  { value: "select_option", label: "Select Option", description: "Select value in a dropdown" },
  { value: "check", label: "Check Box", description: "Check a checkbox or radio input" },
  { value: "uncheck", label: "Uncheck Box", description: "Uncheck a checkbox" },
  { value: "wait_for_visible", label: "Wait for Visible", description: "Wait until element is rendered" },
  { value: "assert_visible", label: "Assert Visible", description: "Verify element is visible on page" },
  { value: "assert_text", label: "Assert Text", description: "Verify element text content" },
  { value: "assert_url", label: "Assert URL", description: "Verify browser current URL" },
  { value: "screenshot", label: "Screenshot", description: "Capture page evidence checkpoint" },
];

export const StepEditor: React.FC<StepEditorProps> = ({ steps, onChange }) => {
  const [jsonMode, setJsonMode] = useState(false);
  const [rawJson, setRawJson] = useState("");
  const [jsonError, setJsonError] = useState<string | null>(null);

  const toggleJsonMode = () => {
    if (!jsonMode) {
      setRawJson(JSON.stringify(steps, null, 2));
      setJsonError(null);
    } else {
      try {
        const parsed = JSON.parse(rawJson);
        if (!Array.isArray(parsed)) throw new Error("JSON must be an array of step objects");
        onChange(parsed);
        setJsonError(null);
      } catch (err: any) {
        setJsonError(err.message);
        return;
      }
    }
    setJsonMode(!jsonMode);
  };

  const handleRawJsonChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setRawJson(val);
    try {
      const parsed = JSON.parse(val);
      if (Array.isArray(parsed)) {
        onChange(parsed);
        setJsonError(null);
      } else {
        setJsonError("Must be an array of steps");
      }
    } catch (err: any) {
      setJsonError(err.message);
    }
  };

  const addStep = (type: ActionType = "click") => {
    const newStep: StepAction = { action: type };
    if (type === "goto") newStep.url = "/";
    else if (type === "screenshot") newStep.name = "checkpoint";
    else newStep.selector = "";

    onChange([...steps, newStep]);
  };

  const updateStep = (index: number, updates: Partial<StepAction>) => {
    const newSteps = [...steps];
    newSteps[index] = { ...newSteps[index], ...updates };
    onChange(newSteps);
  };

  const removeStep = (index: number) => {
    onChange(steps.filter((_, i) => i !== index));
  };

  const moveStep = (index: number, direction: "up" | "down") => {
    const target = direction === "up" ? index - 1 : index + 1;
    if (target < 0 || target >= steps.length) return;
    const newSteps = [...steps];
    const temp = newSteps[index];
    newSteps[index] = newSteps[target];
    newSteps[target] = temp;
    onChange(newSteps);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
          Journey Steps ({steps.length})
        </div>
        <button
          type="button"
          onClick={toggleJsonMode}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded border border-zinc-700 bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors"
        >
          {jsonMode ? (
            <>
              <ListTree className="h-3.5 w-3.5 text-purple-400" />
              <span>Form View</span>
            </>
          ) : (
            <>
              <Code2 className="h-3.5 w-3.5 text-purple-400" />
              <span>JSON Mode</span>
            </>
          )}
        </button>
      </div>

      {jsonMode ? (
        <div className="space-y-2">
          <textarea
            value={rawJson}
            onChange={handleRawJsonChange}
            rows={14}
            className="w-full rounded-lg border border-zinc-800 bg-[#0c0c0e] p-3 font-mono text-xs text-zinc-200 focus:border-purple-500 focus:outline-none"
          />
          {jsonError ? (
            <div className="flex items-center gap-2 text-xs text-rose-400 font-mono">
              <AlertCircle className="h-3.5 w-3.5" />
              <span>JSON Syntax Error: {jsonError}</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-xs text-emerald-400 font-mono">
              <CheckCircle className="h-3.5 w-3.5" />
              <span>Valid JSON step definition format</span>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {steps.map((step, idx) => (
            <div
              key={idx}
              className="rounded-lg border border-zinc-800 bg-[#111114] p-4 space-y-3 relative group"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="h-5 w-5 rounded bg-zinc-800 border border-zinc-700 text-zinc-400 font-mono text-[10px] flex items-center justify-center font-bold">
                    {idx + 1}
                  </span>
                  <select
                    value={step.action}
                    onChange={(e) => updateStep(idx, { action: e.target.value as ActionType })}
                    className="rounded border border-zinc-700 bg-[#16161a] px-2.5 py-1 text-xs font-mono font-medium text-purple-300 focus:border-purple-500 focus:outline-none"
                  >
                    {ACTION_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    disabled={idx === 0}
                    onClick={() => moveStep(idx, "up")}
                    className="p-1 text-zinc-500 hover:text-zinc-200 disabled:opacity-20"
                  >
                    <ChevronUp className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    disabled={idx === steps.length - 1}
                    onClick={() => moveStep(idx, "down")}
                    className="p-1 text-zinc-500 hover:text-zinc-200 disabled:opacity-20"
                  >
                    <ChevronDown className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => removeStep(idx)}
                    className="p-1 text-zinc-500 hover:text-rose-400 transition-colors ml-1"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* Dynamic fields based on action */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                {step.action === "goto" && (
                  <div className="col-span-2">
                    <label className="block text-[11px] font-mono text-zinc-400 mb-1">Target Path / URL</label>
                    <input
                      type="text"
                      value={step.url || ""}
                      onChange={(e) => updateStep(idx, { url: e.target.value })}
                      placeholder="/dashboard or https://..."
                      className="w-full rounded border border-zinc-800 bg-[#0c0c0e] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-purple-500 focus:outline-none"
                    />
                  </div>
                )}

                {step.action !== "goto" && step.action !== "screenshot" && step.action !== "assert_url" && (
                  <div className={step.action === "fill" || step.action === "select_option" || step.action === "assert_text" ? "col-span-1" : "col-span-2"}>
                    <label className="block text-[11px] font-mono text-zinc-400 mb-1">Target Selector</label>
                    <input
                      type="text"
                      value={step.selector || ""}
                      onChange={(e) => updateStep(idx, { selector: e.target.value })}
                      placeholder="button#submit, input[name='email'], .card"
                      className="w-full rounded border border-zinc-800 bg-[#0c0c0e] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-purple-500 focus:outline-none font-mono"
                    />
                  </div>
                )}

                {step.action === "fill" && (
                  <div>
                    <label className="block text-[11px] font-mono text-zinc-400 mb-1">Input Value</label>
                    <input
                      type="text"
                      value={step.value || ""}
                      onChange={(e) => updateStep(idx, { value: e.target.value })}
                      placeholder="Text to type..."
                      className="w-full rounded border border-zinc-800 bg-[#0c0c0e] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-purple-500 focus:outline-none"
                    />
                  </div>
                )}

                {step.action === "select_option" && (
                  <div>
                    <label className="block text-[11px] font-mono text-zinc-400 mb-1">Option Value</label>
                    <input
                      type="text"
                      value={step.value || ""}
                      onChange={(e) => updateStep(idx, { value: e.target.value })}
                      placeholder="Option value or key"
                      className="w-full rounded border border-zinc-800 bg-[#0c0c0e] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-purple-500 focus:outline-none"
                    />
                  </div>
                )}

                {step.action === "assert_text" && (
                  <div>
                    <label className="block text-[11px] font-mono text-zinc-400 mb-1">Expected Text</label>
                    <input
                      type="text"
                      value={step.expected_text || ""}
                      onChange={(e) => updateStep(idx, { expected_text: e.target.value })}
                      placeholder="Text substring or exact phrase"
                      className="w-full rounded border border-zinc-800 bg-[#0c0c0e] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-purple-500 focus:outline-none"
                    />
                  </div>
                )}

                {step.action === "assert_url" && (
                  <div className="col-span-2">
                    <label className="block text-[11px] font-mono text-zinc-400 mb-1">Expected URL Substring</label>
                    <input
                      type="text"
                      value={step.expected_url || ""}
                      onChange={(e) => updateStep(idx, { expected_url: e.target.value })}
                      placeholder="/dashboard or complete url"
                      className="w-full rounded border border-zinc-800 bg-[#0c0c0e] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-purple-500 focus:outline-none"
                    />
                  </div>
                )}

                {step.action === "screenshot" && (
                  <div className="col-span-2">
                    <label className="block text-[11px] font-mono text-zinc-400 mb-1">Screenshot Label</label>
                    <input
                      type="text"
                      value={step.name || ""}
                      onChange={(e) => updateStep(idx, { name: e.target.value })}
                      placeholder="e.g. checkout_modal_opened"
                      className="w-full rounded border border-zinc-800 bg-[#0c0c0e] px-2.5 py-1.5 text-xs text-zinc-200 focus:border-purple-500 focus:outline-none"
                    />
                  </div>
                )}
              </div>
            </div>
          ))}

          <div className="flex items-center gap-2 pt-2">
            <button
              type="button"
              onClick={() => addStep("click")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-purple-500/30 text-xs font-medium text-purple-300 bg-purple-950/30 hover:bg-purple-900/40 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Add Step</span>
            </button>
            <button
              type="button"
              onClick={() => addStep("screenshot")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-700 text-xs font-medium text-zinc-300 bg-zinc-800 hover:bg-zinc-700 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Add Screenshot Checkpoint</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
