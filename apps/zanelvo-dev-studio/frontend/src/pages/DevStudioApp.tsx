import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Plus, FolderGit2, Brain, Bot, Github, Settings as SettingsIcon, MessageSquarePlus, LogOut,
  Sparkles, Pencil, Trash2,
} from "lucide-react";
import devstudio from "@/lib/devstudio";
import { toast } from "@/lib/toast";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { SkeletonRows } from "@/components/ui/Skeleton";
import { PromptDialog } from "@/components/ui/PromptDialog";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { CommandPalette, type CommandItem } from "@/components/ui/CommandPalette";
import { statusDotClass, formatStatusLabel, isActiveStatus } from "@/lib/status";
import type { Project, Branch, Task } from "@/lib/types";
import TaskView from "./TaskView";
import { RepoBrowser, MemoryPanel, AgentsPanel, GitHubPanel, SettingsPanel } from "./panels";
import { NewProjectDialog } from "./dialogs";

type View = "task" | "repo" | "memory" | "agents" | "github" | "settings";

const NAV_ITEMS = [
  ["repo", FolderGit2, "Repository"],
  ["memory", Brain, "Project Memory"],
  ["agents", Bot, "Agents"],
  ["github", Github, "GitHub"],
  ["settings", SettingsIcon, "Settings"],
] as const;

export default function DevStudioApp() {
  const { logout } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [branch, setBranch] = useState<string | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [view, setView] = useState<View>("task");
  const [newProjectOpen, setNewProjectOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<{ id: string; title: string } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null);
  const [creatingChat, setCreatingChat] = useState(false);
  const [loading, setLoading] = useState(true);
  const [paletteOpen, setPaletteOpen] = useState(false);

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
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Could not load tasks");
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

  async function handleNewChat() {
    if (!projectId || !branch) return;
    setCreatingChat(true);
    try {
      // Blank chat, ChatGPT/Claude-style: no upfront form. The Supervisor kicks off and the
      // title auto-generates the moment you send your first message in TaskView.
      const { data } = await devstudio.createTask({ project_id: projectId, branch, mode: "feature" });
      await refreshTasks(projectId);
      setTaskId(data.id);
      setView("task");
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Could not start a new chat");
    } finally {
      setCreatingChat(false);
    }
  }

  async function handleRename(newTitle: string) {
    if (!renameTarget) return;
    try {
      await devstudio.renameTask(renameTarget.id, newTitle);
      await refreshTasks(projectId);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Could not rename chat");
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await devstudio.deleteTask(deleteTarget.id);
      if (taskId === deleteTarget.id) setTaskId(null);
      await refreshTasks(projectId);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Could not delete chat");
    }
  }

  const currentProject = projects.find((p) => p.id === projectId);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const commandItems = useMemo<CommandItem[]>(() => {
    const chatItems: CommandItem[] = tasks.map((t) => ({
      id: `task-${t.id}`,
      label: t.title,
      sublabel: formatStatusLabel(t.status),
      icon: MessageSquarePlus,
      onSelect: () => {
        setTaskId(t.id);
        setView("task");
      },
    }));
    const navItems: CommandItem[] = NAV_ITEMS.map(([key, Icon, label]) => ({
      id: `nav-${key}`,
      label,
      sublabel: "Panel",
      icon: Icon,
      onSelect: () => setView(key),
    }));
    const actionItems: CommandItem[] = [];
    if (projectId && branch) {
      actionItems.push({
        id: "action-new-chat",
        label: "New Chat",
        sublabel: "Start a fresh chat in this repository",
        icon: MessageSquarePlus,
        onSelect: handleNewChat,
      });
    }
    return [...actionItems, ...chatItems, ...navItems];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tasks, projectId, branch]);

  return (
    <div className="h-screen w-screen flex bg-surface-0 text-white overflow-hidden">
      {/* LEFT SIDEBAR */}
      <aside className="w-72 flex-shrink-0 flex flex-col border-r border-white/10 bg-surface-1">
        <div className="h-14 flex items-center gap-2.5 px-4 border-b border-white/10 flex-shrink-0">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 via-fuchsia-500 to-amber-400 shadow-glow flex items-center justify-center flex-shrink-0">
            <Sparkles className="w-3.5 h-3.5 text-white" strokeWidth={2.25} />
          </div>
          <span className="font-semibold text-sm tracking-tight flex-1 min-w-0 truncate">Zanelvo Dev Studio</span>
          <button
            onClick={() => setPaletteOpen(true)}
            title="Quick nav (⌘K / Ctrl+K)"
            className="flex-shrink-0 text-[10px] text-white/35 border border-white/15 rounded px-1.5 py-0.5 hover:text-white/70 hover:border-white/30 transition-colors"
          >
            ⌘K
          </button>
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
          <Button className="w-full" disabled={!projectId || !branch} loading={creatingChat} onClick={handleNewChat}>
            <MessageSquarePlus className="w-3.5 h-3.5" /> New Chat
          </Button>
        </div>

        <div className="px-3.5 pt-3 pb-1.5 text-[10px] font-medium uppercase tracking-widest text-white/35 flex-shrink-0">
          Chats
        </div>
        <div className="flex-1 overflow-y-auto px-2 min-h-0">
          {loading && <SkeletonRows count={3} className="px-1" />}
          {!loading && (
            <div className="space-y-0.5 pb-2">
              {tasks.map((t, i) => {
                const active = taskId === t.id && view === "task";
                return (
                  <div
                    key={t.id}
                    style={{ animationDelay: `${Math.min(i, 8) * 25}ms` }}
                    className={`group w-full flex items-start gap-2 pl-2.5 pr-1 py-2 rounded-lg text-xs transition-colors border-l-2 cursor-pointer animate-fade-up ${
                      active
                        ? "bg-white/[0.08] text-white border-indigo-400"
                        : "text-white/60 hover:bg-white/[0.04] hover:text-white/90 border-transparent"
                    }`}
                    onClick={() => {
                      setTaskId(t.id);
                      setView("task");
                    }}
                  >
                    <span
                      className={`w-1.5 h-1.5 mt-1.5 flex-shrink-0 rounded-full ${statusDotClass(t.status)} ${
                        isActiveStatus(t.status) ? "animate-pulse-ring" : ""
                      }`}
                    />
                    <span className="flex-1 min-w-0">
                      <div className="truncate leading-snug">{t.title}</div>
                      <div className="text-[10px] text-white/35 mt-0.5 capitalize">{formatStatusLabel(t.status)}</div>
                    </span>
                    <span className="flex-shrink-0 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setRenameTarget({ id: t.id, title: t.title });
                        }}
                        className="p-1 rounded hover:bg-white/10 hover:text-white"
                        title="Rename"
                      >
                        <Pencil className="w-3 h-3" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteTarget({ id: t.id, title: t.title });
                        }}
                        className="p-1 rounded hover:bg-red-500/20 hover:text-red-300"
                        title="Delete"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </span>
                  </div>
                );
              })}
              {!tasks.length && projectId && (
                <EmptyState compact icon={MessageSquarePlus} title="No chats yet" description="Start one to get going." />
              )}
            </div>
          )}
        </div>

        <nav className="border-t border-white/10 p-2 space-y-0.5 flex-shrink-0">
          {NAV_ITEMS.map(([key, Icon, label]) => (
            <button
              key={key}
              onClick={() => setView(key)}
              className={`w-full flex items-center gap-2 pl-2.5 pr-2 py-1.5 rounded-lg text-xs transition-all duration-150 border-l-2 active:scale-[0.98] ${
                view === key
                  ? "bg-white/[0.08] text-white border-indigo-400"
                  : "text-white/50 hover:bg-white/[0.04] hover:text-white/90 border-transparent"
              }`}
            >
              <Icon className="w-3.5 h-3.5" /> {label}
            </button>
          ))}
        </nav>
        <div className="p-3 border-t border-white/10 text-[11px] text-white/40 flex items-center justify-between flex-shrink-0">
          {currentProject?.last_indexed_commit_sha ? (
            <Badge className="border-white/15 text-white/50 font-mono">
              {currentProject.last_indexed_commit_sha.slice(0, 7)}
            </Badge>
          ) : (
            <span />
          )}
          <button onClick={logout} className="flex items-center gap-1 hover:text-white transition-colors">
            <LogOut className="w-3.5 h-3.5" /> Sign out
          </button>
        </div>
      </aside>

      {/* CENTER + RIGHT */}
      <div key={view} className="flex-1 min-w-0 flex flex-col animate-fade-in">
        {view === "task" && taskId && <TaskView taskId={taskId} onTaskChanged={() => refreshTasks(projectId)} />}
        {view === "task" && !taskId && (
          <div className="flex-1 grid place-items-center">
            <EmptyState
              icon={MessageSquarePlus}
              title={projectId ? "No chat selected" : "Connect a repository to begin"}
              description={
                projectId
                  ? "Select a chat from the sidebar, or start a new one."
                  : "Zanelvo Dev Studio needs a GitHub repository to analyze, plan against, and edit."
              }
              action={
                !projectId ? (
                  <Button size="sm" onClick={() => setNewProjectOpen(true)}>
                    <Plus className="w-3.5 h-3.5" /> Connect a repository
                  </Button>
                ) : (
                  <Button size="sm" disabled={!branch} loading={creatingChat} onClick={handleNewChat}>
                    <MessageSquarePlus className="w-3.5 h-3.5" /> New Chat
                  </Button>
                )
              }
            />
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

      <PromptDialog
        open={!!renameTarget}
        onOpenChange={(v) => !v && setRenameTarget(null)}
        title="Rename chat"
        defaultValue={renameTarget?.title ?? ""}
        submitLabel="Rename"
        onSubmit={handleRename}
      />
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(v) => !v && setDeleteTarget(null)}
        title={`Delete "${deleteTarget?.title ?? ""}"?`}
        description="Removes it from the sidebar. Its plan, diff, and test history stay recoverable server-side."
        confirmLabel="Delete"
        danger
        onConfirm={handleDelete}
      />
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} items={commandItems} />
    </div>
  );
}
