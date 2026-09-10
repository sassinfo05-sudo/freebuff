import { useState } from "react";
import devstudio from "@/lib/devstudio";
import { toast } from "@/lib/toast";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { Select } from "@/components/ui/Select";
import { Dialog } from "@/components/ui/Dialog";

export function NewProjectDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onCreated: () => void;
}) {
  const [owner, setOwner] = useState("");
  const [repo, setRepo] = useState("");
  const [branch, setBranchName] = useState("main");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!owner.trim() || !repo.trim()) return;
    setBusy(true);
    try {
      await devstudio.createProject({
        github_owner: owner.trim(), github_repo: repo.trim(), default_branch: branch.trim() || "main",
      });
      toast.success("Repository connected");
      onCreated();
      setOwner("");
      setRepo("");
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || "Could not connect repository");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Connect a GitHub repository"
      footer={<Button disabled={busy} onClick={submit}>{busy ? "Connecting…" : "Connect"}</Button>}
    >
      <Input value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="Owner (e.g. your-username)" />
      <Input value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="Repository name" />
      <Input value={branch} onChange={(e) => setBranchName(e.target.value)} placeholder="Default branch" />
    </Dialog>
  );
}

export function NewTaskDialog({
  open,
  onOpenChange,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onSubmit: (fields: { title: string; request_text: string; mode: string }) => void;
}) {
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [mode, setMode] = useState("feature");

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="New Task"
      footer={
        <Button
          disabled={!title.trim() || !text.trim()}
          onClick={() => onSubmit({ title: title.trim(), request_text: text.trim(), mode })}
        >
          Create &amp; Run
        </Button>
      }
    >
      <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Short title" />
      <Select
        value={mode}
        onChange={(e) => setMode(e.target.value)}
        options={["feature", "bugfix", "refactor", "chore", "investigation"].map((m) => ({ value: m, label: m }))}
      />
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={5}
        placeholder="Describe the feature or bug in natural language…"
      />
    </Dialog>
  );
}
