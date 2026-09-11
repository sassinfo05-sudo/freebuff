import { useState } from "react";
import devstudio from "@/lib/devstudio";
import { toast } from "@/lib/toast";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
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
      description="Dev Studio needs read/write access — configure a token in Settings if you haven't."
      footer={
        <Button loading={busy} disabled={!owner.trim() || !repo.trim()} onClick={submit}>
          Connect
        </Button>
      }
    >
      <div>
        <label className="text-xs text-white/50 block mb-1">Owner</label>
        <Input value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="e.g. your-username" />
      </div>
      <div>
        <label className="text-xs text-white/50 block mb-1">Repository</label>
        <Input value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="Repository name" />
      </div>
      <div>
        <label className="text-xs text-white/50 block mb-1">Default branch</label>
        <Input value={branch} onChange={(e) => setBranchName(e.target.value)} placeholder="main" />
      </div>
    </Dialog>
  );
}
