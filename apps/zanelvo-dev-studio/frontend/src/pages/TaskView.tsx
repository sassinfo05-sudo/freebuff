import { useCallback, useEffect, useRef, useState } from "react";
import {
  Play, Square, GitCommit, UploadCloud, Send, Bot, Wrench, FileText, TestTube2,
  ScrollText, FlagTriangleRight,
} from "lucide-react";
import devstudio from "@/lib/devstudio";
import { toast } from "@/lib/toast";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Textarea";
import { Badge } from "@/components/ui/Badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/Tabs";

const AGENT_ICON: Record<string, any> = {
  supervisor: Bot, repository_analyst: FileText, planner: FlagTriangleRight,
  design: Wrench, frontend: Wrench, backend: Wrench, integration: Wrench, qa: TestTube2,
  reviewer: FileText, git: GitCommit,
};

export default function TaskView({ taskId, onTaskChanged }: { taskId: string; onTaskChanged?: () => void }) {
  const [task, setTask] = useState<any>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [message, setMessage] = useState("");
  const [diff, setDiff] = useState<any>(null);
  const [plan, setPlan] = useState<any[]>([]);
  const [tests, setTests] = useState<any[]>([]);
  const [screenshots, setScreenshots] = useState<any[]>([]);
  const [files, setFiles] = useState<any[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState("");
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const refreshAll = useCallback(async () => {
    const [t, d, p, ts, sc] = await Promise.all([
      devstudio.getTask(taskId), devstudio.diff(taskId), devstudio.plan(taskId),
      devstudio.tests(taskId), devstudio.screenshots(taskId),
    ]);
    setTask(t.data);
    setDiff(d.data);
    setPlan(p.data.plan);
    setTests(ts.data.runs);
    setScreenshots(sc.data.screenshots);
    onTaskChanged?.();
  }, [taskId, onTaskChanged]);

  useEffect(() => {
    setEvents([]);
    refreshAll();
    devstudio
      .filesTree(taskId)
      .then(({ data }) => setFiles(data.entries))
      .catch(() => setFiles([]));

    const es = new EventSource(devstudio.eventsUrl(taskId), { withCredentials: true });
    const onAny = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        setEvents((prev) => [...prev, { ...data, kind: e.type }]);
        if (["state_change", "plan_created", "plan_item_status", "agent_finished"].includes(e.type)) refreshAll();
      } catch {
        /* ignore malformed event */
      }
    };
    const kinds = [
      "task_created", "state_change", "message", "agent_started", "agent_finished", "plan_created",
      "plan_item_status", "supervisor_note", "stop_requested",
    ];
    kinds.forEach((k) => es.addEventListener(k, onAny as EventListener));
    return () => es.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [events]);

  async function send() {
    if (!message.trim()) return;
    await devstudio.postMessage(taskId, message.trim());
    setMessage("");
  }

  async function run() {
    await devstudio.runTask(taskId);
    toast.success("Supervisor started");
    refreshAll();
  }
  async function stop() {
    await devstudio.stopTask(taskId);
    toast.info("Stop requested");
  }
  async function commit() {
    const msg = window.prompt("Commit message", task?.title || "Dev Studio changes");
    if (!msg) return;
    try {
      await devstudio.commit(taskId, msg);
      toast.success("Committed");
      refreshAll();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Commit failed");
    }
  }
  async function push() {
    try {
      await devstudio.push(taskId);
      toast.success("Pushed to GitHub");
      refreshAll();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Push failed");
    }
  }
  async function openFile(path: string) {
    setSelectedFile(path);
    const { data } = await devstudio.fileRead(taskId, path);
    setFileContent(data.content);
  }
  async function runTests() {
    try {
      const { data } = await devstudio.runTests(taskId);
      setTests(data.runs);
      toast.success("Tests ran");
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Could not run tests");
    }
  }

  if (!task) return <div className="flex-1 grid place-items-center text-white/40 text-sm">Loading…</div>;

  return (
    <div className="flex-1 flex min-h-0">
      {/* CENTER */}
      <div className="flex-1 min-w-0 flex flex-col border-r border-white/10">
        <div className="h-14 flex items-center gap-3 px-4 border-b border-white/10 flex-shrink-0">
          <div className="min-w-0">
            <div className="text-sm font-medium truncate">{task.title}</div>
            <div className="text-[11px] text-white/40 flex items-center gap-2">
              <Badge className="border-white/20 text-white/60">{task.status}</Badge>
              <span>{task.mode}</span>
              <span>·</span>
              <span>{task.branch}</span>
              {diff && (
                <>
                  <span>·</span>
                  <span>{diff.changed_file_count} files changed</span>
                </>
              )}
            </div>
          </div>
          <div className="ml-auto flex items-center gap-1.5">
            <Button size="sm" variant="secondary" onClick={run}>
              <Play className="w-3.5 h-3.5" /> Run
            </Button>
            <Button size="sm" variant="outline" onClick={stop}>
              <Square className="w-3.5 h-3.5" /> Stop
            </Button>
            <Button size="sm" variant="outline" onClick={commit} disabled={task.status !== "READY_FOR_APPROVAL"}>
              <GitCommit className="w-3.5 h-3.5" /> Commit
            </Button>
            <Button size="sm" onClick={push} disabled={task.status !== "COMMITTING" && task.status !== "READY_FOR_APPROVAL"}>
              <UploadCloud className="w-3.5 h-3.5" /> Push
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto" ref={scrollRef}>
          <div className="p-4 space-y-2">
            {events.map((e, i) => (
              <ActivityRow key={i} event={e} />
            ))}
            {task.blocked_reason && (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
                <strong>Blocked:</strong> {task.blocked_reason}
              </div>
            )}
          </div>
        </div>

        <div className="p-3 border-t border-white/10 flex gap-2 flex-shrink-0">
          <Textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={1}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder='Message the Supervisor — e.g. "Continue.", "Only change frontend.", "Run tests again."'
            className="min-h-9"
          />
          <Button size="icon" onClick={send}>
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* RIGHT INSPECTOR */}
      <Tabs defaultValue="plan" className="w-[420px] flex-shrink-0 flex flex-col">
        <TabsList className="mx-2 mt-2">
          <TabsTrigger value="plan">plan</TabsTrigger>
          <TabsTrigger value="files">files</TabsTrigger>
          <TabsTrigger value="diff">diff</TabsTrigger>
          <TabsTrigger value="tests">tests</TabsTrigger>
          <TabsTrigger value="screenshots">screenshots</TabsTrigger>
        </TabsList>

        <TabsContent value="plan" className="flex-1 min-h-0 overflow-y-auto p-3">
          {plan.map((p) => (
            <div key={p.id} className="rounded-lg border border-white/10 bg-white/5 p-2.5 mb-2 text-xs">
              <div className="flex items-center gap-1.5">
                <Badge
                  className={`border-white/20 ${p.status === "VERIFIED" ? "text-emerald-300" : p.status === "FAILED" ? "text-red-300" : "text-white/60"}`}
                >
                  {p.status}
                </Badge>
                <span className="text-white/40">{p.assigned_agent}</span>
              </div>
              <div className="text-white/85 font-medium mt-1">{p.title}</div>
              <div className="text-white/50 mt-0.5">{p.description}</div>
            </div>
          ))}
          {!plan.length && <div className="text-xs text-white/40 p-1">No plan yet — run the task to generate one.</div>}
        </TabsContent>

        <TabsContent value="files" className="flex-1 min-h-0 flex">
          <div className="w-1/2 border-r border-white/10 overflow-y-auto">
            {files
              .filter((f) => !f.is_dir)
              .map((f) => (
                <button
                  key={f.path}
                  onClick={() => openFile(f.path)}
                  className={`w-full text-left px-2 py-1 text-[11px] rounded hover:bg-white/5 truncate ${
                    selectedFile === f.path ? "bg-white/10 text-white" : "text-white/60"
                  }`}
                >
                  {f.path}
                </button>
              ))}
          </div>
          <div className="w-1/2 overflow-y-auto">
            <pre className="p-2 text-[10px] text-white/70 whitespace-pre-wrap font-mono">{fileContent || "Select a file"}</pre>
          </div>
        </TabsContent>

        <TabsContent value="diff" className="flex-1 min-h-0 overflow-y-auto p-3">
          <div className="text-xs text-white/50 mb-2">
            +{diff?.total_additions || 0} / -{diff?.total_deletions || 0} across {diff?.changed_file_count || 0} files
          </div>
          {(diff?.files || []).map((f: any) => (
            <div key={f.path} className="text-xs mb-1.5 flex items-center gap-2">
              <Badge className="border-white/20 text-white/50">{f.change_type}</Badge>
              <span className="text-white/70 truncate">{f.path}</span>
              <span className="ml-auto text-emerald-400">+{f.additions}</span>
              <span className="text-red-400">-{f.deletions}</span>
            </div>
          ))}
          {!diff?.files?.length && <div className="text-xs text-white/40">No changes yet.</div>}
        </TabsContent>

        <TabsContent value="tests" className="flex-1 min-h-0 overflow-y-auto p-3">
          <Button size="sm" variant="outline" className="mb-2" onClick={runTests}>
            <TestTube2 className="w-3.5 h-3.5" /> Run tests now
          </Button>
          {tests.map((r) => (
            <div key={r.id} className="rounded-lg border border-white/10 bg-white/5 p-2.5 mb-2 text-xs">
              <div className="flex items-center gap-1.5">
                <Badge className={`border-white/20 ${r.status === "passed" ? "text-emerald-300" : "text-red-300"}`}>{r.status}</Badge>
                <span className="text-white/50">{r.test_type}</span>
                <span className="text-white/30 ml-auto">{r.duration_ms}ms</span>
              </div>
              <div className="text-white/70 font-mono mt-1 truncate">{r.command}</div>
              {r.status !== "passed" && r.stderr_tail && (
                <pre className="text-red-300/80 mt-1 whitespace-pre-wrap max-h-28 overflow-auto">{r.stderr_tail}</pre>
              )}
            </div>
          ))}
          {!tests.length && <div className="text-xs text-white/40">No test runs yet.</div>}
        </TabsContent>

        <TabsContent value="screenshots" className="flex-1 min-h-0 overflow-y-auto p-3">
          {screenshots.map((s) => (
            <div key={s.id} className="text-xs text-white/50">
              {s.label} — {s.path.split("/").pop()}
            </div>
          ))}
          {!screenshots.length && <div className="text-xs text-white/40">No browser QA screenshots yet.</div>}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ActivityRow({ event }: { event: any }) {
  const kind = event.kind;
  if (kind === "message") {
    return (
      <div
        className={`text-xs rounded-lg p-2.5 max-w-[85%] ${
          event.payload.role === "user" ? "bg-indigo-500/20 ml-auto text-indigo-100" : "bg-white/5 text-white/80"
        }`}
      >
        {event.payload.text}
      </div>
    );
  }
  if (kind === "agent_started" || kind === "agent_finished") {
    const Icon = AGENT_ICON[event.payload.role] || Bot;
    return (
      <div className="flex items-center gap-2 text-[11px] text-white/50">
        <Icon className="w-3.5 h-3.5 flex-shrink-0" />
        <span className="capitalize">{(event.payload.role || "").replace(/_/g, " ")}</span>
        <span>{event.payload.action || event.payload.status}</span>
        {event.payload.model && (
          <span className="text-white/30">
            · {event.payload.provider}/{event.payload.model}
          </span>
        )}
      </div>
    );
  }
  if (kind === "state_change") {
    return (
      <div className="flex items-center gap-2 text-[11px] text-white/40">
        <ScrollText className="w-3.5 h-3.5" /> {event.payload.from} → <strong className="text-white/60">{event.payload.to}</strong>
      </div>
    );
  }
  if (kind === "plan_created") {
    return (
      <div className="text-[11px] text-white/40 flex items-center gap-2">
        <FlagTriangleRight className="w-3.5 h-3.5" /> Plan created ({event.payload.item_count} items)
      </div>
    );
  }
  if (kind === "plan_item_status") {
    return (
      <div className="text-[11px] text-white/40">
        Plan item "{event.payload.title}": {event.payload.from} → {event.payload.to}
      </div>
    );
  }
  return <div className="text-[11px] text-white/30">{event.payload?.note || kind}</div>;
}
