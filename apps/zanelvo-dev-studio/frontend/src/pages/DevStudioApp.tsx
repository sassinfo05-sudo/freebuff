import { useCallback, useEffect, useState } from "react";
import {
  Plus, FolderGit2, Brain, Bot, Github, Settings as SettingsIcon, ListTodo, Circle, LogOut,
} from "lucide-react";
import devstudio from "@/lib/devstudio";
import { toast } from "@/lib/toast";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Badge } from "@/components/ui/Badge";
import TaskView from "./TaskView";
import { RepoBrowser, MemoryPanel, AgentsPanel, GitHubPanel, SettingsPanel } from "./panels";
import { NewProjectDialog, NewTaskDialog } from "./dialogs";

const STATUS_COLOR: Record<string, string> = {
  COMPLETED: "bg-emerald-500", BLOCKED: "bg-amber-500", FAILED: "bg-red-500",
  CANCELLED: "bg-zinc-400", READY_FOR_APPROVAL: "bg-indigo-500",
};

type View = "task" | "repo" | "memory" | "agents" | "github" | "settings";

export default function DevStudioApp() {
  const { logout } = useAuth();
  const [projects, setProjects] = useState<any[]>([]);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [branches, setBranches] = useState<any[]>([]);
  const [branch, setBranch] = useState<string | null>(null);
  const [tasks, setTasks] = useState<any[]>([]);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [view, setView] = useState<View>("task");
  const [newProjectOpen, setNewProjectOpen] = useState(false);
  const [newTaskOpen, setNewTaskOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const refreshProjects = useCallback(async () => {
    try {
      const { data } = await devstudio.listProjects();
      setProjects(data.projects);
      setProjectId((prev) => prev ?? data.projects[0]?.id ?? null);
    } catch {
      /* nothing connected yet */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshProjects();
  }, [refreshProjects]);

  const refreshTasks = useCallback(async (pid: string | null) => {
    if (!pid) return;
    try {
      const { data } = await devstudio.listTasks(pid);
      setTasks(data.tasks);
    } catch {
      /* noop */
    }
  }, []);

  useEffect(() => {
    if (!projectId) return;
    (async () => {
      try {
        const { data } = await devstudio.projectBranches(projectId);
        setBranches(data.branches);
        const project = projects.find((p) => p.id === projectId);
        setBranch(project?.default_branch || data.branches?.[0]?.name || null);
      } catch (e: any) {
        toast.error(e?.response?.data?.detail || "Could not load branches");
      }
      refreshTasks(projectId);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function handleCreateTask(fields: { title: string; request_text: string; mode: string }) {
    if (!projectId || !branch) return;
    try {
      const { data } = await devstudio.createTask({
        project_id: projectId, branch, model_preset: "BALANCED", ...fields,
      });
      toast.success("Task created");
      setNewTaskOpen(false);
      await refreshTasks(projectId);
      setTaskId(data.id);
      setView("task");
      await devstudio.runTask(data.id);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Could not create task");
    }
  }

  const currentProject = projects.find((p) => p.id === projectId);

  return (
    <div className="h-screen w-screen flex bg-[#0B0A16] text-white overflow-hidden">
      {/* LEFT SIDEBAR */}
      <aside className="w-72 flex-shrink-0 flex flex-col border-r border-white/10 bg-[#0F0E1B]">
        <div className="h-14 flex items-center gap-2 px-4 border-b border-white/10">
          <div className="w-6 h-6 rounded-md bg-gradient-to-br from-indigo-500 via-fuchsia-500 to-amber-400" />
          <span className="font-semibold text-sm tracking-tight">Zanelvo Dev Studio</span>
        </div>

        <div className="p-3 space-y-2 border-b border-white/10">
          <div className="flex items-center gap-1.5">
            <Select
              value={projectId ?? ""}
              onChange={(e) => {
                setProjectId(e.target.value || null);
                setTaskId(null);
              }}
              placeholder={loading ? "Loading…" : "Select repository"}
              options={projects.map((p) => ({ value: p.id, label: p.name }))}
            />
            <Button size="icon" variant="ghost" onClick={() => setNewProjectOpen(true)} title="Connect a repository">
              <Plus className="w-4 h-4" />
            </Button>
          </div>
          {projectId && (
            <Select
              value={branch ?? ""}
              onChange={(e) => setBranch(e.target.value || null)}
              placeholder="Select branch"
              options={branches.map((b) => ({ value: b.name, label: b.name }))}
            />
          )}
          <Button className="w-full" disabled={!projectId || !branch} onClick={() => setNewTaskOpen(true)}>
            <Plus className="w-3.5 h-3.5" /> New Task
          </Button>
        </div>

        <div className="px-3 pt-3 pb-1 text-[10px] uppercase tracking-widest text-white/40">Tasks</div>
        <div className="flex-1 overflow-y-auto px-2">
          <div className="space-y-0.5 pb-2">
            {tasks.map((t) => (
              <button
                key={t.id}
                onClick={() => {
                  setTaskId(t.id);
                  setView("task");
                }}
                className={`w-full text-left px-2.5 py-2 rounded-lg text-xs flex items-start gap-2 transition ${
                  taskId === t.id && view === "task" ? "bg-white/10 text-white" : "text-white/60 hover:bg-white/5 hover:text-white"
                }`}
              >
                <Circle className={`w-2 h-2 mt-1 flex-shrink-0 rounded-full ${STATUS_COLOR[t.status] || "bg-sky-500"}`} fill="currentColor" />
                <span className="flex-1 min-w-0">
                  <div className="truncate">{t.title}</div>
                  <div className="text-[10px] text-white/40 mt-0.5">{t.status}</div>
                </span>
              </button>
            ))}
            {!tasks.length && <div className="text-xs text-white/30 px-2 py-4">No tasks yet.</div>}
          </div>
        </div>

        <nav className="border-t border-white/10 p-2 space-y-0.5">
          {(
            [
              ["repo", FolderGit2, "Repository"],
              ["memory", Brain, "Project Memory"],
              ["agents", Bot, "Agents"],
              ["github", Github, "GitHub"],
              ["settings", SettingsIcon, "Settings"],
            ] as const
          ).map(([key, Icon, label]) => (
            <button
              key={key}
              onClick={() => setView(key)}
              className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs transition ${
                view === key ? "bg-white/10 text-white" : "text-white/50 hover:bg-white/5 hover:text-white"
              }`}
            >
              <Icon className="w-3.5 h-3.5" /> {label}
            </button>
          ))}
        </nav>
        <div className="p-3 border-t border-white/10 text-[11px] text-white/40 flex items-center justify-between">
          {currentProject?.last_indexed_commit_sha ? (
            <Badge className="border-white/20 text-white/50">{currentProject.last_indexed_commit_sha.slice(0, 7)}</Badge>
          ) : (
            <span />
          )}
          <button onClick={logout} className="flex items-center gap-1 hover:text-white">
            <LogOut className="w-3.5 h-3.5" /> Sign out
          </button>
        </div>
      </aside>

      {/* CENTER + RIGHT */}
      <div className="flex-1 min-w-0 flex flex-col">
        {view === "task" && taskId && <TaskView taskId={taskId} onTaskChanged={() => refreshTasks(projectId)} />}
        {view === "task" && !taskId && (
          <div className="flex-1 grid place-items-center text-white/40 text-sm">
            <div className="text-center">
              <ListTodo className="w-8 h-8 mx-auto mb-2 opacity-40" />
              Select a task, or create a new one.
            </div>
          </div>
        )}
        {view === "repo" && projectId && branch && <RepoBrowser projectId={projectId} branch={branch} />}
        {view === "memory" && projectId && <MemoryPanel projectId={projectId} />}
        {view === "agents" && <AgentsPanel />}
        {view === "github" && <GitHubPanel />}
        {view === "settings" && <SettingsPanel />}
      </div>

      <NewProjectDialog
        open={newProjectOpen}
        onOpenChange={setNewProjectOpen}
        onCreated={() => {
          setNewProjectOpen(false);
          refreshProjects();
        }}
      />
      <NewTaskDialog open={newTaskOpen} onOpenChange={setNewTaskOpen} onSubmit={handleCreateTask} />
    </div>
  );
}
