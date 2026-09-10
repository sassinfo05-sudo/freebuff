import { useEffect, useState } from "react";
import { Folder, File as FileIcon, Search, CheckCircle2, AlertTriangle, XCircle, RefreshCw } from "lucide-react";
import devstudio from "@/lib/devstudio";
import { toast } from "@/lib/toast";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Select } from "@/components/ui/Select";

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

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  gemini: "Gemini",
  bedrock: "Amazon Bedrock",
  emergent: "Emergent",
};

const EDITABLE_FIELDS = [
  "enabled", "primary_provider", "primary_model", "fallback_provider", "fallback_model",
  "reasoning_level", "max_attempts", "automatic_fallback",
] as const;

type ModelInfo = { id: string; provider: string; label: string };
type AgentDraft = {
  enabled: boolean;
  primary_provider: string;
  primary_model: string;
  fallback_provider: string | null;
  fallback_model: string | null;
  reasoning_level: string | null;
  max_attempts: number;
  automatic_fallback: boolean;
};

export function AgentsPanel() {
  const [agents, setAgents] = useState<Record<string, AgentDraft>>({});
  const [drafts, setDrafts] = useState<Record<string, AgentDraft>>({});
  const [modelsByProvider, setModelsByProvider] = useState<Record<string, ModelInfo[]>>({});
  const [providers, setProviders] = useState<string[]>([]);
  const [savingRole, setSavingRole] = useState<string | null>(null);

  async function load() {
    const [{ data: agentData }, { data: modelData }] = await Promise.all([
      devstudio.agentConfigs(),
      devstudio.providerModels(),
    ]);
    setAgents(agentData.agents);
    setDrafts(Object.fromEntries(Object.entries(agentData.agents).map(([r, c]) => [r, { ...(c as AgentDraft) }])));
    setModelsByProvider(modelData.models);
    setProviders(modelData.providers);
  }
  useEffect(() => {
    load();
  }, []);

  async function applyPreset(preset: string) {
    const { data } = await devstudio.applyPreset(preset);
    setAgents(data.agents);
    setDrafts(Object.fromEntries(Object.entries(data.agents).map(([r, c]) => [r, { ...(c as AgentDraft) }])));
    toast.success(`Applied ${preset} preset to all agents`);
  }

  function setField<K extends keyof AgentDraft>(role: string, field: K, value: AgentDraft[K]) {
    setDrafts((d) => ({ ...d, [role]: { ...d[role], [field]: value } }));
  }

  function isDirty(role: string): boolean {
    const a = agents[role], d = drafts[role];
    if (!a || !d) return false;
    return EDITABLE_FIELDS.some((k) => (a[k] ?? null) !== (d[k] ?? null));
  }

  async function save(role: string) {
    setSavingRole(role);
    try {
      const d = drafts[role];
      const { data } = await devstudio.updateAgentConfig(role, {
        enabled: d.enabled,
        primary_provider: d.primary_provider,
        primary_model: d.primary_model,
        fallback_provider: d.fallback_provider || null,
        fallback_model: d.fallback_model || null,
        reasoning_level: d.reasoning_level || null,
        max_attempts: d.max_attempts,
        automatic_fallback: d.automatic_fallback,
      });
      setAgents((a) => ({ ...a, [role]: data }));
      setDrafts((dr) => ({ ...dr, [role]: { ...data } }));
      toast.success(`Saved ${role.replace(/_/g, " ")}`);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Could not save agent config");
    } finally {
      setSavingRole(null);
    }
  }

  function modelOptions(provider: string) {
    const models = modelsByProvider[provider] || [];
    if (!models.length) return [{ value: "", label: provider === "emergent" ? "(stub — no models yet)" : "(no models)" }];
    return models.map((m) => ({ value: m.id, label: m.label }));
  }

  const providerOptions = providers.map((p) => ({ value: p, label: PROVIDER_LABELS[p] || p }));

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
        <div className="text-[11px] text-white/40">
          Presets set every role at once. Override any single role below — including its
          fallback — without leaving the preset for everything else.
        </div>
        {Object.entries(drafts).map(([role, cfg]) => (
          <div key={role} className="rounded-lg border border-white/10 bg-white/5 p-3 text-xs space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="font-medium text-white/80 capitalize">{role.replace(/_/g, " ")}</div>
              <div className="flex items-center gap-2">
                {isDirty(role) && <Badge className="border-amber-500/40 text-amber-300">unsaved</Badge>}
                <label className="flex items-center gap-1.5 text-white/60">
                  <input type="checkbox" checked={cfg.enabled}
                    onChange={(e) => setField(role, "enabled", e.target.checked)} />
                  enabled
                </label>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <div className="text-white/40 mb-1">Primary provider</div>
                <Select value={cfg.primary_provider} options={providerOptions}
                  onChange={(e) => {
                    const provider = e.target.value;
                    const firstModel = (modelsByProvider[provider] || [])[0]?.id || "";
                    setDrafts((d) => ({ ...d, [role]: { ...d[role], primary_provider: provider, primary_model: firstModel } }));
                  }} />
              </div>
              <div>
                <div className="text-white/40 mb-1">Primary model</div>
                <Select value={cfg.primary_model} options={modelOptions(cfg.primary_provider)}
                  onChange={(e) => setField(role, "primary_model", e.target.value)} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <div className="text-white/40 mb-1">Fallback provider</div>
                <Select value={cfg.fallback_provider || ""}
                  options={[{ value: "", label: "None" }, ...providerOptions]}
                  onChange={(e) => {
                    const provider = e.target.value;
                    const firstModel = provider ? (modelsByProvider[provider] || [])[0]?.id || "" : "";
                    setDrafts((d) => ({
                      ...d,
                      [role]: { ...d[role], fallback_provider: provider || null, fallback_model: firstModel || null },
                    }));
                  }} />
              </div>
              <div>
                <div className="text-white/40 mb-1">Fallback model</div>
                <Select value={cfg.fallback_model || ""} disabled={!cfg.fallback_provider}
                  options={cfg.fallback_provider ? modelOptions(cfg.fallback_provider) : [{ value: "", label: "—" }]}
                  onChange={(e) => setField(role, "fallback_model", e.target.value)} />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div>
                <div className="text-white/40 mb-1">Reasoning level</div>
                <Select value={cfg.reasoning_level || ""}
                  options={[
                    { value: "", label: "none" }, { value: "low", label: "low" },
                    { value: "medium", label: "medium" }, { value: "high", label: "high" },
                  ]}
                  onChange={(e) => setField(role, "reasoning_level", e.target.value || null)} />
              </div>
              <div>
                <div className="text-white/40 mb-1">Max attempts</div>
                <Input type="number" min={1} max={5} value={cfg.max_attempts}
                  onChange={(e) => setField(role, "max_attempts", Number(e.target.value) || 1)} />
              </div>
              <div>
                <div className="text-white/40 mb-1">Auto-fallback</div>
                <label className="flex items-center gap-1.5 text-white/60 h-8">
                  <input type="checkbox" checked={cfg.automatic_fallback}
                    onChange={(e) => setField(role, "automatic_fallback", e.target.checked)} />
                  on failure
                </label>
              </div>
            </div>

            <div className="flex items-center justify-between pt-1">
              <div className="text-white/40">
                {cfg.primary_provider}/{cfg.primary_model || "—"}
                {cfg.fallback_model
                  ? <span> → fallback {cfg.fallback_provider}/{cfg.fallback_model}</span>
                  : <span> → no fallback</span>}
              </div>
              <Button size="sm" disabled={!isDirty(role) || savingRole === role} onClick={() => save(role)}>
                {savingRole === role ? "Saving…" : "Save"}
              </Button>
            </div>
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
  const [reposError, setReposError] = useState<string | null>(null);

  async function load() {
    setReposError(null);
    const { data } = await devstudio.githubWhoami();
    setStatus(data);
    if (data.available) {
      try {
        const r = await devstudio.githubRepos();
        setRepos(r.data.repos);
      } catch (e: any) {
        // Connectivity can be fine while listing repos still fails (e.g. a token scoped to
        // specific repos rather than full account access) — surface it instead of going quiet.
        setRepos([]);
        setReposError(e?.response?.data?.detail || "Could not list repositories");
      }
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
        {reposError && <div className="text-xs text-amber-300">{reposError}</div>}
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

const SECRET_FIELDS: { key: string; label: string; placeholder: string; group: string }[] = [
  { key: "github_pat", label: "GitHub Personal Access Token", placeholder: "ghp_…", group: "GitHub" },
  { key: "anthropic_api_key", label: "Anthropic API Key", placeholder: "sk-ant-…", group: "Native API keys" },
  { key: "openai_api_key", label: "OpenAI API Key", placeholder: "sk-…", group: "Native API keys" },
  { key: "gemini_api_key", label: "Gemini API Key", placeholder: "AIza…", group: "Native API keys" },
  { key: "emergent_universal_key", label: "Emergent Universal Key", placeholder: "sk-emergent-…", group: "Emergent" },
  { key: "aws_access_key_id", label: "AWS Access Key ID", placeholder: "AKIA…", group: "Amazon Bedrock" },
  { key: "aws_secret_access_key", label: "AWS Secret Access Key", placeholder: "…", group: "Amazon Bedrock" },
  { key: "aws_session_token", label: "AWS Session Token (optional, for temporary credentials)", placeholder: "…", group: "Amazon Bedrock" },
  { key: "aws_region", label: "AWS Region", placeholder: "us-east-1", group: "Amazon Bedrock" },
];
const SECRET_GROUPS = ["GitHub", "Native API keys", "Amazon Bedrock", "Emergent"];

export function SettingsPanel() {
  const [caps, setCaps] = useState<any[]>([]);
  const [secretsConfigured, setSecretsConfigured] = useState<Record<string, boolean>>({});
  const [draft, setDraft] = useState<Record<string, string>>({});

  async function load() {
    const { data } = await devstudio.capabilities();
    setCaps(data.capabilities);
    const s = await devstudio.getSettings();
    setSecretsConfigured(s.data.secrets_configured);
  }
  useEffect(() => {
    load();
  }, []);

  async function saveSecret(name: string) {
    const value = draft[name];
    if (!value) return;
    await devstudio.setSecret(name, value);
    toast.success("Saved. It is encrypted at rest and never shown again.");
    setDraft((d) => ({ ...d, [name]: "" }));
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
          <div className="space-y-5">
            {SECRET_GROUPS.map((group) => (
              <div key={group} className="space-y-3">
                <div className="text-[11px] uppercase tracking-wide text-white/40">{group}</div>
                {group === "Amazon Bedrock" && (
                  <div className="text-[11px] text-white/40 -mt-1">
                    Access key/secret are optional — if left blank, Bedrock falls back to the
                    standard AWS default credential chain (environment variables, an EC2/ECS/Lambda
                    IAM role). A region is always required.
                  </div>
                )}
                {SECRET_FIELDS.filter((f) => f.group === group).map((f) => (
                  <div key={f.key}>
                    <label className="text-xs text-white/50">
                      {f.label}{" "}
                      {secretsConfigured[f.key] && (
                        <Badge className="ml-1 bg-emerald-500/20 text-emerald-300 border-0">configured</Badge>
                      )}
                    </label>
                    <div className="flex gap-1.5 mt-1">
                      <Input type="password" value={draft[f.key] || ""}
                        onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))}
                        placeholder={f.placeholder} />
                      <Button size="sm" onClick={() => saveSecret(f.key)}>Save</Button>
                    </div>
                  </div>
                ))}
              </div>
            ))}
            <div className="text-[11px] text-white/40">
              Secrets are encrypted at rest and never re-displayed. Environment variables
              (ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, DEVSTUDIO_GITHUB_TOKEN,
              EMERGENT_UNIVERSAL_KEY, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN,
              AWS_REGION) override these if set.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
