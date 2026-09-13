"""End-to-end review tests for Zanelvo Dev Studio bug fixes.
Covers:
- Agent config invariants (emergent primary, auto_provider on, memory MCP, tools_enabled non-empty)
- Preset regression (MAX_QUALITY / ECONOMICAL / BALANCED must not change provider or use gpt-6-astra)
- Live task run: BLOCKED task must progress past PLANNING with no PROVIDER_ERROR / no runtime balance.
"""
import os
import time
import pytest
import requests

BASE_URL = "https://dd9723a3-2b0f-40a4-9f36-1a22a68cb070.preview.emergentagent.com"
ADMIN_PASSWORD = "zanelvo-admin-2026"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


def _get_config(client):
    r = client.get(f"{BASE_URL}/api/devstudio/agents/config", timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _assert_invariants(cfg):
    # cfg is {"agents": {role: spec, ...}} or similar
    roles = cfg.get("agents") or cfg.get("roles") or cfg
    if isinstance(roles, dict) and roles.get("agents"):
        roles = roles["agents"]
    assert isinstance(roles, dict) and roles, f"empty config: {cfg}"
    for role, spec in roles.items():
        if not isinstance(spec, dict):
            continue
        assert spec.get("primary_provider") == "emergent", f"{role} provider={spec.get('primary_provider')}"
        assert spec.get("auto_provider") is True, f"{role} auto_provider={spec.get('auto_provider')}"
        tools = spec.get("tools_enabled") or []
        assert len(tools) > 0, f"{role} has no tools_enabled"
        mcps = spec.get("mcp_servers") or []
        assert "memory" in mcps, f"{role} mcp_servers={mcps}"
        assert spec.get("primary_model") != "gpt-6-astra", f"{role} uses banned gpt-6-astra"


def test_agent_config_invariants(client):
    cfg = _get_config(client)
    _assert_invariants(cfg)


@pytest.mark.parametrize("preset", ["MAX_QUALITY", "ECONOMICAL", "BALANCED"])
def test_preset_does_not_break_invariants(client, preset):
    r = client.post(f"{BASE_URL}/api/devstudio/agents/preset/{preset}", timeout=30)
    assert r.status_code in (200, 201, 204), f"preset {preset}: {r.status_code} {r.text}"
    cfg = _get_config(client)
    _assert_invariants(cfg)


def test_task_progresses_past_planning(client):
    # Restore MAX_QUALITY (planner=gpt-5.6-terra) prior to task run
    client.post(f"{BASE_URL}/api/devstudio/agents/preset/MAX_QUALITY", timeout=30)

    # Find a BLOCKED task or create a new one
    r = client.get(f"{BASE_URL}/api/devstudio/tasks", timeout=30)
    assert r.status_code == 200, r.text
    tasks = r.json()
    task_list = tasks.get("tasks", tasks) if isinstance(tasks, dict) else tasks

    task_id = None
    for t in task_list:
        if isinstance(t, dict) and t.get("status") == "BLOCKED":
            task_id = t.get("id") or t.get("task_id")
            print(f"Found BLOCKED task: {task_id}")
            break

    if not task_id:
        # Create a new task in existing project
        pr = client.get(f"{BASE_URL}/api/devstudio/projects", timeout=30)
        assert pr.status_code == 200, pr.text
        pj = pr.json()
        projects = pj.get("projects", pj) if isinstance(pj, dict) else pj
        assert projects, "no projects available"
        project_id = projects[0].get("id") or projects[0].get("project_id")
        payload = {
            "project_id": project_id,
            "branch": "main",
            "request": "Add a visible move counter reset button",
            "title": "Add reset button",
        }
        cr = client.post(f"{BASE_URL}/api/devstudio/tasks", json=payload, timeout=60)
        assert cr.status_code in (200, 201), f"create task failed: {cr.status_code} {cr.text}"
        cj = cr.json()
        task_id = cj.get("id") or cj.get("task_id") or (cj.get("task") or {}).get("id")
        print(f"Created new task: {task_id}")

    assert task_id, "no task id available"

    # Trigger run
    run = client.post(f"{BASE_URL}/api/devstudio/tasks/{task_id}/run", timeout=60)
    assert run.status_code in (200, 201, 202), f"run failed: {run.status_code} {run.text}"

    # Poll status up to ~4 minutes
    deadline = time.time() + 240
    last_status = None
    last_blocked = None
    plan_produced = False
    advanced_past_planning = False
    seen_planning = False
    terminal_ok = {"READY", "IMPLEMENTING", "REVIEWING", "READY_FOR_APPROVAL", "QA", "TESTING", "APPROVED", "COMPLETED", "MERGED"}

    while time.time() < deadline:
        time.sleep(10)
        s = client.get(f"{BASE_URL}/api/devstudio/tasks/{task_id}", timeout=30)
        if s.status_code != 200:
            continue
        sj = s.json()
        task = sj.get("task", sj) if isinstance(sj, dict) else sj
        status = task.get("status")
        blocked_reason = task.get("blocked_reason") or ""
        last_status = status
        last_blocked = blocked_reason
        print(f"[poll] status={status} blocked_reason={blocked_reason!r}")

        if status == "PLANNING":
            seen_planning = True

        # Fetch plan
        pr = client.get(f"{BASE_URL}/api/devstudio/tasks/{task_id}/plan", timeout=30)
        if pr.status_code == 200:
            pj = pr.json()
            plan = pj.get("plan", pj) if isinstance(pj, dict) else pj
            steps = (plan or {}).get("steps") if isinstance(plan, dict) else None
            if steps:
                plan_produced = True

        if status in terminal_ok:
            advanced_past_planning = True
            break
        if status == "BLOCKED":
            if "PROVIDER_ERROR" in blocked_reason or "no runtime balance" in blocked_reason.lower():
                pytest.fail(f"Regression: BLOCKED with old error: {blocked_reason}")
            # Some OTHER blocked reason, still bad - stop
            pytest.fail(f"Task BLOCKED with reason: {blocked_reason}")

    print(f"Final status={last_status} blocked={last_blocked!r} plan_produced={plan_produced}")

    # Assert no bug regression
    if last_blocked:
        assert "PROVIDER_ERROR" not in last_blocked, f"planner PROVIDER_ERROR: {last_blocked}"
        assert "no runtime balance" not in last_blocked.lower(), f"'no runtime balance' error: {last_blocked}"

    assert advanced_past_planning or plan_produced, (
        f"Task did not progress past PLANNING and no plan produced. "
        f"status={last_status} blocked_reason={last_blocked!r}"
    )
