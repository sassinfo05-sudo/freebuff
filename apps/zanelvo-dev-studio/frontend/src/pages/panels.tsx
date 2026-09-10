import { useEffect, useState } from "react";
import { Folder, File as FileIcon, Search, CheckCircle2, AlertTriangle, XCircle, RefreshCw } from "lucide-react";
import devstudio from "@/lib/devstudio";
import { toast } from "@/lib/toast";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";

// --- Repository browser ---------------------------------------------------------------

export function RepoBrowser({ projectId, branch }: { projectId: string; branch: string }) {
  const [entries, setEntries] = useState<any[]>([]);
  const [subdir, setSubdir] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState("");

  useEffect(() => {
    devstudio
      .tree(projectId, branch, subdir)
      .then(({ data }) => setEntries(data.entries))
      .catch((e: any) => toast.error(e?.response?.data?.detail || "Could not load tree"));
  }, [projectId, branch, subdir]);

  async function openFile(path: string) {
    setSelected(path);
    try {
      const { data } = await devstudio.readFile(projectId, branch, path);
      setContent(data.content);
    } catch (e: any) {
      setContent(`<< ${e?.response?.data?.detail || "could not read file"} >>`);
    }
  }

  async function doSearch() {
    if (!query.trim()) {
      setResults(null);
      return;
    }
    const { data } = await devstudio.search(projectId, branch, query);
    setResults(data.results);
  }

  const rows = results ?? entries;

  return (
    <div className="flex-1 flex min-h-0">
      <div className="w-72 border-r border-white/10 flex flex-col">
        <div className="p-2 border-b border-white/10 flex gap-1">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && doSearch()}
            placeholder="Search code…"
          />
          <Button size="icon" variant="ghost" onClick={doSearch}>
            <Search className="w-3.5 h-3.5" />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-1">
          {subdir && (
            <button
              className="w-full text-left px-2 py-1 text-xs text-white/50 hover:bg-white/5 rounded"
              onClick={() => setSubdir(subdir.split("/").slice(0, -1).join("/"))}
            >
              .. (up)
            </button>
          )}
          {rows.map((e) => (
            <button
              key={e.path}
              onClick={() => (e.is_dir ? setSubdir(e.path) : openFile(e.path))}
              className={`w-full flex items-center gap-1.5 text-left px-2 py-1 text-xs rounded hover:bg-white/5 ${
                selected === e.path ? "bg-white/10 text-white" : "text-white/70"
              }`}
            >
              {e.is_dir ? (
                <Folder className="w-3.5 h-3.5 text-sky-400 flex-shrink-0" />
              ) : (
                <FileIcon className="w-3.5 h-3.5 text-white/40 flex-shrink-0" />
              )}
              <span className="truncate">{e.path.split("/").pop()}</span>
              {e.line && <span className="text-white/30 ml-auto flex-shrink-0">:{e.line}</span>}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        <pre className="p-4 text-xs text-white/80 whitespace-pre-wrap font-mono">
          {content || "Select a file to view its contents."}
        </pre>
      </div>
    </div>
  );
}

// --- Project memory --------------------------------------------------------------------

export function MemoryPanel({ projectId }: { projectId: string }) {
  const [items, setItems] = useState<any[]>([]);

  async function load() {
    const { data } = await devstudio.listMemory(projectId);
    setItems(data.memory);
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="p-6 max-w-3xl mx-auto space-y-3">
        <div className="text-sm font-medium text-white/80 mb-2">Project Memory</div>
        {items.map((m) => (
          <div key={m.id} className="rounded-lg border border-white/10 bg-white/5 p-3">
            <div className="flex items-center gap-2 mb-1">
              <Badge className="border-white/20 text-white/60">{m.category}</Badge>
              {m.stale && <Badge className="bg-amber-500/20 text-amber-300 border-0">stale</Badge>}
              <span className="text-xs font-medium text-white/80">{m.title}</span>
            </div>
            <div className="text-xs text-white/60 whitespace-pre-wrap">{m.content}</div>
          </div>
        ))}
        {!items.length && <div className="text-xs text-white/40">No memory recorded yet — it accumulates as tasks run.</div>}
      </div>
    </div>
  );
}

// --- Agents config -----------------------------------------------------------------------

export function AgentsPanel() {
  const [agents, setAgents] = useState<Record<string, any>>({});

  async function load() {
    const { data } = await devstudio.agentConfigs();
    setAgents(data.agents);
  }
  useEffect(() => {
    load();
  }, []);

  async function applyPreset(preset: string) {
    const { data } = await devstudio.applyPreset(preset);
    setAgents(data.agents);
    toast.success(`Applied ${preset} preset to all agents`);
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="p-6 max-w-3xl mx-auto space-y-4">
        <div className="flex items-center justify-between">
          <div className="text-sm font-medium text-white/80">Agent Configuration</div>
          <div className="flex gap-1.5">
            {["ECONOMICAL", "BALANCED", "MAX_QUALITY"].map((p) => (
              <Button key={p} size="sm" variant="outline" onClick={() => applyPreset(p)}>
                {p}
              </Button>
            ))}
          </div>
        </div>
        {Object.entries(agents).map(([role, cfg]) => (
          <div key={role} className="rounded-lg border border-white/10 bg-white/5 p-3 text-xs flex items-center justify-between">
            <div>
              <div className="font-medium text-white/80 capitalize">{role.replace(/_/g, " ")}</div>
              <div className="text-white/40 mt-0.5">
                {cfg.primary_provider}/{cfg.primary_model}
                {cfg.fallback_model && <span> → fallback {cfg.fallback_provider}/{cfg.fallback_model}</span>}
              </div>
            </div>
            <Badge className={cfg.enabled ? "border-emerald-500/40 text-emerald-300" : "border-white/20 text-white/40"}>
              {cfg.enabled ? "enabled" : "disabled"}
            </Badge>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- GitHub ------------------------------------------------------------------------------

export function GitHubPanel() {
  const [status, setStatus] = useState<any>(null);
  const [repos, setRepos] = useState<any[]>([]);

  async function load() {
    const { data } = await devstudio.githubWhoami();
    setStatus(data);
    if (data.available) {
      const r = await devstudio.githubRepos();
      setRepos(r.data.repos);
    }
  }
  useEffect(() => {
    load();
  }, []);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="p-6 max-w-3xl mx-auto space-y-4">
        <div className="flex items-center gap-2">
          {status?.available ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          ) : (
            <XCircle className="w-4 h-4 text-red-400" />
          )}
          <span className="text-sm text-white/80">{status?.detail || "Checking…"}</span>
          <Button size="icon" variant="ghost" className="ml-auto" onClick={load}>
            <RefreshCw className="w-3.5 h-3.5" />
          </Button>
        </div>
        {!status?.available && (
          <div className="text-xs text-white/50">
            Configure a GitHub Personal Access Token in Settings to browse repositories, index code,
            and commit/push from Dev Studio.
          </div>
        )}
        {repos.map((r) => (
          <div key={r.full_name} className="rounded-lg border border-white/10 bg-white/5 p-3 text-xs flex items-center justify-between">
            <span className="text-white/80">{r.full_name}</span>
            <Badge className="border-white/20 text-white/50">{r.default_branch}</Badge>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Settings ----------------------------------------------------------------------------

export function SettingsPanel() {
  const [caps, setCaps] = useState<any[]>([]);
  const [secretsConfigured, setSecretsConfigured] = useState<Record<string, boolean>>({});
  const [githubPat, setGithubPat] = useState("");
  const [anthropicKey, setAnthropicKey] = useState("");

  async function load() {
    const { data } = await devstudio.capabilities();
    setCaps(data.capabilities);
    const s = await devstudio.getSettings();
    setSecretsConfigured(s.data.secrets_configured);
  }
  useEffect(() => {
    load();
  }, []);

  async function saveSecret(name: string, value: string, clear: (v: string) => void) {
    if (!value) return;
    await devstudio.setSecret(name, value);
    toast.success("Saved. It is encrypted at rest and never shown again.");
    clear("");
    load();
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="p-6 max-w-2xl mx-auto space-y-6">
        <div>
          <div className="text-sm font-medium text-white/80 mb-2">Capabilities</div>
          <div className="space-y-1">
            {caps.map((c) => (
              <div key={c.name} className="flex items-center gap-2 text-xs">
                {c.available ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                ) : (
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
                )}
                <span className="text-white/70 w-44">{c.name.replace(/_/g, " ")}</span>
                <span className="text-white/40 truncate">{c.detail || (c.available ? "available" : "unavailable")}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="text-sm font-medium text-white/80 mb-2">Secrets</div>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-white/50">
                GitHub Personal Access Token{" "}
                {secretsConfigured.github_pat && <Badge className="ml-1 bg-emerald-500/20 text-emerald-300 border-0">configured</Badge>}
              </label>
              <div className="flex gap-1.5 mt-1">
                <Input type="password" value={githubPat} onChange={(e) => setGithubPat(e.target.value)} placeholder="ghp_…" />
                <Button size="sm" onClick={() => saveSecret("github_pat", githubPat, setGithubPat)}>
                  Save
                </Button>
              </div>
            </div>
            <div>
              <label className="text-xs text-white/50">
                Anthropic API Key{" "}
                {secretsConfigured.anthropic_api_key && <Badge className="ml-1 bg-emerald-500/20 text-emerald-300 border-0">configured</Badge>}
              </label>
              <div className="flex gap-1.5 mt-1">
                <Input type="password" value={anthropicKey} onChange={(e) => setAnthropicKey(e.target.value)} placeholder="sk-ant-…" />
                <Button size="sm" onClick={() => saveSecret("anthropic_api_key", anthropicKey, setAnthropicKey)}>
                  Save
                </Button>
              </div>
            </div>
            <div className="text-[11px] text-white/40">
              Secrets are encrypted at rest and never re-displayed. Environment variables
              (ANTHROPIC_API_KEY, DEVSTUDIO_GITHUB_TOKEN) override these if set.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
