import { useEffect, useState } from "react";
import { RotateCcw, Save, Play, Square, Link2, Camera } from "lucide-react";
import devstudio from "@/lib/devstudio";
import { toast } from "@/lib/toast";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";

// --- Checkpoints ---------------------------------------------------------------------------

export function CheckpointsPanel({ taskId }: { taskId: string }) {
  const [checkpoints, setCheckpoints] = useState<any[]>([]);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const { data } = await devstudio.checkpoints(taskId);
    setCheckpoints(data.checkpoints);
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId]);

  async function create() {
    if (!label.trim()) return;
    setBusy(true);
    try {
      await devstudio.createCheckpoint(taskId, label.trim());
      toast.success("Checkpoint created");
      setLabel("");
      load();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Could not create checkpoint");
    } finally {
      setBusy(false);
    }
  }

  async function restore(id: string, checkpointLabel: string) {
    if (!window.confirm(`Restore "${checkpointLabel}"? This discards uncommitted changes made after it.`)) return;
    try {
      await devstudio.restoreCheckpoint(taskId, id, true);
      toast.success("Restored");
      load();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Restore failed");
    }
  }

  return (
    <div className="h-full overflow-y-auto p-3">
      <div className="flex gap-1.5 mb-3">
        <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Checkpoint label…"
          onKeyDown={(e) => e.key === "Enter" && create()} />
        <Button size="sm" disabled={busy || !label.trim()} onClick={create}>
          <Save className="w-3.5 h-3.5" />
        </Button>
      </div>
      {checkpoints.map((c) => (
        <div key={c.id} className="rounded-lg border border-white/10 bg-white/5 p-2.5 mb-2 text-xs">
          <div className="flex items-center justify-between gap-2">
            <span className="text-white/85 font-medium truncate">{c.label}</span>
            <Button size="sm" variant="outline" onClick={() => restore(c.id, c.label)}>
              <RotateCcw className="w-3 h-3" /> Restore
            </Button>
          </div>
          <div className="text-white/40 mt-1 font-mono">{c.commit_sha?.slice(0, 10)} · {c.branch}</div>
        </div>
      ))}
      {!checkpoints.length && <div className="text-xs text-white/40">No checkpoints yet.</div>}
    </div>
  );
}

// --- Preview -----------------------------------------------------------------------------

export function PreviewPanel({ taskId }: { taskId: string }) {
  const [state, setState] = useState<any>(null);
  const [externalUrl, setExternalUrl] = useState("");
  const [busy, setBusy] = useState(false);

  async function startLive() {
    setBusy(true);
    try {
      const { data } = await devstudio.previewLiveLocal(taskId);
      setState(data);
      if (data.status !== "running") toast.error(data.detail || "Preview unavailable");
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Could not start preview");
    } finally {
      setBusy(false);
    }
  }

  async function stopLive() {
    await devstudio.previewStop(taskId);
    setState(null);
  }

  async function attachExternal() {
    if (!externalUrl.trim()) return;
    const { data } = await devstudio.previewExternal(taskId, externalUrl.trim());
    setState(data);
  }

  async function loadScreenshotMode() {
    const { data } = await devstudio.previewScreenshot(taskId);
    setState(data);
  }

  return (
    <div className="h-full overflow-y-auto p-3 space-y-3">
      <div className="flex gap-1.5">
        <Button size="sm" variant="outline" disabled={busy} onClick={startLive}>
          <Play className="w-3.5 h-3.5" /> Live local
        </Button>
        <Button size="sm" variant="outline" onClick={stopLive}>
          <Square className="w-3.5 h-3.5" /> Stop
        </Button>
        <Button size="sm" variant="outline" onClick={loadScreenshotMode}>
          <Camera className="w-3.5 h-3.5" /> Screenshot
        </Button>
      </div>
      <div className="flex gap-1.5">
        <Input value={externalUrl} onChange={(e) => setExternalUrl(e.target.value)}
          placeholder="https://your-preview-env…" />
        <Button size="sm" variant="outline" onClick={attachExternal}>
          <Link2 className="w-3.5 h-3.5" />
        </Button>
      </div>
      {state && (
        <div className="rounded-lg border border-white/10 bg-white/5 p-3 text-xs space-y-1">
          <div className="flex items-center gap-2">
            <Badge className="border-white/20 text-white/60">{state.mode}</Badge>
            <Badge className={state.status === "running" || state.status === "attached"
              ? "border-emerald-500/40 text-emerald-300" : "border-amber-500/40 text-amber-300"}>
              {state.status}
            </Badge>
          </div>
          {state.url && (
            <a href={state.url} target="_blank" rel="noreferrer" className="text-indigo-300 underline block break-all">
              {state.url}
            </a>
          )}
          {state.detail && <div className="text-white/50">{state.detail}</div>}
        </div>
      )}
      {!state && <div className="text-xs text-white/40">No preview started yet.</div>}
    </div>
  );
}
