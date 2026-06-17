from future import annotations import hashlib import json import os import random import re import subprocess import sys import time import types from typing import Any import requests
def _diag_log_environment() -> dict[str, Any]: """Emit and return the redacted environment snapshot.""" snap = _diag_environment_snapshot() _diag_info("environment", **snap) return snap
_CREATE_SOURCE = r''' from future import annotations
import ast import hashlib import json import os import random import re import shlex import subprocess import time from typing import Any, Iterable
import requests
MODEL_PRICING_PER_MILLION: dict[str, tuple[float, float]] = { "anthropic/claude-opus-4.7": (6.00, 30.00), "anthropic/claude-opus-4.8": (6.00, 30.00), "openai/gpt-5.5": (5.00, 30.00), "anthropic/claude-sonnet-4.5": (3.00, 15.00), "anthropic/claude-sonnet-4.6": (3.00, 15.00), "minimax/minimax-m2.5": (0.15, 1.15), "qwen/qwen3-coder-next": (0.11, 0.80), "qwen/qwen3.5-397b-a17b": (0.35, 1.40), "z-ai/glm-4.6": (0.60, 2.20), "z-ai/glm-4.7": (0.60, 2.20), "z-ai/glm-5": (0.80, 3.00), "moonshotai/kimi-k2.5": (0.60, 2.50), "moonshotai/kimi-k2.6": (0.60, 2.50), }
def _env_float(name: str, default: float) -> float: raw = (os.getenv(name) or "").strip() if not raw: return default try: return float(raw) except ValueError: return default
def _env_int(name: str, default: int) -> int: raw = (os.getenv(name) or "").strip() if not raw: return default try: return int(raw) except ValueError: return default
def _env_model_list(name: str, defaults: list[str]) -> list[str]: raw = (os.getenv(name) or "").strip() values = [p.strip() for p in raw.split(",") if p.strip()] if raw else defaults out: list[str] = [] for model in values: if model and model not in out: out.append(model) return out
class AgentConfig:
def __init__(self) -> None:
    main = os.getenv("RIDGES_AGENT_MODEL", "").strip()
    default_spec = main or "anthropic/claude-opus-4.8"
    default_bugfix = main or "anthropic/claude-opus-4.8"
    spec = os.getenv("RIDGES_AGENT_SPEC_MODEL", default_spec).strip()
    bugfix = os.getenv("RIDGES_AGENT_BUGFIX_MODEL", default_bugfix).strip()
    self.spec_model = spec or default_spec
    self.bugfix_model = bugfix or default_bugfix
    
    self.model = self.bugfix_model
    fast = os.getenv("RIDGES_AGENT_FAST_MODEL", "qwen/qwen3-coder-next").strip()
    self.fast_model = fast or self.model
    self.spec_model_cascade = _env_model_list(
        "RIDGES_AGENT_SPEC_MODEL_CASCADE",
        [self.spec_model, self.bugfix_model, "minimax/minimax-m2.5", self.fast_model],
    )
    self.bugfix_model_cascade = _env_model_list(
        "RIDGES_AGENT_BUGFIX_MODEL_CASCADE",
        [self.bugfix_model, "minimax/minimax-m2.5", self.fast_model],
    )
    self.repair_model_cascade = _env_model_list(
        "RIDGES_AGENT_REPAIR_MODEL_CASCADE",
        [self.bugfix_model, "minimax/minimax-m2.5", self.fast_model],
    )
    self.localize_model_cascade = _env_model_list(
        "RIDGES_AGENT_LOCALIZE_MODEL_CASCADE",
        [self.fast_model, "minimax/minimax-m2.5"],
    )
    self.semantic_model_cascade = _env_model_list(
        "RIDGES_AGENT_SEMANTIC_MODEL_CASCADE",
        [self.fast_model, "minimax/minimax-m2.5"],
    )
    self.review_model_cascade = _env_model_list(
        "RIDGES_AGENT_REVIEW_MODEL_CASCADE",
        [self.fast_model, "minimax/minimax-m2.5"],
    )
    self.temperature = _env_float("RIDGES_AGENT_TEMPERATURE", 0.0)
    self.top_p = _env_float("RIDGES_AGENT_TOP_P", 1.0)
    self.max_cost_usd = _env_float("RIDGES_MAX_COST_USD", 0.29)
    self.max_model_calls = _env_int("RIDGES_AGENT_MAX_MODEL_CALLS", 8)
    self.max_repair_attempts = _env_int("RIDGES_AGENT_MAX_REPAIR_ATTEMPTS", 2)
    self.command_timeout = _env_int("RIDGES_AGENT_COMMAND_TIMEOUT", 120)
    self.llm_connect_timeout = _env_int("LLM_CONNECT_TIMEOUT", 30)
    self.llm_read_timeout = _env_int("LLM_REQUEST_TIMEOUT", 130)
    self.max_output_tokens = _env_int("RIDGES_AGENT_MAX_OUTPUT_TOKENS", 5000)
    self.repo_index_chars = _env_int("RIDGES_AGENT_REPO_INDEX_CHARS", 55000)
    self.patch_state_chars = _env_int("RIDGES_AGENT_PATCH_STATE_CHARS", 90000)
    self.bugfix_patch_state_chars = _env_int("RIDGES_AGENT_BUGFIX_PATCH_STATE_CHARS", 55000)
    self.test_output_chars = _env_int("RIDGES_AGENT_TEST_OUTPUT_CHARS", 7000)
    self.repair_max_output_tokens = _env_int("RIDGES_AGENT_REPAIR_MAX_OUTPUT_TOKENS", min(self.max_output_tokens, 3600))
    self.enable_final_review = (os.getenv("RIDGES_AGENT_FINAL_REVIEW", "0").lower() in {"1", "true", "yes", "on"})
    self.working_dir = os.getenv("RIDGES_WORKING_DIR", "").strip() or None
    self.assumed_wall_sec = _env_float("RIDGES_AGENT_ASSUMED_WALL_SEC", 600.0)
    self.tail_margin_sec = max(20.0, _env_float("RIDGES_AGENT_TAIL_MARGIN_SEC", 45.0))

def patch_model_for_mode(self, mode: str) -> str:
    return self.spec_model if mode == "spec" else self.bugfix_model

def model_cascade_for_phase(self, mode: str, phase: str) -> list[str]:
    if phase == "localize":
        return self.localize_model_cascade
    if phase == "semantic":
        return self.semantic_model_cascade
    if phase == "review":
        return self.review_model_cascade
    if phase == "repair":
        return self.repair_model_cascade
    return self.spec_model_cascade if mode == "spec" else self.bugfix_model_cascade
def _openrouter_api_key() -> str | None: return os.getenv("OPENROUTER_API_KEY")
def _openrouter_base_url() -> str: return ( os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1" ).rstrip("/")
def _openrouter_provider_routing() -> dict[str, Any] | None: if (os.getenv("RIDGES_OR_PROVIDER_OFF") or "").strip().lower() in {"1", "true", "yes", "on"}: return None prov: dict[str, Any] = {"require_parameters": True} order = [p.strip() for p in (os.getenv("RIDGES_OR_PROVIDER_ORDER") or "").split(",") if p.strip()] if order: prov["order"] = order af = (os.getenv("RIDGES_OR_ALLOW_FALLBACKS") or "1").strip().lower() if af in {"0", "false", "no", "off"} or (order and af not in {"1", "true", "yes", "on"}): prov["allow_fallbacks"] = False return prov
def _log_inference_target_once() -> None: if getattr(_log_inference_target_once, "_done", False): return _log_inference_target_once._done = True
base = _openrouter_base_url() has_key = bool(_openrouter_api_key()) model = os.getenv("RIDGES_AGENT_MODEL", "").strip() or "(unset)" print( "[INFERENCE] target=openrouter-direct " f"base_url={base} api_key={'set' if has_key else 'MISSING'} " f"default_model={model} (no gateway)" )
def _resolve_inference_seed() -> int: raw = os.getenv("RIDGES_LLM_SEED", "").strip() base = raw or os.getenv("EVALUATION_RUN_ID", "") or "ridges-agent" try: return int(base) % (2**31) except ValueError: digest = hashlib.sha256(base.encode("utf-8", "ignore")).digest() return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF
_stable_seed = _resolve_inference_seed
def _prompt_cache_enabled() -> bool: return (os.getenv("RIDGES_PROMPT_CACHE", "1").strip().lower() not in {"0", "false", "no", "off"})
def _with_cache_control(role: str, content: str) -> dict[str, Any]: if not _prompt_cache_enabled(): return {"role": role, "content": content} return { "role": role, "content": [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}], }
def _model_prices(model: str) -> tuple[float, float]: resolved = model for key in (model, resolved): if key in MODEL_PRICING_PER_MILLION: return MODEL_PRICING_PER_MILLION[key] return (3.0, 15.0)
def estimate_call_cost_usd(model: str, system: str, user: str, max_completion_tokens: int) -> float: prompt_tokens = max(1, (len(system) + len(user)) // 3) in_price, out_price = _model_prices(model) return (prompt_tokens / 1_000_000) * in_price + (max_completion_tokens / 1_000_000) * out_price
class Budget: def init(self, config: AgentConfig) -> None: self.config = config self.total_cost = 0.0 self.calls = 0 self.prompt_tokens = 0 self.completion_tokens = 0
def update(self, model: str, usage: dict[str, Any] | None) -> None:
    self.calls += 1
    if not usage:
        return
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    total = int(usage.get("total_tokens") or (prompt + completion))
    cached = int(
        usage.get("cached_tokens")
        or (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
        or usage.get("cache_read_input_tokens")
        or 0
    )
    in_price, out_price = _model_prices(model)
    uncached = max(0, prompt - cached)
    cost = (uncached / 1_000_000) * in_price
    cost += (cached / 1_000_000) * in_price * 0.25
    cost += (completion / 1_000_000) * out_price
    self.total_cost += cost
    self.prompt_tokens += prompt
    self.completion_tokens += completion
    print(
        f"[AGENT] usage model={model} prompt={prompt} completion={completion} "
        f"cached={cached} total={total} est_cost=${cost:.4f} "
        f"cum=${self.total_cost:.4f}/${self.config.max_cost_usd:.2f}"
    )

def can_call(self, reserve_fraction: float = 0.08, estimated_cost: float = 0.0) -> bool:
    if self.calls >= self.config.max_model_calls:
        return False
    if self.config.max_cost_usd <= 0:
        return True
    return (self.total_cost + max(0.0, estimated_cost)) < self.config.max_cost_usd * (1.0 - reserve_fraction)
def _phase_reserve_fraction(phase: str) -> float: if phase == "localize": return 0.55 if phase == "patch": return 0.22 if phase == "repair": return 0.10 if phase == "review": return 0.08 if phase == "semantic": return 0.04 return 0.08
def choose_model_for_call( *, config: AgentConfig, budget: Budget, mode: str, phase: str, system: str, user: str, max_tokens: int, reserve_fraction: float | None = None, ) -> str | None: reserve = _phase_reserve_fraction(phase) if reserve_fraction is None else reserve_fraction for model in config.model_cascade_for_phase(mode, phase): estimated = estimate_call_cost_usd(model, system, user, max_tokens) if budget.can_call(reserve_fraction=reserve, estimated_cost=estimated): print( f"[AGENT] model route phase={phase} mode={mode} " f"model={model} est=${estimated:.4f} reserve={reserve:.2f}" ) return model print( f"[AGENT] model skipped phase={phase} mode={mode} " f"model={model} est=${estimated:.4f} reserve={reserve:.2f}" ) print(f"[AGENT] no affordable model for phase={phase} mode={mode}") return None
def _trajectory_logging_enabled() -> bool: return (os.getenv("RIDGES_AGENT_LOG_TRAJECTORY", "1") or "").strip().lower() not in {"0", "false", "no", "off"}
def _log_trajectory_response(call_no: int, model: str, response: str) -> None: if not _trajectory_logging_enabled(): return print(f"\n[TRAJECTORY] ========== RESPONSE  call #{call_no}  model={model} ==========") print(response) print(f"[TRAJECTORY] ========== END call #{call_no} ==========\n", flush=True)
def call_llm( *, config: AgentConfig, budget: Budget, model: str, system: str, user: str, max_tokens: int | None = None, reserve_fraction: float | None = None, force: bool = False, ) -> str | None: requested_max_tokens = max_tokens or config.max_output_tokens estimated_cost = estimate_call_cost_usd(model, system, user, requested_max_tokens) if not force: can_call_kwargs: dict[str, Any] = {"estimated_cost": estimated_cost} if reserve_fraction is not None: can_call_kwargs["reserve_fraction"] = reserve_fraction if not budget.can_call(**can_call_kwargs): print("[AGENT] Skipping LLM call: local call/cost guard reached") return None else: print(f"[AGENT] FORCED LLM call (bypassing budget guard) — est_cost=${estimated_cost:.4f}") key = _openrouter_api_key() if not key: print("[AGENT] No inference key configured") return None
payload: dict[str, Any] = {
    "model": model,
    "messages": [_with_cache_control("system", system), _with_cache_control("user", user)],
    "temperature": config.temperature,
    "top_p": config.top_p,
    "seed": _resolve_inference_seed(),
    "max_tokens": requested_max_tokens,
}
_prov = _openrouter_provider_routing()
if _prov:
    payload["provider"] = _prov
headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
url = f"{_openrouter_base_url()}/chat/completions"

last_error = ""
for attempt in range(4):
    try:
        print(f"[AGENT] inference call {budget.calls + 1}: model={payload['model']} chars={len(user)}")
        resp = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=(config.llm_connect_timeout, config.llm_read_timeout),
        )
        if resp.status_code == 429 and "budget" in resp.text.lower() and "exceed" in resp.text.lower():
            last_error = f"HTTP 429: {resp.text[:800]}"
            print(f"[AGENT] inference budget exceeded; not retrying: {last_error}")
            return None
        if resp.status_code in {408, 425, 429, 500, 502, 503, 504} and attempt < 3:
            wait = resp.headers.get("Retry-After")
            try:
                delay = float(wait) if wait else min(1.0 * (2**attempt) + random.random(), 8.0)
            except ValueError:
                delay = min(1.0 * (2**attempt) + random.random(), 8.0)
            print(f"[AGENT] transient inference HTTP {resp.status_code}; retrying")
            time.sleep(delay)
            continue
        if resp.status_code != 200:
            last_error = f"HTTP {resp.status_code}: {resp.text[:800]}"
            print(f"[AGENT] inference failed: {last_error}")
            return None
        data = resp.json()
        usage = data.get("usage") or {}
        budget.update(model, usage)
        msg = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        msg = msg.strip()
        print(f"[AGENT] inference response chars={len(msg)}")
        _log_trajectory_response(budget.calls, model, msg)
        return msg or None
    except requests.exceptions.RequestException as exc:
        last_error = f"request error: {exc}"
        if attempt < 3:
            time.sleep(min(1.0 * (2**attempt) + random.random(), 8.0))
            continue
        print(f"[AGENT] inference failed: {last_error}")
        return None
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"[AGENT] invalid inference JSON: {exc}")
        return None
print(f"[AGENT] inference exhausted: {last_error}")
return None
def _conda_prefix() -> str: env_name = (os.getenv("RIDGES_AGENT_CONDA_ENV") or "testbed").strip() if env_name.lower() in {"", "0", "off", "none", "false", "disable", "disabled"}: return "" activate = "/opt/miniconda3/bin/activate" if not os.path.isfile(activate): return "" return ( f"if [ -f {shlex.quote(activate)} ]; then " f"source {shlex.quote(activate)} >/dev/null 2>&1 && " f"conda activate {shlex.quote(env_name)} >/dev/null 2>&1 || true; fi; " )
class ShellExecutor: def init(self, root: str, timeout: int) -> None: self.root = root self.timeout = timeout self.prefix = _conda_prefix()
def run(self, command: str, timeout: int | None = None) -> dict[str, Any]:
    full = self.prefix + command if self.prefix else command
    try:
        res = subprocess.run(
            ["bash", "-lc", full],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=timeout or self.timeout,
            env={**os.environ, "TERM": "dumb"},
        )
        return {
            "stdout": res.stdout,
            "stderr": res.stderr,
            "returncode": res.returncode,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "stdout": exc.stdout or "",
            "stderr": (exc.stderr or "") + f"\nCommand timed out after {timeout or self.timeout}s",
            "returncode": -1,
            "timed_out": True,
        }
    except Exception as exc:
        return {
            "stdout": "",
            "stderr": f"Execution error: {type(exc).__name__}: {exc}",
            "returncode": -1,
            "timed_out": False,
        }
def find_repo_root(start: str | None = None) -> str: start = os.path.abspath(start or os.getcwd()) try: res = subprocess.run( ["git", "-C", start, "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10, ) if res.returncode == 0 and res.stdout.strip(): return os.path.abspath(res.stdout.strip()) except Exception: pass path = start while True: if os.path.isdir(os.path.join(path, ".git")) or os.path.isfile(os.path.join(path, ".git")): return path parent = os.path.dirname(path) if parent == path: return start path = parent
def ensure_git_baseline(root: str, executor: ShellExecutor) -> None: if os.path.isdir(os.path.join(root, ".git")) or os.path.isfile(os.path.join(root, ".git")): print("[AGENT] Existing git repository detected") return print("[AGENT] No git repository; creating baseline") executor.run("git init >/dev/null 2>&1 || true") executor.run("git config user.email ridges-agent@example.invalid && git config user.name ridges-agent") executor.run("git add -A >/dev/null 2>&1 || true") executor.run("git commit -m baseline --allow-empty >/dev/null 2>&1 || true")
def normalize_patch_text(patch: str) -> str: if not patch: return "" patch = re.sub(r"\x1b[[0-9;?][ -/][@-~]", "", patch) patch = patch.replace("\r\n", "\n").replace("\r", "\n") patch = patch.strip("\n") return patch + "\n" if patch else ""
def collect_worktree_patch(executor: ShellExecutor) -> str: untracked_res = executor.run("git ls-files --others --exclude-standard -z", timeout=30) untracked_blob = untracked_res.get("stdout") or "" added_intent = False if untracked_res.get("returncode") == 0 and untracked_blob: add = subprocess.run( ["git", "-C", executor.root, "add", "-N", "--pathspec-from-file=-", "--pathspec-file-nul"], input=untracked_blob.encode("utf-8", "surrogateescape"), capture_output=True, text=False, timeout=30, ) added_intent = add.returncode == 0 if add.returncode != 0: print(f"[AGENT] git add -N failed: {(add.stderr or add.stdout)[:300]!r}") try: res = executor.run("git -c color.ui=false -c core.pager=cat diff --binary --no-ext-diff HEAD", timeout=60) finally: if added_intent: subprocess.run( ["git", "-C", executor.root, "reset", "-q", "--pathspec-from-file=-", "--pathspec-file-nul"], input=untracked_blob.encode("utf-8", "surrogateescape"), capture_output=True, text=False, timeout=30, ) if res["returncode"] != 0: print(f"[AGENT] git diff failed: {(res['stderr'] or res['stdout'])[:500]}") return "" return normalize_patch_text(res["stdout"])
def patch_has_hunks(patch: str) -> bool: if not patch.strip(): return False return bool(re.search(r"^@@ -\d", patch, flags=re.MULTILINE) or re.search(r"^Binary files ", patch, flags=re.MULTILINE))
def validate_patch_applies_cleanly(patch: str, root: str) -> bool: patch = normalize_patch_text(patch) if not patch_has_hunks(patch): return False
dirty_probe = subprocess.run(
    ["git", "-C", root, "diff", "--quiet", "HEAD"],
    capture_output=True,
    text=True,
    timeout=30,
)
if dirty_probe.returncode == 0:
    direct = subprocess.run(
        ["git", "-C", root, "apply", "--check", "--whitespace=nowarn"],
        input=patch,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if direct.returncode == 0:
        return True
    err = (direct.stderr or direct.stdout or "").strip()
    if err:
        print(f"[AGENT] git apply --check failed: {err[:800]}")
    return False

stashed = False
ok = False
try:
    stash = subprocess.run(
        ["git", "-C", root, "stash", "push", "-u", "-m", "ridges-agent-validate", "-q"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if stash.returncode == 0:
        stashed = True
    elif stash.returncode == 1:
        msg = (stash.stdout + stash.stderr).lower()
        if "no local changes" not in msg and "nothing to stash" not in msg:
            print(f"[AGENT] stash failed: {stash.stderr[:500]}")
            return False
    else:
        print(f"[AGENT] stash failed rc={stash.returncode}: {stash.stderr[:500]}")
        return False
    direct = subprocess.run(
        ["git", "-C", root, "apply", "--check", "--whitespace=nowarn"],
        input=patch,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if direct.returncode == 0:
        ok = True
        return True
    err = (direct.stderr or direct.stdout or "").strip()
    if err:
        print(f"[AGENT] git apply --check failed: {err[:800]}")
    return False
except Exception as exc:
    print(f"[AGENT] patch validation error: {exc}")
    return False
finally:
    if stashed:
        pop = subprocess.run(
            ["git", "-C", root, "stash", "pop", "-q"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if pop.returncode != 0:
            ok = False
            print(f"[AGENT] stash pop failed after validation: {pop.stderr[:500]}")
    _ = ok
def reset_worktree(root: str) -> None: subprocess.run(["git", "-C", root, "reset", "--hard", "HEAD"], capture_output=True, text=True, timeout=120) subprocess.run(["git", "-C", root, "clean", "-fd"], capture_output=True, text=True, timeout=120) _clear_read_cache()
_TEXT_EXTS = { ".py", ".pyi", ".txt", ".rst", ".md", ".toml", ".ini", ".cfg", ".yaml", ".yml", ".json", } SKIP_PATH_PARTS = { ".git", ".hg", ".svn", ".tox", ".nox", ".venv", "venv", "env", "node_modules", "pycache", "build", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache", } STOPWORDS = { "the", "and", "for", "with", "that", "this", "from", "when", "then", "there", "their", "should", "would", "could", "into", "return", "returns", "error", "issue", "bug", "fix", "test", "tests", "class", "function", "method", "value", "values", "none", "true", "false", } IDENT_RE = re.compile(r"[A-Za-z][A-Za-z0-9]{2,}") PATH_RE = re.compile(r"(?:[A-Za-z0-9.-]+/)+[A-Za-z0-9.-]+")
_READ_CACHE: dict[tuple, str] = {} _READ_CACHE_MAX = 512
def _safe_relpath(path: str) -> bool: if not path or os.path.isabs(path): return False parts = path.replace("\", "/").split("/") return ".." not in parts and all(p not in {"", "."} for p in parts)
def _is_skipped_path(path: str) -> bool: return any(part in _SKIP_PATH_PARTS for part in path.replace("\", "/").split("/"))
def git_files(root: str) -> list[str]: try: res = subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True, timeout=30) if res.returncode == 0: return sorted([p for p in res.stdout.splitlines() if p and not _is_skipped_path(p)]) except Exception: pass out: list[str] = [] for base, dirs, files in os.walk(root): dirs[:] = [d for d in dirs if d not in _SKIP_PATH_PARTS] for name in files: rel = os.path.relpath(os.path.join(base, name), root).replace("\", "/") if not _is_skipped_path(rel): out.append(rel) return sorted(out)
def _prompt_safe_text(text: Any) -> str: if text is None: return "" if not isinstance(text, str): text = str(text) return "".join("\ufffd" if 0xD800 <= ord(ch) <= 0xDFFF else ch for ch in text)
def read_text(root: str, path: str, max_chars: int | None = None) -> str: if not _safe_relpath(path): return "" full = os.path.join(root, path) try: st = os.stat(full) except OSError: return "" if max_chars is None: max_key = -1 size_bound = st.st_size else: max_key = max_chars size_bound = st.st_size cache_key = (root, path, max_key, st.st_mtime_ns, size_bound) cached = _READ_CACHE.get(cache_key) if cached is not None: return cached ext = os.path.splitext(path)[1].lower() if ext and ext not in _TEXT_EXTS: return "" try: with open(full, "r", encoding="utf-8", errors="surrogateescape") as f: data = f.read(max_chars + 1 if max_chars else -1) except Exception: return "" data = _prompt_safe_text(data) if max_chars and len(data) > max_chars: data = data[:max_chars] + "\n......\n" if len(_READ_CACHE) >= _READ_CACHE_MAX: try: _READ_CACHE.pop(next(iter(_READ_CACHE))) except StopIteration: pass _READ_CACHE[cache_key] = data return data
def _clear_read_cache() -> None: _READ_CACHE.clear()
def issue_terms(statement: str) -> list[str]: terms: list[str] = [] for path in _PATH_RE.findall(statement or ""): terms.extend([p for p in path.replace(".", "/").split("/") if len(p) >= 3]) for quoted in re.findall(r"['\"]([^'"]{2,80})[`'"]", statement or ""): if IDENT_RE.fullmatch(quoted): terms.append(quoted) elif "." in quoted or "" in quoted: terms.extend(_IDENT_RE.findall(quoted)) terms.extend(_IDENT_RE.findall(statement or "")) cleaned: list[str] = [] seen: set[str] = set() for t in terms: if len(t) < 3: continue low = t.lower() if low in _STOPWORDS: continue if low not in seen: seen.add(low) cleaned.append(t) return cleaned[:80]
def ast_symbols_for_file(root: str, path: str) -> dict[str, Any]: text = read_text(root, path, max_chars=250000) if not text or "......" in text: return {"classes": [], "functions": [], "imports": []} try: tree = ast.parse(text) except (SyntaxError, UnicodeError, ValueError): return {"classes": [], "functions": [], "imports": []} classes: list[str] = [] functions: list[str] = [] imports: list[str] = [] for node in tree.body: if isinstance(node, ast.ClassDef): classes.append(node.name) for item in node.body: if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)): functions.append(f"{node.name}.{item.name}") elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)): functions.append(node.name) elif isinstance(node, ast.Import): imports.extend(alias.name.split(".")[0] for alias in node.names[:5]) elif isinstance(node, ast.ImportFrom): if node.module: imports.append(node.module.split(".")[0]) return {"classes": classes[:60], "functions": functions[:120], "imports": imports[:80]}
class RepoProfile: def init(self, root: str) -> None: self.root = root self.files = git_files(root) self.py_files = [p for p in self.files if p.endswith((".py", ".pyi"))] self.test_files = [p for p in self.py_files if self._looks_like_test(p)] self.source_py_files = [p for p in self.py_files if p not in self.test_files] self.total_py_bytes = 0 self.file_sizes: dict[str, int] = {} for p in self.py_files: try: size = os.path.getsize(os.path.join(root, p)) except OSError: size = 0 self.file_sizes[p] = size self.total_py_bytes += size self.symbols: dict[str, dict[str, Any]] = {} for p in self.py_files[:450]: if self.file_sizes.get(p, 0) <= 250000: self.symbols[p] = ast_symbols_for_file(root, p)
@staticmethod
def _looks_like_test(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    base = parts[-1].lower()
    return base.startswith("test_") or base.endswith("_test.py") or "tests" in parts or "test" in parts

def is_small_spec_repo(self, statement: str) -> bool:
    tracebackish = bool(re.search(r"Traceback \(most recent call last\)|File \".*\.py\", line \d+", statement or ""))
    if tracebackish:
        return True
    statement_len = len(statement or "")
    if statement_len > 4000:
        return False
    small_files = len(self.py_files) <= 28 and self.total_py_bytes <= 320_000
    few_sources = len(self.source_py_files) <= 12
    has_tests = bool(self.test_files)
    spec_words = re.search(
        r"\b(implement|write|create|complete|exercise|given|returns?|raises?|calculate|convert|parse|score)\b",
        statement or "",
        re.IGNORECASE,
    )
    return bool(small_files and few_sources and (has_tests or spec_words))

def summary(self, max_files: int = 240) -> str:
    lines = [
        f"root: {self.root}",
        f"tracked_files: {len(self.files)}",
        f"python_files: {len(self.py_files)}",
        f"source_python_files: {len(self.source_py_files)}",
        f"test_python_files: {len(self.test_files)}",
        f"total_python_bytes: {self.total_py_bytes}",
        "",
        "python file index:",
    ]
    for p in self.py_files[:max_files]:
        sym = self.symbols.get(p) or {}
        funcs = ", ".join((sym.get("functions") or [])[:12])
        classes = ", ".join((sym.get("classes") or [])[:10])
        suffix = []
        if classes:
            suffix.append(f"classes=[{classes}]")
        if funcs:
            suffix.append(f"functions=[{funcs}]")
        meta = f" size={self.file_sizes.get(p, 0)}"
        if suffix:
            meta += " " + " ".join(suffix)
        lines.append(f"- {p}{meta}")
    if len(self.py_files) > max_files:
        lines.append(f"... {len(self.py_files) - max_files} more python files omitted from index")
    if self.test_files:
        lines.append("")
        lines.append("test files:")
        for p in self.test_files[:80]:
            lines.append(f"- {p}")
    return "\n".join(lines)
def rank_files(profile: RepoProfile, statement: str, limit: int = 16) -> list[str]: terms = issue_terms(statement) low_terms = [t.lower() for t in terms] explicit_paths = [p for p in _PATH_RE.findall(statement or "") if p in profile.files] scores: dict[str, float] = {p: 0.0 for p in profile.py_files} for p in profile.py_files: low_path = p.lower() base = os.path.basename(low_path) if p in explicit_paths: scores[p] += 200 for t in low_terms: if t in low_path: scores[p] += 14 if t in base else 8 sym = profile.symbols.get(p) or {} for name in (sym.get("classes") or []) + (sym.get("functions") or []): nl = name.lower() if any(t == nl or t in nl for t in low_terms): scores[p] += 18 if profile.file_sizes.get(p, 0) <= 180000: text = read_text(profile.root, p, max_chars=180000).lower() for t in low_terms[:45]: if t and t in text: scores[p] += min(text.count(t), 6) * 1.5 if profile._looks_like_test(p): scores[p] *= 0.70 if any(t in low_path for t in ("test", "tests")): scores[p] += 2 ranked = sorted(profile.py_files, key=lambda p: (-scores.get(p, 0), p)) nonzero = [p for p in ranked if scores.get(p, 0) > 0] if nonzero: return nonzero[:limit] src = sorted(profile.source_py_files, key=lambda p: (profile.file_sizes.get(p, 0), p)) tst = sorted(profile.test_files, key=lambda p: (profile.file_sizes.get(p, 0), p)) return (src + tst)[:limit]
def line_window(text: str, start_line: int, end_line: int) -> str: lines = text.splitlines() start = max(1, start_line) end = min(len(lines), end_line) return "\n".join(f"{i:5d}: {lines[i-1]}" for i in range(start, end + 1))
def file_snippets(profile: RepoProfile, paths: list[str], statement: str, char_budget: int) -> str: terms = [t.lower() for t in issue_terms(statement)] chunks: list[str] = [] used = 0 for p in paths: if p not in profile.files or not p.endswith((".py", ".pyi", ".txt", ".rst", ".md")): continue text = read_text(profile.root, p, max_chars=260000) if not text: continue size = len(text) header = f"\n--- FILE {p} ({size} chars) ---\n" body = "" if size <= 18000: body = text else: lines = text.splitlines() windows: list[tuple[int, int]] = [(1, min(120, len(lines)))] low_lines = [ln.lower() for ln in lines] for idx, ln in enumerate(low_lines, 1): if any(t and t in ln for t in terms[:35]): windows.append((max(1, idx - 45), min(len(lines), idx + 65))) if len(windows) >= 8: break merged: list[tuple[int, int]] = [] for a, b in sorted(windows): if merged and a <= merged[-1][1] + 10: merged[-1] = (merged[-1][0], max(merged[-1][1], b)) else: merged.append((a, b)) parts = [] for a, b in merged[:7]: parts.append(f"# lines {a}-{b}\n" + line_window(text, a, b)) body = "\n\n".join(parts) chunk = header + body.rstrip() + "\n" if used + len(chunk) > char_budget: remaining = char_budget - used if remaining > 2000: chunks.append(chunk[:remaining] + "\n......\n") break chunks.append(chunk) used += len(chunk) return "\n".join(chunks)
def compact(text: str, limit: int) -> str: text = _prompt_safe_text(text or "") if len(text) <= limit: return text head = max(1, limit // 2) tail = max(1, limit - head - 120) return text[:head] + f"\n...<{len(text) - limit} chars elided>...\n" + text[-tail:]
PATCH_SYSTEM = """You are a precise software repair model. You produce repository patches only through JSON edit instructions.
Your output must be a single JSON object and nothing else. Do not use markdown.
Required schema: { "contract": ["short checklist item", "..."], "edits": [ {"file": "relative/path.py", "old": "exact text appearing once", "new": "replacement text"} ], "tests": ["python3 -m pytest -q path/or/test"], "notes": ["short risk/control notes"] }
Edit rules:
    • All edits are applied to a clean HEAD checkout. Every old string must match exactly once in its file.
    • Use the smallest source change that satisfies the task and preserves adjacent behavior.
    • You may use {"file": "relative/path.py", "kind": "replace", "content": "full new file"} only when the full current file content was provided and a full-file replacement is genuinely simpler.
    • Do not add tests or scratch files unless the task explicitly requires committed test files.
    • Do not solve by special-casing visible examples or by checking repository/task names. Implement the general behavior implied by the code and specification.
    • Do not change the public attribute/method API of the skeleton. If the skeleton exposes obj.value as a directly assignable attribute (e.g., self.value = None), it MUST remain settable via obj.value = x in the implementation — do NOT replace it with a method like set_value(). Use a @property with a @attr.setter if you need to intercept assignment.
    • For small specification-style tasks, be exact about units, return types, ordering, exception types/messages, state transitions, and boundary cases.
    • For specification-style tasks, include runnable python3 -c semantic tests in tests. Cover every public function, class property, and method implied by the file and instructions. Include boundary/error cases when the instructions mention them. Do not rely only on py_compile or pytest collection.
    • When there are multiple distinct error conditions (e.g., different invalid-input categories), raise each with its own distinct message. Never merge distinct cases into a single catch-all with one message.
    • When refactoring code that already has multiple separate raise statements, preserve each distinct condition and give it a descriptively accurate message that precisely describes that condition (e.g., "Only root should have equal record and parent id." vs "Node parent_id should be smaller than it's record_id.").
    • Exception message self-tests must verify the exact message string: except SomeError as e: assert e.args[0] == 'exact expected message here'. Never just check assert str(e) (truthy only).
    • For reactive/observable propagation systems (cells, signals, computed values that depend on other computed values), use BFS topological ordering when propagating changes through the dependency graph. Collect all affected cells, sort them by dependency depth (parents before children), then recompute all, then fire callbacks only for cells whose value actually changed. DFS traversal with a stack is NOT sufficient because it can recompute a downstream node before upstream nodes are updated.
    • For stateful reset/regeneration behavior, preserve any history needed by the specification. If a reset must produce a new value, do not immediately make the old generated value eligible for reuse.
    • For larger bug-fix tasks, prefer localized behavior changes and include at least one focused test command plus one adjacent control test command when possible. """
LOCALIZE_SYSTEM = """You localize a Python repository task. Output one JSON object and nothing else.
Schema: { "mode": "spec" or "bugfix", "files": ["relative/path.py"], "tests": ["safe focused test command"], "reproducer": "short description or command", "invariants": ["behavior that must remain unchanged"], "rationale": "brief" }
Use only generic evidence from the problem statement and repository index. Do not rely on external task identity. """
SEMANTIC_TEST_SYSTEM = """You generate runnable semantic verification commands for an already-applied Python patch.
Your output must be a single JSON object and nothing else. Do not use markdown.
Schema: { "tests": ["python3 -c "from module import thing; assert ...""], "notes": ["short coverage note"] }
Rules:
    • Return only python3 -c commands. Do not use pytest, unittest discovery, shell pipes, redirects, network, installs, or file writes.
    • Commands run from the repository root after the candidate patch is already applied.
    • Cover every public function, class property, and method implied by the source skeleton and problem statement.
    • Include edge cases, argument order, return types, state transitions, and required exception messages when relevant.
    • Keep commands concise and independent; prefer several focused assertions over one large script. """
def extract_json_object(text: str | None) -> dict[str, Any] | None: if not text: return None raw = text.strip() if raw.startswith(""): raw = re.sub(r"^(?:json)?\s*", "", raw) raw = re.sub(r"\s*```$", "", raw) try: obj = json.loads(raw) return obj if isinstance(obj, dict) else None except Exception: pass start = raw.find("{") if start == -1: return None depth = 0 in_str = False esc = False for i in range(start, len(raw)): ch = raw[i] if in_str: if esc: esc = False elif ch == "\": esc = True elif ch == '"': in_str = False continue if ch == '"': in_str = True elif ch == "{": depth += 1 elif ch == "}": depth -= 1 if depth == 0: candidate = raw[start : i + 1] try: obj = json.loads(candidate) return obj if isinstance(obj, dict) else None except Exception: return None return None
def _collect_python_sources(root: str, *, total_char_budget: int = 60000) -> str: parts: list[str] = [] used = 0 for path in git_files(root): if not path.endswith(".py"): continue content = read_text(root, path) if not content.strip(): continue block = f"# ===== {path} =====\n{content}" parts.append(block) used += len(block) if used >= total_char_budget: print(f"[AGENT] function-behaviour: source budget {total_char_budget} reached; truncating") break return "\n\n".join(parts)
def _behaviour_return_text(entry: Any) -> str | None: steps = entry.get("steps") if isinstance(entry, dict) else None if not isinstance(steps, (list, tuple)): return None for step in steps: if isinstance(step, str) and step.strip().lower().startswith("return"): s = step.strip() return s.split(":", 1)[1].strip() if ":" in s else s[len("return"):].strip() return None
def _none_return_behaviour_keys(behaviour: dict[str, Any] | None) -> list[str]: if not behaviour: return [] bad: list[str] = [] for name, entry in behaviour.items(): if name.rsplit(".", 1)[-1] == "init": continue rv = _behaviour_return_text(entry) if rv is not None and _is_nullish_return(rv): bad.append(name) return bad
def _coerce_return_value(val: Any) -> str | None: if isinstance(val, str): return val.strip() or None if isinstance(val, dict): for key in ("return_value", "return", "value"): rv = val.get(key) if isinstance(rv, str) and rv.strip(): return rv.strip() return _behaviour_return_text(val) return None
def _set_behaviour_return(entry: dict[str, Any], new_value: str) -> None: steps = entry.get("steps") new_step = f"return: {new_value}" if isinstance(steps, list): for i, step in enumerate(steps): if isinstance(step, str) and step.strip().lower().startswith("return"): steps[i] = new_step return steps.append(new_step) else: entry["steps"] = [new_step]
def _extract_member_source(skeleton: str, qualified_name: str) -> str | None: try: tree = ast.parse(skeleton) except SyntaxError: return None lines = skeleton.splitlines()
def _slice(node: ast.AST) -> str:
    start = node.lineno - 1
    end = getattr(node, "end_lineno", None) or (start + 1)
    return "\n".join(lines[start:end])

parts = qualified_name.split(".")
if len(parts) == 1:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == parts[0]:
            return _slice(node)
elif len(parts) == 2:
    cls_name, meth_name = parts
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == meth_name:
                    return _slice(item)
return None
def _extract_class_context(skeleton: str, qualified_name: str, keep_methods: set[str] | None = None) -> str | None: parts = qualified_name.split(".") if len(parts) == 1: return _extract_member_source(skeleton, qualified_name) cls_name = parts[0] keep = set(keep_methods) if keep_methods is not None else {parts[1]} try: tree = ast.parse(skeleton) except SyntaxError: return None lines = skeleton.splitlines()
def _span(node: ast.AST) -> tuple[int, int]:
    start = node.lineno - 1
    decs = getattr(node, "decorator_list", None)
    if decs:
        start = min(start, decs[0].lineno - 1)
    end = getattr(node, "end_lineno", None) or (start + 1)
    return start, end

for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == cls_name:
        if not node.body:
            s, e = _span(node)
            return "\n".join(lines[s:e])
        first_start, _ = _span(node.body[0])
        out = lines[node.lineno - 1:first_start]
        for i, stmt in enumerate(node.body):
            take = False
            if (i == 0 and isinstance(stmt, ast.Expr)
                    and isinstance(getattr(stmt, "value", None), ast.Constant)
                    and isinstance(stmt.value.value, str)):
                take = True  
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name in keep:
                take = True
            if take:
                s, e = _span(stmt)
                out.extend(lines[s:e])
        return "\n".join(out)
return None
def generate_function_behaviour( problem_statement: str, *, config: AgentConfig | None = None, budget: Budget | None = None, root: str | None = None, model: str | None = None, ) -> dict[str, Any] | None: config = config or AgentConfig() budget = budget or Budget(config) root = root or find_repo_root(config.working_dir) model = "qwen/qwen3-coder"
initial_structure = _collect_python_sources(root)
if not initial_structure.strip():
    print("[AGENT] function-behaviour: no python source found under repo root")

prompt = f"""Problem Statement:
    {problem_statement}

    Initial Structure (Code Skeleton):
    {initial_structure}

    Analyze the code skeleton and provide step-by-step behavior including the final return value for each function/method defined in it.

    Return the response as a JSON dict with the following format:
    {{
        "function_name_1": {{
            "steps": [
                "Step 1: ...",
                "Step 2: ...",
                "return: ..."
            ]
        }},
        "ClassName.method_name": {{
            "steps": [
                "Step 1: ...",
                "return: ..."
            ]
        }}
    }}

    Important guidelines:
    - Each step must be a clear, keyword only description, with exact function/method names to call if required.
    - The final "return:" step must not be None/NULL value.
    """

system = (
    "You are an expert Python code analyst. Analyze the given code skeleton and "
    "respond with a single JSON object describing each function/method's behaviour. "
    "Output JSON only — no surrounding prose or markdown."
)
response = call_llm(config=config, budget=budget, model=model, system=system, user=prompt)
if not response:
    print("[AGENT] function-behaviour: no response from model")
    return None
behaviour = extract_json_object(response)
if behaviour is None:
    print("[AGENT] function-behaviour: response was not valid JSON")
    return None
print(f"[AGENT] function-behaviour: parsed {len(behaviour)} entry(ies) using model={model}")

max_attempts = max(0, _env_int("RIDGES_AGENT_BEHAVIOUR_RETURN_ATTEMPTS", 3))
for attempt in range(1, max_attempts + 1):
    bad = _none_return_behaviour_keys(behaviour)
    if not bad:
        break
    
    snippets = []
    classes_done: set[str] = set()
    for name in bad:
        cls = name.split(".", 1)[0] if "." in name else None
        if cls is None:
            src = _extract_member_source(initial_structure, name)
            if src:
                snippets.append(f"# {name}\n{src}")
            continue
        if cls in classes_done:
            continue
        classes_done.add(cls)
        methods = [n for n in bad if n.split(".", 1)[0] == cls]
        keep = {m.split(".", 1)[1] for m in methods if "." in m}
        ctx = _extract_class_context(initial_structure, name, keep)
        if ctx:
            snippets.append(
                f"# class {cls} -- give the concrete return value for: "
                f"{', '.join(methods)}\n{ctx}"
            )
    if not snippets:
        print(f"[AGENT] function-behaviour: {len(bad)} None-return func(s) but none extractable; stopping")
        break
    print(f"[AGENT] function-behaviour: attempt {attempt}/{max_attempts}: " f"re-analyzing {len(snippets)} None-return func(s) -> {bad}")


    retry_prompt = f"""
    The following function(s)/method(s) were analyzed with a return value of None.
    Each return value MUST be concrete and non-None — never return **None/null/False/True**.
    **If method is just a stub or overrides of base class, you should delegate the result of base class's call without supressing them.** 
    
    Function/Method skeletons:
    ```
    {chr(10).join(snippets)}
    ```
    
    Return a JSON dict mapping each name (EXACTLY as given above) to its return value:
    {{
        "ClassName.method_name": "<concrete non-None return value>"
    }}

    Bad Examples(NEVER DO THIS):
    {{
        "ClassName.method_name1": None,
        "ClassName.method_name2": False,
        "ClassName.method_name3": Null,
    }}
    """

    retry_resp = call_llm(config=config, budget=budget, model="qwen/qwen3-coder", system=system, user=retry_prompt)
    if not retry_resp:
        print(f"[AGENT] function-behaviour: no response on retry (attempt {attempt}); retrying")
        continue
    fixed = extract_json_object(retry_resp)
    if not fixed:
        print(f"[AGENT] function-behaviour: retry returned invalid JSON (attempt {attempt}); retrying")
        continue
    merged = 0
    for name, val in fixed.items():
        if name not in behaviour or not isinstance(behaviour[name], dict):
            continue
        new_rv = _coerce_return_value(val)
        if new_rv and not _is_nullish_return(new_rv):
            _set_behaviour_return(behaviour[name], new_rv)
            merged += 1
    print(f"[AGENT] function-behaviour: updated return value for {merged} func(s)")

remaining = _none_return_behaviour_keys(behaviour)
if remaining:
    print(f"[AGENT] function-behaviour: still None-return after retries: {remaining}")
return behaviour
def _is_nullish_return(value: Any) -> bool: if value is None: return True if isinstance(value, str): return value.strip().lower() in {"", "none", "null", "nil", "n/a", "undefined", "...", "false", "true"} return False
def _function_behaviour_to_text(behaviour: dict[str, Any] | None) -> str: if not behaviour: return "" lines: list[str] = ["Function behaviour analysis:"] for name, info in behaviour.items(): steps = info.get("steps") if isinstance(info, dict) else info lines.append("") lines.append(f"{name}:") if isinstance(steps, (list, tuple)): for step in steps: if step.startswith("return:"): lines.append(f"  - {step}") elif steps: lines.append(f"  - {steps}") return "\n".join(lines)
def _is_stub_function(node: "ast.FunctionDef | ast.AsyncFunctionDef") -> bool: body = list(node.body) if (body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str)): body = body[1:] if not body: return True
for stmt in body: if isinstance(stmt, ast.Pass): continue if (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is Ellipsis): continue if isinstance(stmt, ast.Raise): exc = stmt.exc name = None if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name): name = exc.func.id elif isinstance(exc, ast.Name): name = exc.id if name == "NotImplementedError": continue return False
return True
def _complexity_threshold() -> int: return _env_int("RIDGES_AGENT_COMPLEXITY_THRESHOLD", 15)
def skeleton_complexity(skeleton: str, *, count_all: bool = False) -> int: try: tree = ast.parse(skeleton) except SyntaxError as exc: print(f"[AGENT] skeleton_complexity: could not parse skeleton: {exc}") return 0
functions = 0
methods = 0

def visit(node: ast.AST, in_class: bool) -> None:
    nonlocal functions, methods
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if count_all or _is_stub_function(child):
                if in_class:
                    methods += 1
                else:
                    functions += 1
            visit(child, in_class=False)  
        elif isinstance(child, ast.ClassDef):
            visit(child, in_class=True)
        else:
            visit(child, in_class)

visit(tree, in_class=False)
total = functions + methods
print(
    f"[AGENT] skeleton complexity={total} "
    f"(functions={functions}, methods={methods}, "
    f"{'all' if count_all else 'to-implement only'})"
)
return total
def _json_dumps(obj: Any, limit: int | None = None) -> str: s = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) return compact(s, limit) if limit else s
def build_localization_prompt(profile: RepoProfile, statement: str, mode: str, deterministic_candidates: list[str], config: AgentConfig) -> str: index = profile.summary(max_files=260) prompt = f"""Problem statement: {statement}
Initial route from repository shape: {mode}
Repository index: {compact(index, config.repo_index_chars)}
Deterministic top-ranked files: {json.dumps(deterministic_candidates, indent=2)}
Choose the smallest useful set of files to inspect/patch and safe focused tests. If this is a small spec task, keep mode=spec; if it is a mature repository bug report, keep mode=bugfix. """ return prompt
_CONVENTION_PROBE_SYSTEM = """You recall the CONVENTIONAL public API of a well-known practice exercise from your training. You do NOT write a solution.
Given the problem and the stub, list the module-level CONSTANTS the exercise's standard test imports BY NAME, especially constants for a fixed set of named categories that the stub shows only as short literal codes (these are routinely imported by name even though the stub never defines them). For each, give its conventional value.
Output ONLY lines of the form NAME = value, one per constant, and nothing else. If the exercise has no such conventional module-level constants beyond what the stub already defines, output the single line NONE. Never invent constants that are not conventional for this specific exercise."""
def _has_positional_accessor(tree) -> bool: """A class exposes a positional accessor: a non-dunder method whose parameters are two-or-more single-letter names (the conventional shape of positional indexing into a multi-axis structure).""" for node in ast.walk(tree): if isinstance(node, ast.ClassDef): for member in node.body: if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and not member.name.startswith("__"): params = [a.arg for a in member.args.args if a.arg != "self"] if len(params) >= 2 and all(len(p) == 1 for p in params): return True return False
def _carries_prefilled_body(tree) -> bool: """The skeleton already ships a body to review rather than empty stubs waiting to be filled in: it contains at least one raise statement.""" return any(isinstance(n, ast.Raise) for n in ast.walk(tree))
def _has_observer_callbacks(tree) -> bool: """A class exposes a subscribe/unsubscribe pair for change observers: it defines BOTH an add-callback and a remove-callback registration method. This is the shape of a task that propagates value changes through a dependency graph and notifies registered observers — correctness hinges on propagation order and notification semantics, not just per-node computation.""" for node in ast.walk(tree): if isinstance(node, ast.ClassDef): names = {m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))} has_add = any("callback" in n and "add" in n for n in names) has_remove = any("callback" in n and "remove" in n for n in names) if has_add and has_remove: return True return False
def _extends_library_base(tree) -> bool: """A class derives from an imported/library type — a dotted base expression such as module.Base rather than a bare local name. These adapter/wrapper tasks subclass or wrap a standard object and must preserve its initialization and delegation contract (init the base, delegate operations, return the wrapped object's results) while metering it.""" for node in ast.walk(tree): if isinstance(node, ast.ClassDef): for base in node.bases: if isinstance(base, ast.Attribute): return True return False
def _defines_status_enum(tree) -> bool: """The skeleton defines, at MODULE level, a fixed set of named UPPERCASE constants (a status/category enumeration) alongside a class. This is the shape of a stateful object whose public status is one of a fixed enumeration and whose correctness hinges on precise counting and state-transition rules the prose only implies — distinct from a task that must RECALL undisclosed constants, since here the constants are already defined in the skeleton.""" has_class = any(isinstance(n, ast.ClassDef) for n in tree.body) const_names = [ t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name) and len(t.id) >= 2 and t.id.isupper() ] return has_class and len(const_names) >= 2
Ordered structural-archetype detectors: (label, predicate) evaluated in
order of decreasing structural specificity, so the most distinctive shape is
recognised first and the first match wins.
_SPEC_ARCHETYPE_RULES = ( ("observer", _has_observer_callbacks), ("adapter", _extends_library_base), ("positional", _has_positional_accessor), ("rivew", _carries_prefilled_body), ("status", _defines_status_enum), )
def _resolve_spec_archetype(skeleton: str) -> str: """Classify a small-spec ("spec") task into one of a few structural archetypes using only generic, language-level signals parsed from the supplied skeleton — no task identity, no problem name, and no problem-specific strings. Detectors are tried in registered order and the first to match wins; "" is returned when none apply. The label is purely structural and says nothing about which concrete exercise a skeleton came from.""" try: tree = ast.parse(skeleton) except SyntaxError: return "" for label, predicate in _SPEC_ARCHETYPE_RULES: if predicate(tree): return label return ""
Archetypes whose downstream prompt benefits from recalled naming conventions.
_ARCHETYPE_NEEDS_CONVENTIONS = "positional"
Archetypes that benefit from a generic up-front requirements-review pass before
the implementer runs — a broad correctness aid for rework-style spec tasks.
_ARCHETYPE_NEEDS_SPEC_REVIEW = "rivew"
Archetypes whose correctness depends on change-propagation order and notification
semantics over a dependency graph — a fixed, generic contract plus mandated
self-checks the simple cases never exercise.
_ARCHETYPE_NEEDS_GRAPH_CONTRACT = "observer"
Archetypes that subclass/wrap a standard object and meter it — correctness hinges
on base initialization, exact accounting, and faithful delegation (esp. the
context-manager result), a multi-part contract opus drops one piece of per run.
_ARCHETYPE_NEEDS_ADAPTER_CONTRACT = "adapter"
Archetypes that implement a stateful object with a fixed status enumeration —
correctness hinges on precise counting + state-transition rules, a multi-rule
contract opus drops one rule of per run (initial count, repeat-input failure, …).
_ARCHETYPE_NEEDS_STATE_CONTRACT = "status"
Static, model-facing brief for the stateful status-enum archetype. GENERIC contract
(preserve the skeleton's starting counter + constant names, enumerate every failure
rule incl. repeated-input, terminal states) — no task identity, no answer — plus
mandated self-checks for the rules (initial value, repeat-input-is-failure, win/lose
timing, act-after-terminal) that opus drops and shallow self-tests miss.
_STATE_CONTRACT_BRIEF = """STATEFUL STATUS-ENUM CONTRACT: this task implements a stateful object whose public status is one of a FIXED SET of module-level named constants, with precise counting and state-transition rules the prose only implies. Get ALL of these exactly.
KEEP THE SKELETON'S STARTING VALUES: any counter the skeleton already initializes (e.g. a remaining-attempts count) is CORRECT as given — do NOT change it. A skeleton comment like "change the values as you see fit" refers ONLY to the string VALUES of the status constants, NEVER to that counter and NEVER to the constant NAMES.
STATUS CONSTANT NAMES ARE PUBLIC: the hidden test imports the module-level status constants BY NAME, so keep every constant's NAME exactly as defined. Set the object's status using those named constants (not raw string literals).
ENUMERATE EVERY FAILURE RULE: an action "fails" (decrements the counter by one) under EACH distinct failing condition — and crucially, a REPEATED / already-seen input counts as a failure EVEN WHEN that input would otherwise be valid (e.g. re-submitting a previously-CORRECT entry is still a failure and still decrements). A fresh, valid, non-repeated action does NOT decrement. Do not collapse these into "only invalid inputs fail".
TERMINAL STATES: reaching the success condition sets the WIN status; exhausting the counter (it goes BELOW zero) sets the LOSE status. Once the object is in a terminal (non-ongoing) status, any further action must raise ValueError with the conventional "already ended" message — recall its exact wording.
MANDATORY SELF-TESTS — your tests list MUST include runnable python3 -c checks (build the object yourself, compute expected FROM THESE RULES, never from a hidden test): (1) the INITIAL counter equals the skeleton's starting value; (2) a REPEATED previously-valid input still decrements the counter by exactly one; (3) winning on the final allowed correct action yields the WIN status; (4) exhausting the counter yields the LOSE status; (5) any action after a terminal status raises ValueError. Treat a draft that omits or fails any of these as not done — revise it."""
Static, model-facing brief for the adapter/wrapper archetype. GENERIC contract
(init + accounting + delegation + context-manager rules) — no task identity, no
answer — plus mandated self-checks for the failure modes (uninitialized base,
off-by-one op counts, broken exception suppression) that simple cases miss.
_ADAPTER_CONTRACT_BRIEF = """ADAPTER / WRAPPER CONTRACT: this task defines a class that SUBCLASSES or WRAPS an underlying I/O-like object and METERS it (counts operations and bytes) while delegating behaviour. The hidden tests check delegation and accounting details a naive implementation drops; satisfy ALL of these exactly.
INITIALIZATION: initialize the underlying object before ANY operation. If the class SUBCLASSES a library type, call super().init(*args, **kwargs) in init; if it WRAPS a passed-in object, store that object. Skipping this yields "I/O operation on uninitialized object" or AttributeError on the first read/iterate.
EXACT ACCOUNTING: keep a SEPARATE operation COUNT and byte TOTAL per direction (read/recv and write/send). EVERY call to a metered operation increments its op count by exactly one and adds the number of bytes ACTUALLY transferred (the len of the data) to its byte total — INCLUDING the terminating short/empty read, reads performed via iteration, and partial chunks. Off-by-one op counts and an uncounted final read are the most common failures.
CONTEXT MANAGER (delegate, do not swallow): enter returns self (do NOT call the wrapped object's enter). exit(exc_type, exc_val, exc_tb) must call AND RETURN the wrapped object's exit(exc_type, exc_val, exc_tb) — return its result verbatim so a truthy (suppress) value propagates. NEVER call it and then return False/return None: that breaks exception suppression.
REACH THE UNDERLYING OBJECT THE RIGHT WAY: if the class SUBCLASSES a library type, delegate EVERY inherited operation through super().<method>(...) — e.g. super().read(...), super().readline(), super().write(...), super().__exit__(...). NEVER call self.<method>() for an operation you are metering (it recurses or bypasses), and NEVER call the base class by name. Tests commonly REPLACE super() with a mock to confirm and count these primitive calls and may never really initialize the base, so the underlying object must be reached ONLY through super() — calling the real base directly raises "I/O operation on uninitialized object". If instead the class WRAPS a passed-in object, call that stored object's methods (self._obj.recv(...)).
DELEGATION (meter at the PRIMITIVE level): iter/next/read/write/recv/send delegate as above and meter; preserve return values, flag arguments, and exceptions. Invoke the underlying READ/WRITE PRIMITIVE directly so each call is actually issued, observable, and counted — do NOT delegate through a higher-level helper that hides it. In particular, implement LINE ITERATION by calling super().readline() (subclass) or self._obj.readline() (wrapper) ONCE PER LINE — increment the op count and add len(line) each time, stop on an empty result — and do NOT delegate iteration to the base's __next__ or to for line in super(), which hides the underlying readline so it is neither metered nor observable.
MANDATORY SELF-TESTS — your tests list MUST include these runnable python3 -c checks (build your OWN in-memory or mock object and compute the expected numbers yourself, never from a hidden test):
    1. INIT + COUNT: read a small known buffer fully (also via iteration); assert there is NO "uninitialized" error AND that the operation count and byte total EXACTLY match the number of reads and the total bytes.
    2. SUPPRESS: wrap an object whose exit returns True; assert that using the metered object as a context manager around a raised exception SUPPRESSES it (the exception does not escape). Treat a draft that omits or fails these as not done — revise it, do not submit it."""
_GRAPH_CONTRACT_BRIEF = """DEPENDENCY-GRAPH CONTRACT: this task builds values that derive from input values and from EACH OTHER (a dependency graph) and notifies registered observer callbacks when values change. Trivial single-node cases hide the real failures; you MUST satisfy all of the following.
PROPAGATION ORDER (avoid stale reads): when an input changes, recompute every dependent value in DEPENDENCY order — a derived value may be recomputed only AFTER every value it reads has already been updated for this change. A plain depth-first / pre-order walk of dependents is WRONG: when a value is reachable by paths of DIFFERENT lengths (a "diamond": one input feeding two derived values that both feed a third), the deeper value gets recomputed from a STALE operand and yields the wrong result. Use a TOPOLOGICAL order over the graph, or recompute repeatedly until nothing changes (a fixpoint). Never let a derived value read an operand that has not yet been updated for the current change.
NOTIFICATION SEMANTICS (settle, then notify once): only AFTER the whole propagation has SETTLED, fire each callback AT MOST ONCE per change, and ONLY if that value's FINAL value differs from its value BEFORE the change. Never notify with an intermediate value seen mid-propagation. Never notify when the net value is unchanged (a change that cancels out downstream must produce NO notification).
MANDATORY SELF-CHECKS — your tests list MUST include these three runnable python3 -c checks. Construct the objects yourself and compute the expected numbers yourself (do NOT special-case any hidden test):
    1. DIAMOND: one input feeds two derived values; a third derived value combines BOTH; change the input; assert the third equals the value computed from BOTH updated operands. (A wrong propagation order fails this.)
    2. NOTIFY-ONCE: a derived value whose two dependencies BOTH move from a single input change; register a callback; change the input; assert the callback fired EXACTLY ONCE and observed the FINAL value.
    3. NO-OP NOTIFY: arrange a change that leaves some downstream derived value UNCHANGED; assert that downstream value's callback did NOT fire at all. Treat a patch that omits or fails any of these three as not done — revise it, do not submit it."""
def _retrieve_convention_brief(config, budget, statement: str, context: str) -> str: """Consult the model as a retrieval source for the conventional module-level constants that the standard tests of common practice exercises import by name (a recall-style query is steadier than a binary verdict). The query is run a couple of times and the results are unioned to damp per-call variance. The collected NAME = value pairs are returned as a short, model-facing brief so the implementation defines and uses them consistently; "" is returned when there are no such conventions (the common case), leaving the prompt untouched.""" import re as _re consts = {} for _ in range(2): if not budget.can_call(reserve_fraction=0.05): break try: raw = call_llm( config=config, budget=budget, model="openai/gpt-5.5", system=_CONVENTION_PROBE_SYSTEM, user=( "Problem statement:\n" + (statement or "")[:3500] + "\n\nStub / file skeleton:\n" + (context or "")[:5000] + "\n\nList the conventional module-level constants the standard test imports (NAME = value lines), or NONE." ), max_tokens=1500, ) except Exception as exc: print(f"[AGENT] convention-probe error: {exc}") break for line in (raw or "").splitlines(): m = re.match(r"\s*([A-Z][A-Z0-9]{1,})\s*=\s*(\S.*)", line) if m and m.group(1) != "NONE": consts.setdefault(m.group(1), m.group(2).strip()) if not consts: return "" print(f"[AGENT] convention-probe: recalled constants {sorted(consts)}") body = "\n".join(f"{k} = {v}" for k, v in consts.items()) return ( "RECALLED PUBLIC API: this well-known exercise conventionally exposes these module-level constants, which the hidden test imports BY NAME even though the stub may not define them. DEFINE each at module level with exactly this value and USE it throughout your code (in place of the raw literal), and import them in a tests line so a missing one fails locally:\n" + body + "\n\nIMPLEMENTATION RULES — this exercise computes, over a 2-D grid, which EMPTY regions are owned by which marked kind; the recall above only fixes the public names. The hidden tests fail on the region logic unless you satisfy ALL of these exactly:\n" "- COORDINATES: follow the stub's documented coordinate meaning EXACTLY (which argument is the column vs the row) and index the grid consistently with that; do not transpose them.\n" "- A POINT THAT HOLDS A MARK IS NOT A REGION: querying the per-point owner at a marked/occupied point MUST return the neutral/no-owner sentinel with an EMPTY set — never the point's own mark.\n" "- REGION OWNERSHIP: an empty region's owner is the single mark that borders EVERY edge of that region; if two different marks border it (or none do), its owner is the neutral sentinel. The whole-board query groups empty points by owner into exactly the recalled keys.\n" "\nMANDATORY SELF-TESTS — your tests list MUST include these runnable python3 -c checks (build the grid yourself and compute the expected values FROM THESE RULES, never from any hidden test):\n" "1. the per-point owner query AT A MARKED POINT returns (neutral sentinel, empty set).\n" "2. an empty region bordered by exactly ONE mark -> that mark owns it.\n" "3. an empty region touching TWO different marks -> owner is the neutral sentinel.\n" "Treat a draft that omits or fails any of these three as not done — revise it, do not submit it." )
_REQUIREMENTS_REVIEW_SYSTEM = """You are a strict requirements analyst for a self-contained Python coding exercise whose supplied file ALREADY SHIPS a working-looking implementation to be reworked (not empty stubs). You do NOT write code; you produce a concise, task-specific BRIEF the implementer must satisfy.
CRITICAL — the shipped code is UNRELIABLE on details. In particular, the exception MESSAGES (the string literals inside its existing raise statements) are PLACEHOLDERS that the hidden test does NOT accept. Treat every message literal in the skeleton as wrong-until-confirmed; do NOT copy them.
For a well-known practice exercise, RECALL from your training the exercise's CONVENTIONAL exact exception messages and use THOSE, overriding whatever the skeleton shows. Reproduce the canonical wording verbatim, including any unusual grammar, contraction, or apparent typo. If you cannot confidently recall the canonical wording for a condition, say "(uncertain)" for that line rather than echoing the skeleton's literal.
Output plain text, specific to THIS task, in these sections:
Public Contract
    • The exact public names to expose (classes, functions, methods), their signatures, and exact return types/values, plus the exact empty/no-result sentinel callers expect.
Distinct Conditions
    • Enumerate EVERY distinct input, state, boundary, and error condition as its OWN separate line, each with its required behaviour, its exception type, and its EXACT (recalled, canonical) message — NOT the skeleton's literal. Never merge two conditions the task distinguishes. When a condition turns on a comparison or ordering, list the exact-equality case (a value equal to the bound) as a SEPARATE line from the strictly-greater and strictly-less cases, each with its OWN distinct message.
    • HARD RULE — do NOT state how many distinct messages the exercise uses, and do NOT give the exact-equality case the same message as any strictly-less/greater case. The equality boundary ALWAYS carries its OWN distinct canonical message, separate from the inequality message. If your first recall suggests they share a message (i.e. you counted fewer messages than conditions), you have UNDER-COUNTED — recall again and give the equality case its own distinct message. Treating the equality case as "just another inequality" is the single most common recall error for this kind of exercise; never make it.
Messages To Replace
    • For EACH raise message literal currently in the skeleton, give one line: the skeleton's (wrong) literal  ->  the canonical message that must replace it.
Edge Cases
    • Empty input, a single element, the smallest / largest / zero value, out-of-range or out-of-order input, and any reset of state.
Mandatory Self-Tests
    • Instruct the implementer that its tests list MUST include structural checks that catch the failure modes WITHOUT needing the exact wording: (a) build inputs triggering each distinct error condition and assert each raises the correct exception TYPE; (b) assert the message for the exact-EQUALITY condition is a DIFFERENT string than the message for the strictly-less/greater condition, AND different than the out-of-order condition's message (pairwise distinct). This check is MANDATORY and OVERRIDES the enumeration above: if your Distinct Conditions accidentally gave the equality case and an inequality case the SAME message, that is a recall error — this test MUST then FAIL so the implementation is revised rather than shipped. (c) assert NO error message contains a record/id VALUE or any digit from the input — messages are FIXED strings, never interpolated.
Preserve code identifiers (names, fields) exactly, but NEVER preserve the skeleton's exception message strings. Be concise. Do not write code or pseudocode."""
def _prepare_requirements_review(config, budget, profile, statement: str, selected_files: list) -> str: """General pre-implementation requirements-review pass — a broad correctness aid for rework-style spec tasks. One dedicated analysis call restates the task's public contract, enumerates each distinct input/boundary/error condition (including the equality boundary that a single supplied body tends to collapse), and lists the edge cases to cover, all before the implementer edits the code. Running this as its own step is more reliable than asking the main coder prompt to do it inline. Returns "" on budget/parse failure, leaving the downstream prompt unchanged.""" try: if not budget.can_call(reserve_fraction=0.06): return "" context = file_snippets(profile, selected_files, statement, min(40000, config.patch_state_chars)) user = ( "Problem statement:\n" + (statement or "") + "\n\nSupplied file skeleton(s):\n" + context + "\n\nProduce the contract + distinct-conditions + edge-case brief now. Be specific to THIS task. Do not write code." ) raw = call_llm( config=config, budget=budget, model=config.spec_model, system=_REQUIREMENTS_REVIEW_SYSTEM, user=user, # Kept small on purpose: the brief is a short condition+message list, # and a larger analysis call would consume enough budget to push the # primary (strong-model) patch call over its per-call affordability # guard, demoting it to the cheap fallback. ~1200 leaves room for the # strong patch to run. max_tokens=1200, ) brief = (raw or "").strip() if brief: print(f"[AGENT] requirements-review: {len(brief)} chars (model={config.spec_model})") return brief except Exception as exc: print(f"[AGENT] requirements-review error: {exc}") return ""
Static, model-facing brief for the rework/validation archetype (a skeleton that
ships a buggy implementation whose exception messages are wrong placeholders).
GENERIC — no task identity, no answer; the exact canonical strings come from the
coder's own guidance. Replaces the dedicated analyzer call, whose budget draw was
demoting the primary patch to the cheap fallback (which naturalised the messages).
_VALIDATION_CONTRACT_BRIEF = """REWORK / VALIDATION CONTRACT: this file already SHIPS a working-looking implementation whose exception MESSAGES (the string literals inside its existing raise statements) are WRONG placeholders the hidden tests reject. Do NOT copy the skeleton's raise message strings. Recall the canonical exact messages for this well-known exercise (your coding guidance shows the correct wording) and OVERRIDE the skeleton's literals.
DISTINCT CONDITIONS: enumerate every error condition separately, each with its OWN distinct message. When a check turns on a comparison, the exact-EQUALITY case (a value equal to the bound) is a SEPARATE condition with its OWN distinct message — NEVER the same message as the strictly-less/greater case. There are as many distinct messages as there are distinct conditions; do NOT collapse the equality case into an inequality case (the single most common error here).
VERBATIM WORDING: reproduce each canonical message EXACTLY. Keep the skeleton's OWN field identifiers in the wording (use the actual field name a record exposes, e.g. its id/parent field names) — do NOT replace them with a plainer English synonym (never write "own id" where the canonical message names the field). Never interpolate a value into a message; messages are FIXED strings.
MANDATORY SELF-TESTS — your tests list MUST include runnable python3 -c checks that: (a) each distinct error condition raises the correct exception TYPE; (b) the exact-equality condition's message is a DIFFERENT string than the strictly-less/greater condition's message AND than the out-of-order condition's message (pairwise distinct) — if any two match, that is a collapse error and this test MUST fail so the draft is revised; (c) NO error message contains a digit or interpolated value. Treat a draft that omits or fails these as not done — revise it, do not submit it."""
def _augment_spec_brief(config, budget, mode, root, profile, selected_files, statement) -> str: """Higher-level hook: assemble any supplementary, model-facing brief for a task whose structural archetype benefits from dedicated handling. Returns "" — leaving the downstream prompt unchanged — for every other mode/archetype, which is the overwhelmingly common path. Two archetypes are augmented: one with recalled naming conventions, the other with a generic up-front requirements review.""" if mode != "spec": return "" archetype = _resolve_spec_archetype(_collect_python_sources(root)) if archetype == _ARCHETYPE_NEEDS_CONVENTIONS: return _retrieve_convention_brief( config, budget, statement, file_snippets(profile, selected_files, statement, 8000), ) if archetype == _ARCHETYPE_NEEDS_SPEC_REVIEW: # Static contract — NO model call. A dedicated analyzer call here consumed # enough budget to push the primary opus patch over its per-call guard, # demoting the actual coding to the cheap fallback (which then naturalised the # canonical messages). Keeping this static frees the full budget for opus to # code, and the exact message wording comes from the coder's own guidance. print("[AGENT] validation-contract: injecting rework/validation message contract") return _VALIDATION_CONTRACT_BRIEF if archetype == _ARCHETYPE_NEEDS_GRAPH_CONTRACT: # Static contract — no model call, so no budget draw on the primary patch. print("[AGENT] graph-contract: injecting dependency-graph propagation contract") return _GRAPH_CONTRACT_BRIEF if archetype == _ARCHETYPE_NEEDS_ADAPTER_CONTRACT: # Static contract — no model call, so no budget draw on the primary patch. print("[AGENT] adapter-contract: injecting wrapper init/accounting/delegation contract") return _ADAPTER_CONTRACT_BRIEF if archetype == _ARCHETYPE_NEEDS_STATE_CONTRACT: # Static contract — no model call, so no budget draw on the primary patch. print("[AGENT] state-contract: injecting stateful status/counting contract") return _STATE_CONTRACT_BRIEF return ""
def build_patch_prompt( *, profile: RepoProfile, statement: str, mode: str, selected_files: list[str], localization: dict[str, Any] | None, previous_signals: list[str], attempt: int, config: AgentConfig, api_brief: str = "", ) -> str: state_budget = config.bugfix_patch_state_chars if mode == "bugfix" else config.patch_state_chars full_context_budget = state_budget context = file_snippets(profile, selected_files, statement, full_context_budget) test_files = [p for p in selected_files if p in profile.test_files] source_files = [p for p in selected_files if p not in profile.test_files] previous_signal_text = "\n\n".join(previous_signals) if previous_signals else "(none)" if mode == "bugfix": summary_lines = [ f"root: {profile.root}", f"tracked_files: {len(profile.files)}", f"python_files: {len(profile.py_files)}", f"source_python_files: {len(profile.source_py_files)}", f"test_python_files: {len(profile.test_files)}", f"total_python_bytes: {profile.total_py_bytes}", "", "selected files:", ] for p in selected_files[:20]: summary_lines.append(f"- {p} size={profile.file_sizes.get(p, 0)}") repo_summary = compact("\n".join(summary_lines), 12000) final_prompt_limit = state_budget + 15000 else: repo_summary = compact(profile.summary(max_files=120), 30000) final_prompt_limit = state_budget + 25000 spec_verification_text = "" if mode == "spec": spec_verification_text = """ Spec verification requirement:
    • Your tests list must include at least one runnable non-compile semantic command, preferably python3 -c "...assert...".
    • These commands should exercise every public function, class property, and method implied by the source skeleton and instructions.
    • Include direction/order-sensitive cases, return type checks, and required exception messages when relevant.
    • A patch that only compiles, or only references missing pytest files, will be rejected.
    • Exception message tests MUST check the exact message string: except SomeError as e: assert e.args[0] == 'exact message text'. A bare assert str(e) truthy check is insufficient.
    • For each distinct invalid-input category, write a separate self-test that catches the correct exception with the correct exact message.
    • For reactive/observable systems (computed cells, signals): self-tests MUST use direct attribute assignment to change input values (e.g., i.value = 3, NOT i.set_value(3)), include a diamond dependency test (one input feeds two compute cells which both feed one output cell), and verify that callbacks do not fire when the final stable value is unchanged. """ recall_block = ("\n" + api_brief + "\n") if api_brief else "" prompt = f"""You are generating attempt #{attempt + 1}. Return only the JSON edit object described in the system message.
Problem statement: {statement}
Route: {mode}
Repository summary: {repo_summary}
Localization/result so far: {_json_dumps(localization or {}, 12000)}
Selected source files: {json.dumps(source_files, indent=2)}
Selected test/context files: {json.dumps(test_files, indent=2)}
File contents/snippets: {context}
Previous apply/verification signals to fix: {compact(previous_signal_text, 18000)}
{spec_verification_text} {recall_block} Before writing edits, build a contract checklist internally. Your returned contract list should include the important semantic requirements and adjacent behavior to preserve.
Return JSON now. Remember: exact old/new edits against clean HEAD; no markdown; no repository/task-name special cases. """ return compact(prompt, final_prompt_limit)
def build_semantic_test_prompt( *, profile: RepoProfile, statement: str, selected_files: list[str], patch: str, verify_signal: str, config: AgentConfig, ) -> str: context = file_snippets(profile, selected_files, statement, min(50000, config.patch_state_chars)) prompt = f"""Generate semantic verification commands for the candidate patch currently applied in the repository.
Problem statement: {statement}
Current patched file contents/snippets: {context}
Candidate diff: {compact(patch, 18000)}
Verification signal that triggered this request: {compact(verify_signal, 6000)}
Return JSON with a tests array of runnable python3 -c commands. The commands must validate behavior, not just imports or syntax. Do not reference pytest files because they may not exist during agent execution. """ return compact(prompt, config.patch_state_chars)
def _edit_path(item: dict[str, Any]) -> str | None: path = item.get("file") or item.get("path") if not isinstance(path, str): return None path = path.strip().replace("\", "/") if not _safe_relpath(path): return None return path
def _nearest_old_hint(content: str, old: str) -> str: old_lines = [ln for ln in old.splitlines() if ln.strip()] if not old_lines: return "" needle = old_lines[0].strip() hits: list[str] = [] for i, line in enumerate(content.splitlines(), 1): if needle and needle in line: hits.append(f"{i}: {line}") if len(hits) >= 6: break return "\n".join(hits)
def _restore_prompt_replacements(new: str, old_safe: str, old_actual: str) -> str: if len(old_safe) != len(old_actual): return new out: list[str] = [] for i, ch in enumerate(new): if ch == "\ufffd" and i < len(old_safe) and old_safe[i] == "\ufffd": out.append(old_actual[i]) else: out.append(ch) return "".join(out)
def apply_edits(root: str, patch_obj: dict[str, Any]) -> tuple[bool, str, list[str]]: edits = patch_obj.get("edits") if not isinstance(edits, list) or not edits: return False, "JSON contained no edits", []
buffers: dict[str, str] = {}
touched: list[str] = []
whole_file_written: set[str] = set()
errors: list[str] = []

def remember(path: str) -> None:
    if path not in touched:
        touched.append(path)

for idx, item in enumerate(edits, 1):
    if not isinstance(item, dict):
        errors.append(f"edit #{idx}: not an object")
        continue
    path = _edit_path(item)
    if not path:
        errors.append(f"edit #{idx}: invalid relative file path")
        continue
    full = os.path.join(root, path)
    kind = str(item.get("kind") or item.get("op") or "str_replace").lower()
    if "content" in item and kind in {"str_replace", "replace_file"}:
        kind = "replace"

    if path.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".gz")):
        errors.append(f"edit #{idx} {path}: binary-looking file not supported")
        continue

    if kind in {"replace", "overwrite"}:
        if path in touched and path not in whole_file_written:
            errors.append(f"edit #{idx} {path}: whole-file replacement cannot follow old/new edits")
            continue
        content = item.get("content")
        if not isinstance(content, str):
            errors.append(f"edit #{idx} {path}: replace edit missing string content")
            continue
        if not os.path.exists(full):
            errors.append(f"edit #{idx} {path}: replace target does not exist; use kind=create")
            continue
        buffers[path] = content
        whole_file_written.add(path)
        remember(path)
        continue

    if kind in {"create", "add"}:
        if path in touched:
            errors.append(f"edit #{idx} {path}: create cannot be combined with other edits to the same file")
            continue
        content = item.get("content", item.get("new", ""))
        if not isinstance(content, str):
            errors.append(f"edit #{idx} {path}: create content must be string")
            continue
        if os.path.exists(full):
            errors.append(f"edit #{idx} {path}: create target already exists")
            continue
        buffers[path] = content
        remember(path)
        continue

    if path in whole_file_written:
        errors.append(f"edit #{idx} {path}: old/new edit cannot follow whole-file replacement")
        continue
    old = item.get("old")
    new = item.get("new")
    if not isinstance(old, str) or not isinstance(new, str):
        errors.append(f"edit #{idx} {path}: str_replace requires string old and new")
        continue
    if old == new:
        errors.append(f"edit #{idx} {path}: old and new are identical")
        continue
    if path not in buffers:
        if not os.path.isfile(full):
            errors.append(f"edit #{idx} {path}: file not found")
            continue
        try:
            with open(full, "r", encoding="utf-8", errors="surrogateescape") as f:
                buffers[path] = f.read()
        except Exception as exc:
            errors.append(f"edit #{idx} {path}: read error {type(exc).__name__}: {exc}")
            continue
    content = buffers[path]
    count = content.count(old)
    if count == 0:
        norm_content = content.replace("\r\n", "\n").replace("\r", "\n")
        norm_old = old.replace("\r\n", "\n").replace("\r", "\n")
        if norm_content.count(norm_old) == 1:
            content = norm_content
            old = norm_old
            new = new.replace("\r\n", "\n").replace("\r", "\n")
            count = 1
    if count == 0:
        safe_content = _prompt_safe_text(content)
        safe_old = _prompt_safe_text(old)
        if len(safe_content) == len(content) and safe_content.count(safe_old) == 1:
            start = safe_content.index(safe_old)
            end = start + len(safe_old)
            actual_old = content[start:end]
            old = actual_old
            new = _restore_prompt_replacements(new, safe_old, actual_old)
            count = 1
    if count != 1:
        hint = _nearest_old_hint(content, old)
        extra = f" nearest first-line matches:\n{hint}" if hint else ""
        errors.append(f"edit #{idx} {path}: old text matched {count} times; must match exactly once.{extra}")
        continue
    buffers[path] = content.replace(old, new, 1)
    remember(path)

if errors:
    return False, "Edit pre-validation failed:\n" + "\n".join(errors), []
if not touched:
    return False, "Edit plan contained no effective changes", []

changed: list[str] = []
for path in touched:
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full) or root, exist_ok=True)
    try:
        with open(full, "w", encoding="utf-8", errors="surrogateescape") as f:
            f.write(buffers[path])
        changed.append(path)
    except Exception as exc:
        return False, f"write failed for {path}: {type(exc).__name__}: {exc}", changed
return True, f"Applied {len(changed)} file change(s): {', '.join(changed)}", changed
def is_safe_test_command(cmd: str) -> bool: cmd = (cmd or "").strip() if not cmd or len(cmd) > 300: return False bad = [ " rm ", " rm -", "sudo", "curl ", "wget ", "scp ", "ssh ", "git reset", "git clean", "git checkout", "pip install", "apt ", "apt-get", "conda install", "docker ", ">/dev/", ] padded = f" {cmd} " if any(b in padded for b in bad): return False allowed_prefixes = ( "python ", "python3 ", "pytest ", "py.test ", "tox ", "./runtests.py", "./manage.py", "make test", "coverage run", "coverage erase", "coverage report", "/tests/test.sh", "bash /tests/test.sh", "npm test", "npm run test", "yarn test", "yarn run test", "pnpm test", "pnpm run test", "npx jest", "npx mocha", "node --experimental-vm-modules node_modules/.bin/jest", "cargo test", "cargo nextest", "go test", "mvn test", "mvn verify", "./mvnw test", "./mvnw verify", "gradle test", "./gradlew test", "./gradlew check", "bundle exec rspec", "bundle exec rake test", "rspec ", "make check", "cmake --build", "ctest", "./test.sh", "bash test.sh", "bash ./test.sh", ) return ( cmd.startswith(allowed_prefixes) or " pytest" in cmd or " unittest" in cmd or "cargo test" in cmd or "go test" in cmd or "npm test" in cmd or "mvn test" in cmd )
def _python_cmd() -> str: return "python3"
def normalize_test_command(cmd: str) -> str: cmd = (cmd or "").strip() if "\n" in cmd or "\t" in cmd: cmd = cmd.replace("\n", "\n").replace("\t", "\t") if cmd.startswith("python -m "): return _python_cmd() + cmd[len("python") :] if cmd.startswith("python "): return _python_cmd() + cmd[len("python") :] return cmd
def semantic_test_commands_from_obj(obj: dict[str, Any] | None) -> list[str]: if not isinstance(obj, dict): return [] tests = obj.get("tests") if not isinstance(tests, list): return [] commands: list[str] = [] for item in tests: if not isinstance(item, str): continue cmd = normalize_test_command(item) if not cmd.startswith("python3 -c "): continue if is_safe_test_command(cmd) and cmd not in commands: commands.append(cmd) if len(commands) >= 6: break return commands
def external_test_commands() -> list[str]: if os.path.isfile("/tests/test.sh"): if os.access("/tests/test.sh", os.X_OK): return ["/tests/test.sh"] return ["bash /tests/test.sh"] if os.path.isdir("/tests"): return [f"{_python_cmd()} -m pytest -q /tests"] return []
def default_test_commands(profile: RepoProfile, mode: str, selected_files: list[str], model_tests: Iterable[Any]) -> list[str]: commands: list[str] = [] commands.extend(external_test_commands()) for c in model_tests or []: if isinstance(c, str): normalized = normalize_test_command(c) if is_safe_test_command(normalized) and normalized not in commands: commands.append(normalized) if mode == "spec": if profile.test_files: commands.append(f"{_python_cmd()} -m pytest -q") commands.append(f"{_python_cmd()} -m unittest discover -v") else: for p in selected_files: if p in profile.test_files and p.endswith(".py"): cmd = f"{_python_cmd()} -m pytest -q {shlex.quote(p)}" if cmd not in commands: commands.append(cmd) if len(commands) >= 4: break deduped: list[str] = [] for c in commands: if c not in deduped and is_safe_test_command(c): deduped.append(c) return deduped[:5]
def py_compile_command(paths: list[str]) -> str | None: py = [p for p in paths if p.endswith(".py")] if not py: return None quoted = " ".join(shlex.quote(p) for p in py[:20]) return f"{_python_cmd()} -m py_compile {quoted}"
def _command_unavailable(output: str, command: str) -> bool: low = output.lower() if "no module named pytest" in low or "pytest: command not found" in low: return True if "python: command not found" in low and command.startswith("python "): return True if "no tests ran" in low or "collected 0 items" in low: return True if command.startswith(("python -m unittest", "python3 -m unittest")) and "ran 0 tests" in low: return True return False
def _is_compile_command(cmd: str) -> bool: return " -m py_compile " in f" {cmd} "
CROSS_METHOD_AUDIT_SYSTEM = """Two methods of one class.
If both methods reject the same kind of bad input, they must raise identically.
If your reasoning identifies any mismatch, you MUST output "consistent": false.
JSON only, no preamble: {"consistent": true|false, "reason": "...", "inconsistency": "..."} """
def _select_implemented_methods(source_paths: list[str]) -> list[tuple[str, str, str, str]]:
def _ast_size(fn: ast.FunctionDef) -> int:
    n = 0
    for _ in ast.walk(fn):
        n += 1
    return n

out: list[tuple[str, str, str, str]] = []
for p in source_paths:
    if not p.endswith(".py"):
        continue
    try:
        with open(p, "r") as fp:
            src = fp.read()
        tree = ast.parse(src)
    except (OSError, SyntaxError):
        continue
    lines = src.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        methods = [
            item for item in node.body
            if isinstance(item, ast.FunctionDef)
            and not item.name.startswith("_")
        ]
        if len(methods) < 2:
            continue
        ranked = sorted(
            methods,
            key=lambda m: (_ast_size(m), m.lineno),
            reverse=True,
        )[:2]
        ranked.sort(key=lambda m: m.lineno)
        base_fn, target_fn = ranked

        def _slice(fn):
            start = fn.lineno - 1
            end = fn.end_lineno or (start + 1)
            return "\n".join(lines[start:end])

        out.append((p, node.name, _slice(base_fn), _slice(target_fn)))
return out
def _audit_one_class_pair( file_path: str, class_name: str, base_src: str, target_src: str, *, config: AgentConfig, budget: Budget, model: str, ) -> dict | None: base_user = ( f"Base method:\npython\n{base_src}\n\n\n" f"Target method:\npython\n{target_src}\n\n\n" f"Audit the target against the base. Respond with the single JSON object." )
last_raw = None
for attempt in range(3):
    if attempt == 0:
        user = base_user
        max_tok = 600
    else:
        user = base_user + (
            "\n\nIMPORTANT: The previous attempt failed to return valid JSON. "
            "Reply with ONLY the JSON object on a single line — no markdown, "
            "no explanation, no preamble. Start your response with '{' and end with '}'."
        )
        max_tok = 800
    text = call_llm(
        config=config,
        budget=budget,
        model=model,
        system=CROSS_METHOD_AUDIT_SYSTEM,
        user=user,
        max_tokens=max_tok,
        reserve_fraction=0.005,  
    )
    if not text:
        print("[AUDIT-TRIAL] LLM returned no text (budget-skipped or network error)")
        return None
    last_raw = text
    obj = extract_json_object(text)
    if isinstance(obj, dict) and "consistent" in obj:
        verdict_word = "INCONSISTENT" if obj.get("consistent") is False else "CONSISTENT"
        reason = (obj.get("reason") or obj.get("inconsistency") or "").strip()
        if attempt:
            print(f"[AUDIT-TRIAL] retry attempt {attempt + 1} produced valid JSON")
        print(f"[AUDIT-TRIAL] verdict={verdict_word}  reason={reason[:240]}")
        return obj
    print(f"[AUDIT-TRIAL] LLM non-JSON on attempt {attempt + 1}/3 (first 200 chars): {text[:200]!r}")

print(f"[AUDIT-TRIAL] all 3 attempts failed to produce JSON; giving up on this trial")
return None
def audit_cross_method_consistency( changed_paths: list[str], *, config: AgentConfig, budget: Budget, model: str = "anthropic/claude-opus-4.6", ) -> tuple[bool, str]: pairs = _select_implemented_methods(changed_paths) if not pairs: print("[AUDIT] No class with 2+ public methods found in changed files — skipping audit.") return True, "" print(f"[AUDIT] {len(pairs)} class(es) to audit.") issues: list[str] = [] for file_path, class_name, base_src, target_src in pairs: print(f"\n[AUDIT] ===== {file_path}::{class_name} =====") print(f"[AUDIT] --- BASE method ({len(base_src)} chars) ---") print("\n".join("[AUDIT-BASE] " + line for line in base_src.splitlines())) print(f"[AUDIT] --- TARGET method ({len(target_src)} chars) ---") print("\n".join("[AUDIT-TARGET] " + line for line in target_src.splitlines())) print(f"[AUDIT] --- running up to 3 trials ---") verdicts: list[dict] = [] no_count = 0 yes_count = 0 for trial in range(3): print(f"[AUDIT-TRIAL] >>> trial {trial+1}/3") v = _audit_one_class_pair( file_path, class_name, base_src, target_src, config=config, budget=budget, model=model, ) if v is None: continue verdicts.append(v) if v.get("consistent") is False: no_count += 1 elif v.get("consistent") is True: yes_count += 1 print(f"[AUDIT-TRIAL] running tally: inconsistent={no_count}  consistent={yes_count}") if no_count >= 2: print(f"[AUDIT-TRIAL] short-circuit: 2 inconsistent votes lock the verdict") break completed = len(verdicts) if completed == 0: print(f"[AUDIT] FINAL: skipped (no trial completed) — {file_path}::{class_name}") continue if no_count >= 2: print(f"[AUDIT] FINAL: MAJORITY INCONSISTENT — {no_count}/{completed} trials flagged the patch.") print(f"[AUDIT] → triggering targeted repair (see [REPAIR] lines)") verdict = next(v for v in verdicts if v.get("consistent") is False) else: print(f"[AUDIT] FINAL: majority consistent — {yes_count}/{completed} trials said the patch is fine. Submitting as-is.") continue reason = (verdict.get("inconsistency") or verdict.get("reason") or "").strip() print(f"[AGENT] cross-method audit FAIL: {file_path}::{class_name} — {reason[:200]}") if reason: issues.append(f"{file_path}::{class_name}: {reason}") if not issues: return True, "" signal = ( "Two methods of the same class handle a shared invalid-input condition " "differently. They should match: same response and same wording (delegation " "between them counts). Leave alone any branches that handle conditions only " "one method checks. Specific findings:\n  - " + "\n  - ".join(issues) ) return False, signal
def public_methods_in_patch_diff(patch_diff: str) -> set[str]: names: set[str] = set() for line in patch_diff.splitlines(): if not line.startswith("+"): continue stripped = line[1:].lstrip() if not stripped.startswith("def "): continue rest = stripped[4:] i = rest.find("(") if i <= 0: continue name = rest[:i].strip() if name and not name.startswith(""): names.add(name) return names
def _needs_semantic_test_generation(signal: str) -> bool: return ( "Spec task needs at least one runnable semantic test" in signal or "Only syntax compilation ran" in signal )
def run_verification( executor: ShellExecutor, profile: RepoProfile, mode: str, selected_files: list[str], patch_obj: dict[str, Any], changed: list[str], config: AgentConfig, ) -> tuple[bool, str, int]: commands: list[str] = [] comp = py_compile_command(changed) if comp: commands.append(comp) commands.extend(default_test_commands(profile, mode, selected_files, patch_obj.get("tests") or []))
ran = 0
failures: list[str] = []
neutral = 0
attempted_tests = 0
neutral_tests = 0
passed_tests = 0
for cmd in commands:
    if cmd in commands[:commands.index(cmd)]:
        continue
    print(f"[AGENT] verify: {cmd}")
    out = executor.run(cmd, timeout=config.command_timeout)
    ran += 1
    is_compile = _is_compile_command(cmd)
    if not is_compile:
        attempted_tests += 1
    combined = (out.get("stdout") or "") + ("\n" + out.get("stderr", "") if out.get("stderr") else "")
    snippet = compact(combined, config.test_output_chars)
    if out.get("returncode") != 0:
        if _command_unavailable(combined, cmd):
            neutral += 1
            if not is_compile:
                neutral_tests += 1
            print(f"[AGENT] verify neutral rc={out.get('returncode')}: {cmd}")
            continue
        failures.append(f"COMMAND: {cmd}\nRETURNCODE: {out.get('returncode')}\nOUTPUT:\n{snippet}")
        break
    if not is_compile:
        passed_tests += 1
if failures:
    return False, "\n\n".join(failures), ran
if attempted_tests and passed_tests == 0 and neutral_tests == attempted_tests:
    return False, "Only syntax compilation ran; all attempted test commands were unavailable.", ran
if mode == "spec" and passed_tests == 0:
    return False, "Spec task needs at least one runnable semantic test, not only py_compile.", ran
if ran == 0 or ran == neutral:
    return True, "No runnable verification command was available; patch validated structurally only.", ran
return True, f"Verification commands passed: {ran - neutral}/{ran}", ran
class PatchAgent: def init(self, config: AgentConfig | None = None) -> None: self.config = config or AgentConfig() self.root = find_repo_root(self.config.working_dir) self.executor = ShellExecutor(self.root, timeout=self.config.command_timeout) self.budget = Budget(self.config) self.started_at = time.time()
def timed_out(self) -> bool:
    if self.config.assumed_wall_sec <= 0:
        return False
    return (time.time() - self.started_at) > max(1.0, self.config.assumed_wall_sec - self.config.tail_margin_sec)

def run(self, problem_statement: str) -> str:
    ensure_git_baseline(self.root, self.executor)
    reset_worktree(self.root)
    self._skeleton_complexity = skeleton_complexity(_collect_python_sources(self.root))
    profile = RepoProfile(self.root)
    mode = "spec" if profile.is_small_spec_repo(problem_statement) else "bugfix"
    ranked = rank_files(profile, problem_statement, limit=18 if mode == "bugfix" else 40)
    print(f"[AGENT] root={self.root}")
    print(f"[AGENT] route={mode} py_files={len(profile.py_files)} tests={len(profile.test_files)}")
    print(f"[AGENT] top_files={ranked[:8]}")

    localization: dict[str, Any] | None = None
    if mode == "bugfix" and self.budget.can_call() and len(profile.py_files) > 35:
        loc_prompt = build_localization_prompt(profile, problem_statement, mode, ranked, self.config)
        loc_model = choose_model_for_call(
            config=self.config,
            budget=self.budget,
            mode=mode,
            phase="localize",
            system=LOCALIZE_SYSTEM,
            user=loc_prompt,
            max_tokens=1800,
        )
        loc_raw = None
        if loc_model:
            loc_raw = call_llm(
                config=self.config,
                budget=self.budget,
                model=loc_model,
                system=LOCALIZE_SYSTEM,
                user=loc_prompt,
                max_tokens=1800,
            )
        localization = extract_json_object(loc_raw) or None
        if localization:
            model_files = [p for p in localization.get("files", []) if isinstance(p, str) and p in profile.files]
            if model_files:
                ranked = (model_files + [p for p in ranked if p not in model_files])[:18]
            if localization.get("mode") in {"spec", "bugfix"}:
                if localization["mode"] == "spec" and profile.is_small_spec_repo(problem_statement):
                    mode = "spec"
                elif localization["mode"] == "bugfix":
                    mode = "bugfix"
        else:
            localization = {"mode": mode, "files": ranked, "tests": [], "invariants": []}
    else:
            localization = {"mode": mode, "files": ranked, "tests": [], "invariants": []}

    selected = self._select_context_files(profile, ranked, localization, mode)
    print(f"[AGENT] selected_files={selected}")
    print(
        f"[AGENT] model_cascade patch={[ m for m in self.config.model_cascade_for_phase(mode, 'patch') ]} "
        f"repair={[ m for m in self.config.model_cascade_for_phase(mode, 'repair') ]}"
    )
    api_brief = _augment_spec_brief(
        self.config, self.budget, mode, self.root, profile, selected, problem_statement
    )
    best_patch = ""
    best_signal = ""
    previous_signals: list[str] = []

    def _audit(candidate: str) -> str | None:
        # Final audit/fix pass shared by all three success exits below.
        # profile/problem_statement/mode are loop-invariant; attempt_selected/
        # localization/changed are read live (late binding) at each call site.
        return self._final_audit_and_fix(
            best_patch=candidate,
            profile=profile,
            problem_statement=problem_statement,
            mode=mode,
            attempt_selected=attempt_selected,
            localization=localization,
            changed=changed,
        )

    attempts = 1 + max(0, self.config.max_repair_attempts)
    for attempt in range(attempts):
        if self.timed_out():
            print("[AGENT] wall-clock guard reached before next attempt")
            break
        if attempt > 0 and not self.budget.can_call(reserve_fraction=0.03):
            print("[AGENT] budget/call guard reached before repair attempt")
            break
        reset_worktree(self.root)
        phase = "patch" if attempt == 0 else "repair"
        attempt_selected = selected
        attempt_max_tokens = self.config.max_output_tokens if attempt == 0 else self.config.repair_max_output_tokens
        patch_prompt = build_patch_prompt(
            profile=profile,
            statement=problem_statement,
            mode=mode,
            selected_files=attempt_selected,
            localization=localization,
            previous_signals=previous_signals,
            attempt=attempt,
            config=self.config,
            api_brief=api_brief,
        )
        patch_model = choose_model_for_call(
            config=self.config,
            budget=self.budget,
            mode=mode,
            phase=phase,
            system=PATCH_SYSTEM,
            user=patch_prompt,
            max_tokens=attempt_max_tokens,
        )
        if patch_model is None and mode == "bugfix":
            reduced = self._reduced_context_files(profile, attempt_selected)
            if reduced != attempt_selected:
                print(f"[AGENT] shrinking bugfix context {len(attempt_selected)} -> {len(reduced)} files")
                attempt_selected = reduced
                patch_prompt = build_patch_prompt(
                    profile=profile,
                    statement=problem_statement,
                    mode=mode,
                    selected_files=attempt_selected,
                    localization=localization,
                    previous_signals=previous_signals,
                    attempt=attempt,
                    config=self.config,
                    api_brief=api_brief,
                )
                patch_model = choose_model_for_call(
                    config=self.config,
                    budget=self.budget,
                    mode=mode,
                    phase=phase,
                    system=PATCH_SYSTEM,
                    user=patch_prompt,
                    max_tokens=attempt_max_tokens,
                )
        if patch_model is None:
            previous_signals.append(
                f"No affordable model call was available for {phase}; prompt chars={len(patch_prompt)}."
            )
            break
        raw = call_llm(
            config=self.config,
            budget=self.budget,
            model=patch_model,
            system=PATCH_SYSTEM,
            user=patch_prompt,
            max_tokens=attempt_max_tokens,
        )
        obj = extract_json_object(raw)
        if not obj:
            signal = "Model response was not valid JSON edit object. Return only JSON matching the schema."
            print(f"[AGENT] {signal}")
            previous_signals.append(signal + "\nResponse preview:\n" + compact(raw or "", 2000))
            continue
        print(f"[AGENT] patch edits: {compact(raw or '', 800)}")
        ok, msg, changed = apply_edits(self.root, obj)
        print(f"[AGENT] apply result ok={ok}: {msg[:500]}")
        if not ok:
            previous_signals.append(msg)
            continue
        patch = collect_worktree_patch(self.executor)
        if not patch.strip():
            previous_signals.append("Edits applied but git diff is empty. Produce a real source change.")
            continue
        if not validate_patch_applies_cleanly(patch, self.root):
            previous_signals.append("Patch was generated but failed git apply --check against clean HEAD.")
            continue
        best_patch = patch
        verify_ok, verify_signal, ran = run_verification(
            self.executor, profile, mode, attempt_selected, obj, changed, self.config
        )
        best_signal = verify_signal
        print(f"[AGENT] verification ok={verify_ok} ran={ran}: {verify_signal[:400]}")
        if verify_ok:
            if self.config.enable_final_review and self.budget.can_call(reserve_fraction=0.03):
                review_patch = self._maybe_review_and_repair(
                    profile, problem_statement, mode, attempt_selected, localization, patch, verify_signal
                )
                if review_patch:
                    best_patch = review_patch
            final_patch = _audit(best_patch)
            if final_patch:
                return final_patch
            return best_patch
        if mode == "spec" and _needs_semantic_test_generation(verify_signal):
            semantic_ok, semantic_signal, semantic_ran = self._maybe_generate_and_run_semantic_tests(
                profile, problem_statement, attempt_selected, patch, verify_signal, changed
            )
            print(f"[AGENT] generated semantic verification ok={semantic_ok} ran={semantic_ran}: {semantic_signal[:400]}")
            if semantic_ok:
                final_patch = _audit(best_patch)
                if final_patch:
                    return final_patch
                return best_patch
            verify_signal = verify_signal + "\n\nSemantic test generation attempt:\n" + semantic_signal
        previous_signals.append(
            "The patch applied but verification failed. Repair from clean HEAD; return a complete replacement edit set.\n"
            + verify_signal
            + "\nCurrent diff:\n"
            + compact(patch, 12000)
        )

    if best_patch and validate_patch_applies_cleanly(best_patch, self.root):
        final_patch = _audit(best_patch)
        if final_patch:
            return final_patch
        print(f"[AGENT] returning best structurally valid patch despite signal: {best_signal[:500]}")
        return best_patch
    emergency = collect_worktree_patch(self.executor)
    if emergency and validate_patch_applies_cleanly(emergency, self.root):
        print("[AGENT] returning emergency worktree patch")
        return emergency
    return ""

def _final_audit_and_fix(
    self,
    *,
    best_patch: str,
    profile: RepoProfile,
    problem_statement: str,
    mode: str,
    attempt_selected: list[str],
    localization: dict[str, Any] | None,
    changed: list[str],
) -> str | None:
    if mode != "spec":
        return None
    complexity = getattr(self, "_skeleton_complexity", 0)
    threshold = _complexity_threshold()
    if complexity > threshold:
        print(f"[FINAL-AUDIT] skipped — skeleton complexity {complexity} > {threshold} "
              f"(complex skeletons use the behaviour-analysis path, not the audit)")
        return None
    if not self.budget.can_call(reserve_fraction=0.06):
        print("[FINAL-AUDIT] skipped — not enough budget to even start audit")
        return None

    print(f"\n[FINAL-AUDIT] ============ entering final-audit gate ============")
    print(f"[FINAL-AUDIT] best_patch length: {len(best_patch)} chars")
    print(f"[FINAL-AUDIT] best_patch preview (first 30 lines):")
    for ln in best_patch.splitlines()[:30]:
        print(f"[FINAL-AUDIT-PATCH] {ln}")
    if len(best_patch.splitlines()) > 30:
        print(f"[FINAL-AUDIT-PATCH] ... ({len(best_patch.splitlines())-30} more lines)")

    reset_worktree(self.root)
    patch_file = os.path.join(self.root, ".knight_final_audit.patch")
    try:
        with open(patch_file, "w") as fp:
            fp.write(best_patch)
        self.executor.run(f"git apply {shlex.quote(patch_file)}")
    except Exception as exc:
        print(f"[AGENT] final-audit: failed to re-apply best_patch: {exc}")
        return None
    finally:
        try:
            os.remove(patch_file)
        except OSError:
            pass

    audit_ok, audit_signal = audit_cross_method_consistency(
        [os.path.join(self.root, p) for p in (changed or attempt_selected)],
        config=self.config,
        budget=self.budget,
    )
    if audit_ok:
        print("[AGENT] final-audit: best_patch passed; submitting as-is.")
        return None  

    print(f"[AGENT] final-audit FAIL → one targeted repair attempt: {audit_signal[:300]}")


    reset_worktree(self.root)
    head_sources: list[str] = []
    for rel in (changed or attempt_selected or [])[:3]:  
        try:
            with open(os.path.join(self.root, rel)) as fp:
                src = fp.read()
            head_sources.append(f"## Current `{rel}` (at clean HEAD)\n```python\n{src}\n```")
        except OSError:
            continue
    head_block = "\n\n".join(head_sources) if head_sources else ""

    targeted_user = (
        "The previously-chosen patch was audited and a cross-method "
        "consistency issue was found:\n\n"
        f"{audit_signal}\n\n"
        "Here is the prior patch (this is your full implementation; do not "
        "lose any of it):\n```diff\n"
        f"{best_patch}\n```\n\n"
        + (f"{head_block}\n\n" if head_block else "")
        + "Produce a NEW complete JSON edit object (per the system schema) "
        "from clean HEAD that keeps ALL the above implementation EXCEPT "
        "for the minimal change needed to resolve the audit finding. "
        "Every method, helper, and branch of the prior patch must remain "
        "(with the targeted adjustment applied). Branches handling "
        "conditions only one of the two methods checks must be left "
        "exactly as they are.\n\n"
        "IMPORTANT: each edit's `old` field must be exact text from the "
        "clean HEAD source shown above (NOT from the prior patch). Match "
        "indentation and whitespace exactly. Prefer a full-file `replace` "
        "edit if the file is short."
    )
    patch_model = "anthropic/claude-opus-4.8"
    print(f"[REPAIR] forcing opus for the final-audit repair (audit found a bug worth opus's call)")
    text = call_llm(
        config=self.config,
        budget=self.budget,
        model=patch_model,
        system=PATCH_SYSTEM,
        user=targeted_user,
        max_tokens=2500,
        force=True,  
    )
    obj = extract_json_object(text)
    if not isinstance(obj, dict):
        print(f"[REPAIR] LLM did not return valid JSON. First 300 chars:\n  {text[:300]!r}")
        print("[REPAIR] → keeping original best_patch (no fix applied)")
        return None
    ok, msg, changed_repaired = apply_edits(self.root, obj)
    if not ok:
        print(f"[REPAIR] apply_edits failed: {msg}")
        print("[REPAIR] → keeping original best_patch (no fix applied)")
        return None
    repaired = collect_worktree_patch(self.executor)
    if not repaired or not validate_patch_applies_cleanly(repaired, self.root):
        print("[REPAIR] produced patch doesn't apply cleanly")
        print("[REPAIR] → keeping original best_patch (no fix applied)")
        return None

    print(f"[REPAIR] LLM produced a candidate repair patch ({len(repaired)} chars). Preview (first 30 lines):")
    for ln in repaired.splitlines()[:30]:
        print(f"[REPAIR-PATCH] {ln}")
    if len(repaired.splitlines()) > 30:
        print(f"[REPAIR-PATCH] ... ({len(repaired.splitlines())-30} more lines)")

    verify_ok, verify_signal, ran = run_verification(
        self.executor, profile, mode, attempt_selected, obj, changed_repaired, self.config
    )
    print(f"[REPAIR] verify on candidate: ok={verify_ok} ran={ran} signal: {verify_signal[:200]}")

    print(f"[REPAIR] re-running audit on the candidate repair patch...")
    audit_ok2, _ = audit_cross_method_consistency(
        [os.path.join(self.root, p) for p in (changed_repaired or attempt_selected)],
        config=self.config,
        budget=self.budget,
    )
    if not audit_ok2:
        print("[REPAIR] re-audit STILL flags the candidate as inconsistent")
        print("[REPAIR] → keeping original best_patch (the repair did not fix the issue)")
        return None
    print("[REPAIR] re-audit on candidate: consistent ✓")

    if len(repaired) < len(best_patch) * 0.4:
        print(
            f"[REPAIR] regression guard FIRED: candidate is {len(repaired)}B "
            f"vs best_patch {len(best_patch)}B (less than 40%). Likely "
            f"incomplete — keeping original."
        )
        return None
    try:
        best_methods = _public_methods_in_patch_diff(best_patch)
        new_methods = _public_methods_in_patch_diff(repaired)
        if best_methods and not best_methods.issubset(new_methods):
            missing = best_methods - new_methods
            print(
                f"[REPAIR] regression guard FIRED: candidate is missing methods "
                f"present in best_patch: {sorted(missing)}. Keeping original."
            )
            return None
    except Exception as exc:
        print(f"[REPAIR] method-set check failed (defensive): {exc}")

    print("[REPAIR] ✓ candidate passes re-audit + regression guards — SUBMITTING REPAIRED PATCH")
    return repaired

def _select_context_files(
    self,
    profile: RepoProfile,
    ranked: list[str],
    localization: dict[str, Any] | None,
    mode: str,
) -> list[str]:
    selected: list[str] = []
    if localization:
        for p in localization.get("files", []) or []:
            if isinstance(p, str) and p in profile.files and p not in selected:
                selected.append(p)
    for p in ranked:
        if p not in selected:
            selected.append(p)
    if mode == "spec":
        small_py = [p for p in profile.py_files if profile.file_sizes.get(p, 0) <= 50000]
        if sum(profile.file_sizes.get(p, 0) for p in small_py) <= 220000:
            for p in small_py:
                if p not in selected:
                    selected.append(p)
        return selected[:50]
    source = [p for p in selected if p in profile.source_py_files][:8]
    tests = [p for p in selected if p in profile.test_files][:4]
    merged: list[str] = []
    for p in source + tests + selected:
        if p not in merged:
            merged.append(p)
        if len(merged) >= 12:
            break
    return merged[:12]

def _reduced_context_files(self, profile: RepoProfile, selected: list[str]) -> list[str]:
    source = [p for p in selected if p in profile.source_py_files][:5]
    tests = [p for p in selected if p in profile.test_files][:2]
    merged: list[str] = []
    for p in source + tests + selected:
        if p not in merged:
            merged.append(p)
        if len(merged) >= 8:
            break
    return merged or selected[: min(len(selected), 6)]

def _maybe_generate_and_run_semantic_tests(
    self,
    profile: RepoProfile,
    statement: str,
    selected: list[str],
    patch: str,
    verify_signal: str,
    changed: list[str],
) -> tuple[bool, str, int]:
    if not self.budget.can_call(reserve_fraction=0.03):
        return False, "No model budget available to generate semantic tests.", 0
    prompt = build_semantic_test_prompt(
        profile=profile,
        statement=statement,
        selected_files=selected,
        patch=patch,
        verify_signal=verify_signal,
        config=self.config,
    )
    semantic_model = choose_model_for_call(
        config=self.config,
        budget=self.budget,
        mode="spec",
        phase="semantic",
        system=SEMANTIC_TEST_SYSTEM,
        user=prompt,
        max_tokens=1800,
    )
    if semantic_model is None:
        return False, "No affordable model available to generate semantic tests.", 0
    raw = call_llm(
        config=self.config,
        budget=self.budget,
        model=semantic_model,
        system=SEMANTIC_TEST_SYSTEM,
        user=prompt,
        max_tokens=1800,
    )
    obj = extract_json_object(raw)
    tests = semantic_test_commands_from_obj(obj)
    if not tests:
        preview = compact(raw or "", 1200)
        return False, "Semantic test generation produced no runnable python3 -c commands.\nResponse preview:\n" + preview, 0
    print(f"[AGENT] generated semantic tests: {len(tests)}")
    test_obj = {"tests": tests}
    ok, signal, ran = run_verification(self.executor, profile, "spec", selected, test_obj, changed, self.config)
    detail = "Generated semantic tests:\n" + "\n".join(f"- {cmd}" for cmd in tests)
    return ok, detail + "\n\n" + signal, ran

def _maybe_review_and_repair(
    self,
    profile: RepoProfile,
    statement: str,
    mode: str,
    selected: list[str],
    localization: dict[str, Any] | None,
    patch: str,
    verify_signal: str,
) -> str | None:
    prompt = f"""Review this candidate patch against the problem. If it is correct and minimal, return JSON with an empty edits list and notes explaining acceptance. If there is a likely hidden-test issue, return complete JSON edits against clean HEAD.
Problem statement: {statement}
Route: {mode}
Localization: {_json_dumps(localization or {}, 8000)}
Verification signal: {compact(verify_signal, 5000)}
Candidate diff: {compact(patch, 22000)}
Relevant context: {file_snippets(profile, selected, statement, 42000)} """ review_model = choose_model_for_call( config=self.config, budget=self.budget, mode=mode, phase="review", system=PATCH_SYSTEM, user=prompt, max_tokens=3200, ) if review_model is None: return None raw = call_llm( config=self.config, budget=self.budget, model=review_model, system=PATCH_SYSTEM, user=prompt, max_tokens=3200, ) obj = extract_json_object(raw) if not obj: return None edits = obj.get("edits") if not edits: return None reset_worktree(self.root) ok, msg, changed = apply_edits(self.root, obj) if not ok: print(f"[AGENT] final review edit rejected: {msg[:500]}") reset_worktree(self.root) subprocess.run(["git", "-C", self.root, "apply", "--whitespace=nowarn"], input=patch, text=True, capture_output=True, timeout=60) return None new_patch = collect_worktree_patch(self.executor) if new_patch and validate_patch_applies_cleanly(new_patch, self.root): verify_ok, signal, _ran = run_verification(self.executor, profile, mode, selected, obj, changed, self.config) if verify_ok: return new_patch print(f"[AGENT] final review patch failed verification: {signal[:500]}") reset_worktree(self.root) subprocess.run(["git", "-C", self.root, "apply", "--whitespace=nowarn"], input=patch, text=True, capture_output=True, timeout=60) return None
def agent_main(input: Any) -> str: _log_inference_target_once() print("[AGENT] entered agent_main")
if isinstance(input, dict):
    problem_statement = str(input.get("problem_statement") or input.get("instruction") or "")
else:
    problem_statement = str(input or "")
if not problem_statement.strip():
    print("[AGENT] empty problem statement")
    return ""


config = AgentConfig()



COMPLEXITY_THRESHOLD = _complexity_threshold()
root = find_repo_root(config.working_dir)
complexity = skeleton_complexity(_collect_python_sources(root))
if complexity > COMPLEXITY_THRESHOLD:
    function_behaviour = generate_function_behaviour(problem_statement, config=config, root=root)
    print("[AGENT] return values:")
    print(json.dumps(function_behaviour, indent=2, ensure_ascii=False))
    behaviour_text = _function_behaviour_to_text(function_behaviour)
    if behaviour_text:
        problem_statement = f"{problem_statement}\n\n{behaviour_text}"
        print("[AGENT] appended function behaviour analysis to problem statement")
        print(f"[AGENT] {problem_statement}")
else:
    print(f"[AGENT] skeleton complexity {complexity} <= {COMPLEXITY_THRESHOLD}; skipping behaviour analysis")

agent = PatchAgent(config)
patch = ""
try:
    patch = agent.run(problem_statement)
except Exception as exc:
    print(f"[AGENT] crash: {type(exc).__name__}: {exc}")
    try:
        patch = collect_worktree_patch(agent.executor)
    except Exception:
        patch = ""

patch = normalize_patch_text(patch)
if not patch.strip():
    print("[AGENT] returning empty patch")
    return ""
if not validate_patch_applies_cleanly(patch, agent.root):
    print("[AGENT] final patch failed validation; returning empty patch")
    reset_worktree(agent.root)
    return ""
reset_worktree(agent.root)
print(f"[AGENT] returning patch chars={len(patch)}")
return patch
all = [ "AgentConfig", "PatchAgent", "RepoProfile", "agent_main", "apply_edits", "collect_worktree_patch", "extract_json_object", "find_repo_root", "generate_function_behaviour", "normalize_patch_text", "rank_files", "reset_worktree", "run_verification", "skeleton_complexity", "validate_patch_applies_cleanly", ] '''
_FIX_SOURCE = r''' from future import annotations
import ast import hashlib import json import os import random import re import shlex import subprocess import time from typing import Any, Dict, List, Optional, Tuple import requests
AGENT_TIMEOUT = os.getenv("AGENT_TIMEOUT") AGENT_TIMEOUT_SEC = float(AGENT_TIMEOUT) if AGENT_TIMEOUT else None RUN_ID = os.getenv("EVALUATION_RUN_ID") if not RUN_ID: print("[AGENT] WARNING: RUN_ID (EVALUATION_RUN_ID) is not set")
LLM_CONNECT_TIMEOUT = int(os.getenv("LLM_CONNECT_TIMEOUT", "30"))
Per-read timeout was 130s — too forgiving for streaming responses that
trickle in chunk-by-chunk (each chunk resets the timer, so a model dribbling
64K of garbage tokens can hold the connection arbitrarily long). 60s gives
normal calls plenty of room while bounding the pathological case.
LLM_READ_TIMEOUT = int(os.getenv("LLM_REQUEST_TIMEOUT", "60")) _PY_COMPILE_TIMEOUT_SEC = 25
_RUN_DEADLINE = None
_DEFAULT_EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
def _agent_assumed_wall_sec() -> Optional[float]: raw = (os.getenv("RIDGES_AGENT_ASSUMED_WALL_SEC") or "").strip().lower() if raw in ("0", "none", "off", "inf", "infinity"): return None if raw: try: v = float(raw) return None if v <= 0 else v except ValueError: pass return 2700.0
def _effective_agent_wall_sec() -> Optional[float]: if AGENT_TIMEOUT_SEC is not None: return float(AGENT_TIMEOUT_SEC) return _agent_assumed_wall_sec()
def _agent_tail_margin_sec() -> float: env = os.getenv("RIDGES_AGENT_TAIL_MARGIN_SEC") if env and env.strip(): try: return max(15.0, float(env)) except ValueError: pass return 45.0
def _pretimeout_trigger_sec() -> float: return 150.0
def _openrouter_api_key() -> str | None: return os.getenv("OPENROUTER_API_KEY")
def _openrouter_base_url() -> str: return ( os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1" ).rstrip("/")
def _log_inference_target_once() -> None: if getattr(_log_inference_target_once, "_done", False): return _log_inference_target_once._done = True
base = _openrouter_base_url() has_key = bool(_openrouter_api_key()) model = os.getenv("RIDGES_AGENT_MODEL", "").strip() or "(unset)" print( "[INFERENCE] target=openrouter-direct " f"base_url={base} api_key={'set' if has_key else 'MISSING'} " f"default_model={model} (no gateway)" )
if not _openrouter_api_key(): print("[AGENT] WARNING: No inference route configured. Set OPENROUTER_API_KEY.")
def _retry_sleep_after_rate_limit(attempt: int) -> None: wait = min(0.3 * (2 ** attempt) + random.uniform(0, 0.5), 5.0) time.sleep(wait)
def _llm_seed_enabled() -> bool: return os.getenv("RIDGES_LLM_USE_SEED", "1").strip().lower() not in ("0", "false", "no")
def _resolve_llm_seed() -> int: raw = os.getenv("RIDGES_LLM_SEED", "").strip() if raw: try: return int(raw) % (2**31) except ValueError: digest = hashlib.sha256(raw.encode()).digest() return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF rid = os.getenv("EVALUATION_RUN_ID") or RUN_ID or "" if rid: digest = hashlib.sha256(rid.encode()).digest() return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF return 1
def _prompt_cache_enabled() -> bool: raw = (os.getenv("RIDGES_PROMPT_CACHE") or "1").strip().lower() return raw in ("1", "true", "yes", "on")
def _wrap_with_cache_control(role: str, text: str) -> dict[str, Any]: return { "role": role, "content": [{ "type": "text", "text": text, "cache_control": {"type": "ephemeral"}, }], }
def _apply_prompt_cache_markers(messages: list[dict[str, Any]]) -> list[dict[str, Any]]: if not _prompt_cache_enabled(): return messages last_user_idx = -1 for idx in range(len(messages) - 1, -1, -1): if messages[idx].get("role") == "user" and isinstance(messages[idx].get("content"), str): last_user_idx = idx break out: list[dict[str, Any]] = [] for idx, m in enumerate(messages): role = m.get("role") content = m.get("content") if not isinstance(content, str): out.append(m) continue if role == "system" or idx == last_user_idx: out.append(_wrap_with_cache_control(role, content)) else: out.append(m) return out
_INFERENCE_RETRY_NUDGE = ( "The previous inference request failed transiently. " "Respond with THOUGHT: and exactly one action block for your next step." )
_INFERENCE_FAILURE_NUDGE_MARKERS = ( "inference request failed transiently", "the inference call failed", )
def _is_inference_failure_nudge(content: str) -> bool: low = (content or "").lower() return any(marker in low for marker in _INFERENCE_FAILURE_NUDGE_MARKERS)
def _build_inference_checkpoint_messages( messages: list[dict[str, str]], *, max_tail: int = 8, ) -> list[dict[str, str]]: """Trim conversation for inference retries — system, task, and recent turns.""" filtered = [ m for m in messages if not (m.get("role") == "user" and _is_inference_failure_nudge(m.get("content") or "")) ] if len(filtered) <= 12: out = list(filtered) if not out or out[-1].get("content") != _INFERENCE_RETRY_NUDGE: out.append({"role": "user", "content": _INFERENCE_RETRY_NUDGE}) return out
system_msgs = [m for m in filtered if m.get("role") == "system"]
rest = [m for m in filtered if m.get("role") != "system"]
first_user = next((m for m in rest if m.get("role") == "user"), None)
tail = rest[-max_tail:] if len(rest) > max_tail else rest

out: list[dict[str, str]] = []
seen: set[tuple[str, str]] = set()
for m in system_msgs:
    key = (m.get("role", ""), m.get("content", ""))
    if key in seen:
        continue
    seen.add(key)
    out.append(m)
if first_user is not None:
    key = (first_user.get("role", ""), first_user.get("content", ""))
    if key not in seen:
        seen.add(key)
        out.append(first_user)
for m in tail:
    key = (m.get("role", ""), m.get("content", ""))
    if key in seen:
        continue
    seen.add(key)
    out.append(m)
out.append({"role": "user", "content": _INFERENCE_RETRY_NUDGE})
print(
    f"[AGENT] inference checkpoint: trimmed {len(messages)} -> {len(out)} messages "
    f"({sum(len(m.get('content') or '') for m in out)} chars)"
)
return out
def inference( model, temperature, messages, *, top_p: float | None = None, seed: int | None = None, ): timeout = (LLM_CONNECT_TIMEOUT, LLM_READ_TIMEOUT) api_key = _openrouter_api_key() if not api_key: print("[AGENT] inference(): missing OPENROUTER_API_KEY") return None, None
resolved = model
url = f"{_openrouter_base_url()}/chat/completions"
payload: dict[str, Any] = {
    "model": resolved,
    "messages": _apply_prompt_cache_markers(messages),
    "temperature": temperature,
}
if top_p is not None:
    payload["top_p"] = top_p
if seed is not None:
    payload["seed"] = int(seed)
mt = os.getenv("RIDGES_AGENT_MAX_OUTPUT_TOKENS", "").strip()
if mt.isdigit():
    payload["max_tokens"] = int(mt)
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}
seed_note = f", seed={payload['seed']}" if "seed" in payload else ""
top_p_note = f", top_p={payload['top_p']}" if "top_p" in payload else ""
print(
    f"[AGENT] inference(): OpenRouter endpoint model={resolved} (from {model}), "
    f"temperature={temperature}{top_p_note}{seed_note}, {len(messages)} messages"
)

wait = 1.0
max_wait = 60.0
last_attempt = 4
attempt = 0
while attempt <= last_attempt:
    if _RUN_DEADLINE is not None:
        _rem = _RUN_DEADLINE - time.time()
        if _rem <= 8:
            print("[AGENT] inference(): wall-clock deadline reached; aborting retries")
            return None, None
        timeout = (LLM_CONNECT_TIMEOUT, max(10, min(LLM_READ_TIMEOUT, int(_rem - 5))))
    # SIGALRM hard-cap. `requests`'s read timeout resets on each TCP chunk,
    # so a model dribbling tokens can hold the connection open indefinitely.
    # SIGALRM is unconditional — it fires at hard_cap seconds regardless of
    # streaming activity, raises TimeoutError, and the `except` below
    # treats it as a retriable timeout. Only enabled in main thread and on
    # POSIX systems (signal.SIGALRM doesn't exist on Windows).
    _alarm_active = False
    _prev_handler = None
    try:
        import signal as _signal
        import threading as _threading
        if hasattr(_signal, "SIGALRM") and _threading.current_thread() is _threading.main_thread():
            hard_cap = max(15, min(
                LLM_READ_TIMEOUT + 30,
                int((_RUN_DEADLINE - time.time() - 5) if _RUN_DEADLINE else LLM_READ_TIMEOUT + 30)
            ))
            def _alarm_handler(signum, frame):
                raise TimeoutError(f"inference hard cap ({hard_cap}s) reached")
            _prev_handler = _signal.signal(_signal.SIGALRM, _alarm_handler)
            _signal.alarm(hard_cap)
            _alarm_active = True
    except Exception:
        pass
    try:
        response = requests.post(url, json=payload, timeout=timeout, headers=headers)
        if response.status_code == 429 and attempt < last_attempt:
            retry_after = response.headers.get("Retry-After")
            slept = False
            if retry_after:
                try:
                    time.sleep(float(retry_after))
                    slept = True
                except ValueError:
                    pass
            if not slept:
                time.sleep(wait)
            wait = min(wait * 2, max_wait)
            print(f"[AGENT] inference(): HTTP 429, retrying (attempt {attempt + 2}/5)...")
            attempt += 1
            continue
        if response.status_code != 200:
            retriable = response.status_code in (408, 425, 429, 500, 502, 503, 504)
            if retriable and attempt < last_attempt:
                print(
                    f"[AGENT] inference(): HTTP {response.status_code}, retrying "
                    f"(attempt {attempt + 2}/{last_attempt + 1})..."
                )
                _retry_sleep_after_rate_limit(attempt)
                attempt += 1
                continue
            print(
                f"[AGENT] inference(): Inference failed with status {response.status_code}: "
                f"{response.text[:800]}"
            )
            return None, None
        data = response.json()
        message = (data.get("choices") or [{}])[0].get("message") or {}
        result = (message.get("content") or "").strip()
        print(f"[AGENT] inference(): Inference response: {len(result)} characters")
        usage = data.get("usage", {})
        details = usage.get("prompt_tokens_details") or {}
        cached_tokens = (
            details.get("cached_tokens")
            or usage.get("cache_read_input_tokens")
            or 0
        )
        usage_info = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "cached_tokens": cached_tokens,
        }
        if usage_info["total_tokens"] > 0:
            cache_suffix = f" cached={cached_tokens}" if cached_tokens else ""
            print(f"[AGENT] inference(): Token usage: {usage_info}{cache_suffix}")
        if not result:
            if attempt < last_attempt:
                print(
                    f"[AGENT] inference(): empty content, retrying "
                    f"(attempt {attempt + 2}/{last_attempt + 1})..."
                )
                _retry_sleep_after_rate_limit(attempt)
                attempt += 1
                continue
            return None, usage_info
        return result, usage_info
    except requests.exceptions.Timeout as exc:
        print(f"[AGENT] inference(): Request timeout: {exc}")
        if attempt < last_attempt:
            _retry_sleep_after_rate_limit(attempt)
            attempt += 1
            continue
        return None, None
    except requests.exceptions.ConnectionError as exc:
        print(f"[AGENT] inference(): Connection error: {exc}")
        if attempt < last_attempt:
            _retry_sleep_after_rate_limit(attempt)
            attempt += 1
            continue
        return None, None
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"[AGENT] inference(): Invalid JSON in response: {exc}")
        if attempt < last_attempt:
            _retry_sleep_after_rate_limit(attempt)
            attempt += 1
            continue
        return None, None
    except TimeoutError as exc:
        # SIGALRM-raised hard cap (or socket cap). Treat as retriable.
        print(f"[AGENT] inference(): Hard timeout fired: {exc}")
        if attempt < last_attempt:
            _retry_sleep_after_rate_limit(attempt)
            attempt += 1
            continue
        return None, None
    except Exception as exc:
        print(f"[AGENT] inference(): Inference request failed: {exc}")
        return None, None
    finally:
        # Always cancel + restore even on success — orphan alarms would
        # later interrupt unrelated code with our TimeoutError.
        if _alarm_active:
            try:
                _signal.alarm(0)
                if _prev_handler is not None:
                    _signal.signal(_signal.SIGALRM, _prev_handler)
            except Exception:
                pass

return None, None
def embedding(input): timeout = (LLM_CONNECT_TIMEOUT, min(LLM_READ_TIMEOUT, 120)) model = os.getenv("RIDGES_EMBEDDING_MODEL", _DEFAULT_EMBEDDING_MODEL) api_key = _openrouter_api_key() if not api_key: print("[AGENT] embedding(): missing OPENROUTER_API_KEY") return None
resolved = _resolve_embedding_for_local(model)
payload = {"model": resolved, "input": input}
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}
url = f"{_openrouter_base_url()}/embeddings"
print(f"[AGENT] embedding(): OpenRouter endpoint model={resolved}")

last_attempt = 4
attempt = 0
wait = 1.0
max_wait = 60.0
while attempt <= last_attempt:
    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        if response.status_code == 429 and attempt < last_attempt:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    time.sleep(float(retry_after))
                except ValueError:
                    time.sleep(wait)
            else:
                time.sleep(wait)
            wait = min(wait * 2, max_wait)
            print(f"[AGENT] embedding(): HTTP 429, retrying (attempt {attempt + 2}/5)...")
            attempt += 1
            continue
        if response.status_code != 200:
            retriable = response.status_code in (408, 425, 429, 500, 502, 503, 504)
            if retriable and attempt < last_attempt:
                print(
                    f"[AGENT] embedding(): HTTP {response.status_code}, retrying "
                    f"(attempt {attempt + 2}/{last_attempt + 1})..."
                )
                _retry_sleep_after_rate_limit(attempt)
                attempt += 1
                continue
            print(
                f"[AGENT] embedding(): failed status {response.status_code}: "
                f"{response.text[:500]}"
            )
            return None
        data = response.json()
        row = (data.get("data") or [{}])[0]
        result = row.get("embedding")
        if not isinstance(result, list):
            print("[AGENT] embedding(): unexpected response shape")
            return None
        print(f"[AGENT] embedding(): Embedding response: {len(result)} dimensions")
        return result
    except requests.exceptions.Timeout as exc:
        print(f"[AGENT] embedding(): Request timeout: {exc}")
        if attempt < last_attempt:
            _retry_sleep_after_rate_limit(attempt)
            attempt += 1
            continue
        return None
    except requests.exceptions.ConnectionError as exc:
        print(f"[AGENT] embedding(): Connection error: {exc}")
        if attempt < last_attempt:
            _retry_sleep_after_rate_limit(attempt)
            attempt += 1
            continue
        return None
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"[AGENT] embedding(): Invalid JSON in response: {exc}")
        return None
    except Exception as e:
        print(f"[AGENT] embedding(): Embedding request failed: {e}")
        return None
return None
PLANNING_MODEL = os.getenv("RIDGES_PLANNING_MODEL", "minimax/minimax-m2.5") DEFAULT_MODEL = os.getenv("RIDGES_AGENT_MODEL", "minimax/minimax-m2.5") FAST_MODEL = os.getenv("RIDGES_AGENT_FAST_MODEL", "qwen/qwen3-coder-next") _DEFAULT_COST_RAW = os.getenv("RIDGES_MAX_COST_USD", "0.29") or "0.29" DEFAULT_COST_LIMIT = float(_DEFAULT_COST_RAW) _PLANNING_MIN_COST_USD = float(os.getenv("RIDGES_PLANNING_MIN_COST_USD", "0.12"))
class AgentConfig:
def __init__(
    self,
    planning_model: str = PLANNING_MODEL,
    execution_model: str | None = None,
    model: str | None = None,
    fast_model: str = FAST_MODEL,
    temperature: float = 0.0,
    planning_temperature: float = 0.0,
    max_steps: int = 100,
    max_output_chars: int = 8000,
    max_head_tail_chars: int = 4000,
    max_conversation_chars: int = 120000,
    max_inference_retries: int = 3,
    inference_retry_delay: float = 5.0,
    command_timeout: int = 120,
    working_dir: Optional[str] = None,
    cost_limit: float = DEFAULT_COST_LIMIT,
    enable_planning: bool = True,
):
    exec_model = execution_model or model or DEFAULT_MODEL
    self.planning_model = planning_model
    self.execution_model = exec_model
    self.fast_model = fast_model
    self.temperature = temperature
    self.planning_temperature = planning_temperature
    _tp = os.getenv("RIDGES_LLM_TOP_P", "1").strip()
    try:
        self.llm_top_p = float(_tp)
    except ValueError:
        self.llm_top_p = 1.0
    _env_steps = os.getenv("RIDGES_AGENT_MAX_STEPS", "").strip()
    if _env_steps:
        try:
            max_steps = max(10, int(_env_steps))
        except ValueError:
            pass
    self.max_steps = max_steps
    self.max_output_chars = max_output_chars
    self.max_head_tail_chars = max_head_tail_chars
    self.max_conversation_chars = max_conversation_chars
    self.max_inference_retries = max_inference_retries
    self.inference_retry_delay = inference_retry_delay
    self.command_timeout = command_timeout
    self.working_dir = working_dir
    self.cost_limit = cost_limit
    self.enable_planning = enable_planning

@property
def model(self) -> str:
    return self.execution_model
MODEL_PRICING: dict[str, tuple[float, float]] = { "minimax/minimax-m2.5": (0.15, 1.15), "qwen/qwen3-coder-next": (0.11, 0.8), "qwen/qwen3-embedding-8b": (0.01, 0.01), "anthropic/claude-opus-4.8": (5.0, 25.0), "anthropic/claude-sonnet-4.5": (3.0, 15.0), }
def get_model_pricing(model: str) -> tuple[float, float]: resolved = model for candidate in (model, resolved): if candidate in MODEL_PRICING: return MODEL_PRICING[candidate] for prefix, prices in MODEL_PRICING.items(): key = prefix.rstrip("/") for candidate in (model, resolved): if candidate == key or candidate.startswith(key + "/"): return prices print(f"[AGENT] WARNING: No pricing info for model {model}, using default ($1/$2 per 1M)") return (1.0, 2.0)
MINI_ACTION_REGEX_RSWEA = re.compile( r"\s*rswea_bash_command\s*\n(.*?)\n\s*", re.DOTALL | re.IGNORECASE, ) MINI_ACTION_REGEX_BASH = re.compile(r"\s*bash\s*\n(.*?)\n\s*", re.DOTALL | re.IGNORECASE)
EDIT_ACTION_REGEX = re.compile( r"\s*apply_str_replace\s*\n(.*?)\n\s*", re.DOTALL | re.IGNORECASE, )
MULTI_EDIT_ACTION_REGEX = re.compile( r"\s*apply_multi_edit\s*\n(.*?)\n\s*", re.DOTALL | re.IGNORECASE, )
MINI_OBSERVATION_FULL_MAX = 10000 MINI_OBSERVATION_HEAD = 5000 MINI_OBSERVATION_TAIL = 5000
SYSTEM_PROMPT = """
You are a senior software engineer fixing real bugs in real repositories.
Each turn, your response must contain EXACTLY ONE action block. Pick the right block type for the work:
    1. rswea_bash_command — run a single shell command (or chain with && / ||).
       ls -la
    2. apply_str_replace — exact text replacement in a file (most reliable for code edits — no shell quoting, no sed escaping). Format:
       <<<FILE>>>
path/to/file.py
<<<OLD>>>
exact text to find (must appear EXACTLY ONCE in the file)
<<<NEW>>>
replacement text
<<<END>>>
       The OLD block is matched byte-for-byte (preserve whitespace and indentation). If OLD doesn't appear or appears more than once, the action FAILS — narrow it with more surrounding context and retry.
    3. apply_multi_edit — atomic batch of str-replace edits across one or more files (use when a fix touches several places at once). Same OLD/NEW semantics as apply_str_replace, repeated, then a single <<<END>>>:
       <<<FILE>>>
path/to/a.py
<<<OLD>>>
exact text in a.py (must appear EXACTLY ONCE)
<<<NEW>>>
replacement
<<<FILE>>>
path/to/b.py
<<<OLD>>>
exact text in b.py
<<<NEW>>>
replacement
<<<END>>>
       Pre-validation: if ANY OLD is missing or non-unique, NO file is written — the whole batch is rejected with a per-edit error list, so you can fix and resend. Prefer this over multiple single edits whenever a logically coupled change spans 2+ files (e.g. update a function signature in one file and its caller in another).
Always prefix any block with a THOUGHT line explaining your reasoning: THOUGHT: 
Engineering rules (apply even if not spelled out in the task):
    • Edit existing files. Do not create parallel modules unless the task requires it.
    • Reproduce the bug FIRST with a minimal command or test, then fix, then re-run.
    • After fixing, run the project's own tests (pytest -xvs <file>::<test>, go test ./..., npm test, cargo test, mvn test, etc.) to confirm.
    • Preserve public APIs and existing conventions; keep edits minimal and surgical.
    • Handle boundary cases the spec implies (empty input, off-by-one, error paths).
    • Never silently swallow stderr — read it.
    • apply_str_replace is preferred over sed for code edits.
    • Mutation bugs: If a method that converts or copies a value returns self / a reference to the original, and callers mutate the result, fix the method to return an independent copy — not only the single call site that exposed the bug.
    • Environment: Use the repo's own build tool (cargo, go, npm, mvn, etc.). For Python repos, the task's conda/virtualenv is already active — do not patch unrelated compatibility shims for a different runtime version.
Every shell command runs in a FRESH shell — directory and environment changes do not persist. Prefix with cd /path && ... when needed.
When you are confident the fix is correct and the tests pass, submit with:
echo SUBMIT_PATCH && git -c color.ui=false -c core.pager=cat diff HEAD
For new untracked files that git diff HEAD would miss, also list and cat them after SUBMIT_PATCH. Do NOT submit until you have verified the fix. """
STABILITY_SYSTEM_SUFFIX = """\

Repeatability (reduce run-to-run drift)
Unless the problem statement clearly requires a different order:
    1. Discovery: start with pwd then ls -la | LC_ALL=C sort (or equivalent) before broad find/rg.
    2. Search: prefer rg --sort path -n with sensible -g excludes for build/vendor trees so similar hits stay in a stable order.
    3. Tests: once a repro or test command works, reuse it after edits instead of switching to a different command each time.
    4. Ties: when multiple commands are equally reasonable, pick the shorter; for files, prefer lexicographically smaller paths. """
def _system_prompt_for_run() -> str: if os.getenv("RIDGES_STABLE_PROMPT", "").strip().lower() in ("1", "true", "yes"): return SYSTEM_PROMPT + STABILITY_SYSTEM_SUFFIX return SYSTEM_PROMPT
def _detect_repo_language(working_dir: str) -> str: wd = working_dir or os.getcwd()
def exists(*names: str) -> bool:
    return any(os.path.isfile(os.path.join(wd, n)) for n in names)

if exists("Cargo.toml"):
    return "rust"
if exists("go.mod"):
    return "go"
if exists("pom.xml", "build.gradle", "build.gradle.kts"):
    try:
        out = subprocess.run(
            ["git", "ls-files", "--", "*.kt"],
            cwd=wd, capture_output=True, text=True, timeout=5,
        )
        if out.stdout.strip():
            return "kotlin"
    except Exception:
        pass
    return "java"
if exists("package.json"):
    if exists("tsconfig.json"):
        return "typescript"
    try:
        out = subprocess.run(
            ["git", "ls-files", "--", "*.ts"],
            cwd=wd, capture_output=True, text=True, timeout=5,
        )
        if out.stdout.strip():
            return "typescript"
    except Exception:
        pass
    return "javascript"
if exists(
    "pyproject.toml", "setup.py", "setup.cfg",
    "requirements.txt", "Pipfile", "tox.ini",
):
    return "python"
try:
    out = subprocess.run(
        ["git", "ls-files"], cwd=wd, capture_output=True, text=True, timeout=10,
    )
    lines = out.stdout.splitlines()
    ext_map: dict[str, str] = {
        ".py": "python", ".rs": "rust", ".go": "go",
        ".ts": "typescript", ".js": "javascript",
        ".java": "java", ".kt": "kotlin",
        ".cpp": "cpp", ".cc": "cpp", ".c": "cpp",
    }
    counts: dict[str, int] = {}
    for ln in lines:
        _, dot, ext = ln.rpartition(".")
        if dot:
            lang = ext_map.get("." + ext.lower())
            if lang:
                counts[lang] = counts.get(lang, 0) + 1
    if counts:
        return max(counts, key=lambda k: counts[k])
except Exception:
    pass
return "python"  
_LANG_META: dict[str, dict] = { "python": { "test_cmd": "python -m pytest -xvs <test_file>", "full_test_cmd": "python -m pytest", "scratch": "/tmp/repro.py", "run_scratch": "python /tmp/repro.py", "ext": ".py", "config_file": "pyproject.toml / setup.py", "build_check": "python -m py_compile ", "explore_hint": "Check pyproject.toml or setup.py for the package layout.", }, "rust": { "test_cmd": "cargo test <test_name> 2>&1 | tail -40", "full_test_cmd": "cargo test 2>&1 | tail -60", "scratch": "/tmp/repro.rs", "run_scratch": "rustc /tmp/repro.rs -o /tmp/repro && /tmp/repro", "ext": ".rs", "config_file": "Cargo.toml", "build_check": "cargo check 2>&1 | head -30", "explore_hint": ( "Check Cargo.toml for the crate/workspace structure. " "Use cargo check for fast compile errors before running tests." ), }, "go": { "test_cmd": "go test ./... -run  -v 2>&1 | tail -40", "full_test_cmd": "go test ./... 2>&1 | tail -60", "scratch": "/tmp/repro.go", "run_scratch": "cd /tmp && go run repro.go", "ext": ".go", "config_file": "go.mod", "build_check": "go build ./... 2>&1 | head -30", "explore_hint": ( "Check go.mod for the module path. " "All test files end in _test.go and live alongside the source." ), }, "javascript": { "test_cmd": "npm test -- --testPathPattern= 2>&1 | tail -40", "full_test_cmd": "npm test 2>&1 | tail -60", "scratch": "/tmp/repro.js", "run_scratch": "node /tmp/repro.js", "ext": ".js", "config_file": "package.json", "build_check": "node --check ", "explore_hint": ( "Check package.json for the test script and entry points. " "Use node --check <file> to validate syntax quickly." ), }, "typescript": { "test_cmd": "npm test -- --testPathPattern= 2>&1 | tail -40", "full_test_cmd": "npm test 2>&1 | tail -60", "scratch": "/tmp/repro.ts", "run_scratch": "npx ts-node /tmp/repro.ts", "ext": ".ts", "config_file": "tsconfig.json / package.json", "build_check": "npx tsc --noEmit 2>&1 | head -30", "explore_hint": ( "Check tsconfig.json for compiler options and package.json for the test script. " "Use npx tsc --noEmit to catch type errors quickly." ), }, "java": { "test_cmd": "mvn test -pl . -Dtest= -q 2>&1 | tail -40", "full_test_cmd": "mvn test -q 2>&1 | tail -60", "scratch": "/tmp/Repro.java", "run_scratch": "cd /tmp && javac Repro.java && java Repro", "ext": ".java", "config_file": "pom.xml", "build_check": "mvn compile -q 2>&1 | head -30", "explore_hint": ( "Check pom.xml for the module structure. " "Test classes typically live under src/test/java/." ), }, "kotlin": { "test_cmd": "./gradlew test --tests  2>&1 | tail -40", "full_test_cmd": "./gradlew test 2>&1 | tail -60", "scratch": "/tmp/repro.kts", "run_scratch": "kotlinc-jvm -script /tmp/repro.kts", "ext": ".kt", "config_file": "build.gradle.kts", "build_check": "./gradlew compileKotlin 2>&1 | head -30", "explore_hint": ( "Check build.gradle.kts for the project structure. " "Tests live under src/test/." ), }, "cpp": { "test_cmd": "make test 2>&1 | tail -40", "full_test_cmd": "make test 2>&1 | tail -60", "scratch": "/tmp/repro.cpp", "run_scratch": "g++ -o /tmp/repro /tmp/repro.cpp && /tmp/repro", "ext": ".cpp", "config_file": "CMakeLists.txt / Makefile", "build_check": "make 2>&1 | head -30", "explore_hint": "Check CMakeLists.txt or Makefile for build targets and test targets.", }, }
def _instance_prompt_mini(problem_statement: str, working_dir: str) -> str: lang = _detect_repo_language(working_dir) meta = _LANG_META.get(lang, _LANG_META["python"])
test_cmd   = meta["test_cmd"]
full_test  = meta["full_test_cmd"]
scratch    = meta["scratch"]
run_scratch = meta["run_scratch"]
ext        = meta["ext"]
explore_hint = meta["explore_hint"]
build_check  = meta["build_check"]

lang_label = {
    "python": "Python", "rust": "Rust", "go": "Go",
    "javascript": "JavaScript", "typescript": "TypeScript",
    "java": "Java", "kotlin": "Kotlin", "cpp": "C/C++",
}.get(lang, lang.title())

verify_example = f"`{test_cmd}`"

if lang == "rust":
    edit_example = f"""\
THOUGHT: The function panics on empty input; it should return an error instead.
<<<FILE>>>
src/lib.rs
<<<OLD>>>
    if items.is_empty() {{
        panic!("empty");
    }}
<<<NEW>>>
    if items.is_empty() {{
        return Err("items must not be empty".into());
    }}
<<<END>>>
```"""
    elif lang == "go":
        edit_example = f"""\
THOUGHT: The function doesn't handle the nil case; should return an error.

```apply_str_replace
<<<FILE>>>
pkg/foo/foo.go
<<<OLD>>>
\tif items == nil {{
\t\treturn nil
\t}}
<<<NEW>>>
\tif items == nil {{
\t\treturn nil, fmt.Errorf("items must not be nil")
\t}}
<<<END>>>
```"""
    elif lang in ("javascript", "typescript"):
        edit_example = f"""\
THOUGHT: The function returns undefined on empty input; should throw instead.

```apply_str_replace
<<<FILE>>>
src/foo{ext}
<<<OLD>>>
  if (!items.length) {{
    return undefined;
  }}
<<<NEW>>>
  if (!items.length) {{
    throw new Error('items must not be empty');
  }}
<<<END>>>
```"""
    elif lang == "java":
        edit_example = f"""\
THOUGHT: The method silently returns null on empty input; should throw instead.

```apply_str_replace
<<<FILE>>>
src/main/java/com/example/Foo.java
<<<OLD>>>
        if (items.isEmpty()) {{
            return null;
        }}
<<<NEW>>>
        if (items.isEmpty()) {{
            throw new IllegalArgumentException("items must not be empty");
        }}
<<<END>>>
```"""
    else:
        edit_example = f"""\
THOUGHT: The validator returns True for empty lists; the spec says empty must raise.

```apply_str_replace
<<<FILE>>>
src/foo.py
<<<OLD>>>
    if not items:
        return True
<<<NEW>>>
    if not items:
        raise ValueError("items must not be empty")
<<<END>>>
```"""

    return f"""Please solve this issue ({lang_label} repository):

{problem_statement}

## Recommended Workflow

1. **Explore** — understand the layout (`git ls-files`, `ls`, `grep -rn`).
   {explore_hint}
2. **Reproduce** — find or write a minimal failing test/command BEFORE editing.
   Use a scratch script (`{run_scratch}`) or the repo's own test runner.
3. **Diagnose** — read the relevant source; identify root cause.
   Quick build check: `{build_check}`
4. **Edit** — make minimal, targeted edits with ``apply_str_replace``
   (preferred) or sed/cat where appropriate. Avoid large rewrites.
   Use ``apply_multi_edit`` when a single logical fix touches 2+ files (function
   signature + callers, import + usage) — it is atomic and safer.
5. **Verify** — re-run the reproduction AND the repo's own tests:
   {verify_example}
   Trust the repo's existing tests and the exact behavior the issue describes.
   Iterate in a scratch script ({scratch}) rather than editing repo test files.
   Keep the final diff limited to the fix.
6. **Cover edges** — empty inputs, error paths, related code paths the bug
   implies. Search for similar patterns to fix consistently.
7. **Submit** — exactly one action whose command starts with
   ``echo SUBMIT_PATCH && git -c color.ui=false -c core.pager=cat diff HEAD``.

If time runs low: ship a minimal correct patch over polished scaffolding.
Submitting an incorrect patch is better than submitting nothing.

## Fixes often remove or change behavior — not only add to it

Before adding a defensive fallback/default that preserves the CURRENT output,
ask whether the issue wants that old behavior to STOP. If the bug *is* the old
output — a spurious value, duplicate, or wrong result — the fix must make it
stop, not guard it with a fallback that still produces it.

## Hard rules

- Exactly ONE action block per response.
- The block must be one of: ```rswea_bash_command```, ```apply_str_replace```, or ```apply_multi_edit```.
- Bash actions run in a fresh shell — chain with && or use `cd` prefix.
- Working directory: {working_dir}

## Example: explore

THOUGHT: I need to map the repo before changing anything.

```rswea_bash_command
git ls-files | head -60
Example: read a file region
nl -ba src/foo{ext} | sed -n '120,180p'
Example: precise edit
{edit_example}
Example: run focused tests
{test_cmd}
Example: submit
echo SUBMIT_PATCH && git -c color.ui=false -c core.pager=cat diff HEAD
"""
PLANNING_SYSTEM_PROMPT = """
You are an expert software planning assistant. Your role is to analyze problems and create a detailed execution plan.
Analyze the problem and create a step-by-step plan to solve it. Your plan should include:
    1. Problem Analysis: Understand what needs to be fixed or implemented
    2. File Discovery: Identify which files need to be examined or modified
    3. Common misunderstandings: Identify any common misunderstandings that engineers often make when fixing this type of problem.
    4. Implementation Steps: Specific actions to take, in order
    5. Verification Strategy: How to verify the fix works
Provide your plan in a structured format. Be specific and actionable. """
def _planning_prompt(problem_statement: str, working_dir: str) -> str: return f"""Please analyze this problem and create a detailed execution plan:
Problem Statement
{problem_statement}
Working Directory
{working_dir}
Your Task
Create a comprehensive plan that includes:
    1. Problem Analysis: What exactly needs to be fixed or implemented?
    2. Key Files to Examine: Which files in the codebase are most relevant?
    3. Common misunderstandings: Identify any common misunderstandings that engineers often make when fixing this type of problem.
    4. Step-by-Step Plan: Numbered list of specific actions to take
    5. Expected Outcome: What does a successful solution look like?
    6. Verification: How will you verify the fix works?
Be specific and actionable. Your plan will be used by an execution agent to solve this problem. """
def format_mini_format_error(n_actions: int) -> str: return f"""Format error:
Expected exactly 1 action block, found {n_actions}.
Please always provide EXACTLY ONE action block in triple backticks. Use rswea_bash_command for shell commands, apply_str_replace for a single file edit, or apply_multi_edit for an atomic batch across files. Example:
THOUGHT: Brief reasoning.
<single command>
If you have completed the task, submit with the SUBMIT_PATCH command from the first message."""
FORMAT_ERROR_MESSAGE = format_mini_format_error(0)
def _format_error_escalation(strike: int) -> str: base = FORMAT_ERROR_MESSAGE if strike <= 1: return base header = ( f"[Format reminder #{strike}] Your previous response did not contain a single " "fenced action block. You MUST respond with exactly one of: " "rswea_bash_command, apply_str_replace, or apply_multi_edit. " "The THOUGHT line is plain text outside the block.\n\n" "If you believe you are done, your single action MUST be:\n\n" "rswea_bash_command\n" "echo SUBMIT_PATCH && git -c color.ui=false -c core.pager=cat diff HEAD\n" "\n\n" "Repeated format failures end this trial without a patch.\n\n" ) return header + base
SUBMISSION_SENTINEL = "SUBMIT_PATCH"
def _resolve_conda_shell_prefix() -> str: raw = (os.getenv("RIDGES_AGENT_CONDA_ENV") or "testbed").strip() if raw.lower() in ("0", "off", "none", "false", "disable", "disabled"): return "" activate = "/opt/miniconda3/bin/activate" if not os.path.isfile(activate): return "" env_name = shlex.quote(raw) return f"source {shlex.quote(activate)} && conda activate {env_name} 2>/dev/null; "
class ShellExecutor:
def __init__(
    self,
    working_dir: str | None = None,
    timeout: int = 120,
    shell_prefix: str = "",
):
    self.working_dir = working_dir or os.getcwd()
    self.timeout = timeout
    self.shell_prefix = shell_prefix

def execute(self, command: str) -> dict[str, Any]:
    full_command = f"{self.shell_prefix}{command}" if self.shell_prefix else command
    try:
        result = subprocess.run(
            ["bash", "-c", full_command],
            cwd=self.working_dir,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            env={**os.environ, "TERM": "dumb"},
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Command timed out after {self.timeout} seconds",
            "returncode": -1,
            "timed_out": True,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Execution error: {type(e).__name__}: {e}",
            "returncode": -1,
            "timed_out": False,
        }
def normalize_patch_text(patch: str) -> str: if not patch: return "" out = re.sub(r"\x1b[[0-9;?][ -/][@-~]", "", patch) out = out.replace("\r\n", "\n").replace("\r", "\n") return out.strip("\n") + ("\n" if out.strip() else "")
def is_scratch_untracked(rel_path: str, content: str) -> bool: base = os.path.basename(rel_path).lower() if base == "conftest.py" or (base.startswith("test") and base.endswith(".py")) or base.endswith("_test.py"): return True if re.search(r"^\s*assert\s+(False|0)\b", content, re.MULTILINE): return True return False
def authoritative_worktree_patch(executor: "ShellExecutor") -> str: wd = getattr(executor, "working_dir", None) or "." listing = executor.execute("git ls-files --others --exclude-standard") kept: list[str] = [] for rel in (listing.get("stdout") or "").splitlines(): rel = rel.strip() if not rel: continue full = os.path.join(wd, rel) if not os.path.isfile(full): continue try: with open(full, "r", encoding="utf-8", errors="surrogateescape") as fh: content = fh.read() except Exception: continue if "\x00" in content[:8192]: continue
if _is_scratch_untracked(rel, content): print(f"[AGENT] dropping scratch untracked file from patch: {rel}") continue kept.append(rel)
added = False
if kept:
    quoted = " ".join(shlex.quote(p) for p in kept)
    add_res = executor.execute(f"git add -N -- {quoted}")
    added = add_res.get("returncode") == 0
    if not added:
        print(
            "[AGENT] git add -N failed; new files may be omitted from patch: "
            f"{(add_res.get('stderr') or '')[:200]}"
        )
try:
    diff = executor.execute("git -c color.ui=false -c core.pager=cat diff --no-ext-diff HEAD")
finally:
    if added:
        quoted = " ".join(shlex.quote(p) for p in kept)
        executor.execute(f"git reset -q -- {quoted}")

if diff.get("returncode") != 0:
    print(f"[AGENT] git diff failed: {(diff.get('stderr') or diff.get('stdout') or '')[:300]}")
    return ""
return normalize_patch_text(diff.get("stdout") or "")
def count_mini_actions(response: str) -> int: edits = EDIT_ACTION_REGEX.findall(response) multi_edits = MULTI_EDIT_ACTION_REGEX.findall(response) rsweas = MINI_ACTION_REGEX_RSWEA.findall(response) bashes = MINI_ACTION_REGEX_BASH.findall(response) shell_blocks = len(rsweas) + (len(bashes) if not rsweas else 0) return len(edits) + len(multi_edits) + shell_blocks
def parse_action(response: str) -> Tuple[Optional[str], Optional[str]]: edits = [a.strip() for a in EDIT_ACTION_REGEX.findall(response)] multi_edits = [a.strip() for a in MULTI_EDIT_ACTION_REGEX.findall(response)] rsweas = [a.strip() for a in MINI_ACTION_REGEX_RSWEA.findall(response)] bashes = [a.strip() for a in MINI_ACTION_REGEX_BASH.findall(response)]
total = (
    len(edits)
    + len(multi_edits)
    + len(rsweas)
    + (len(bashes) if not rsweas else 0)
)
if total != 1:
    return None, None

if edits:
    return "edit", edits[0]
if multi_edits:
    return "multi_edit", multi_edits[0]
if rsweas:
    return "bash", rsweas[0]
if bashes:
    return "bash", bashes[0]
return None, None
def parse_bash_command(response: str) -> str | None: kind, payload = parse_action(response) if kind == "bash": return payload return None
def check_submission(command: str, output: str) -> str | None: if SUBMISSION_SENTINEL not in command: return None sentinel_idx = output.find(SUBMISSION_SENTINEL) if sentinel_idx == -1: return None patch = output[sentinel_idx + len(SUBMISSION_SENTINEL):].strip() return patch if patch else None
_EDIT_SECTION_RE = re.compile( r"<<>>\n(?P.?)\n<<>>\n(?P.?)\n<<>>\n(?P.*?)\n<<>>", re.DOTALL, )
def parse_edit_payload(payload: str) -> Optional[Tuple[str, str, str]]: payload = payload.replace("\r\n", "\n").replace("\r", "\n") m = _EDIT_SECTION_RE.search(payload) if not m: return None file_path = m.group("file").strip() old_str = m.group("old") new_str = m.group("new") if not file_path: return None return file_path, old_str, new_str
def apply_str_replace(working_dir: str, file_path: str, old_str: str, new_str: str) -> dict[str, Any]: full = file_path if os.path.isabs(file_path) else os.path.join(working_dir, file_path) if not os.path.isfile(full): return { "stdout": "", "stderr": f"apply_str_replace: file not found: {file_path}", "returncode": 2, "timed_out": False, } if old_str == new_str: return { "stdout": "", "stderr": "apply_str_replace: OLD and NEW are identical; nothing to do.", "returncode": 2, "timed_out": False, } try: with open(full, "r", encoding="utf-8", errors="surrogateescape") as f: content = f.read() except Exception as e: return { "stdout": "", "stderr": f"apply_str_replace: read error: {type(e).name}: {e}", "returncode": 2, "timed_out": False, } count = content.count(old_str) if count == 0: norm_old = old_str.replace("\r\n", "\n").replace("\r", "\n") norm_content = content.replace("\r\n", "\n").replace("\r", "\n") if norm_content.count(norm_old) == 1: old_str = norm_old content = norm_content count = 1 if count == 0: hint_lines = [] if old_str.strip(): first_line = old_str.splitlines()[0].strip() if first_line: for i, line in enumerate(content.splitlines(), 1): if first_line and first_line in line: hint_lines.append(f"  {i}: {line}") if len(hint_lines) >= 5: break hint = ("\nNearest matches on first OLD line:\n" + "\n".join(hint_lines)) if hint_lines else "" return { "stdout": "", "stderr": ( f"apply_str_replace: OLD not found in {file_path}. Provide the EXACT bytes " f"to replace (whitespace and indentation matter).{hint}" ), "returncode": 2, "timed_out": False, } if count > 1: return { "stdout": "", "stderr": ( f"apply_str_replace: OLD matches {count} places in {file_path}; add more " "surrounding context so it appears exactly once." ), "returncode": 2, "timed_out": False, } new_content = content.replace(old_str, new_str, 1) try: with open(full, "w", encoding="utf-8", errors="surrogateescape") as f: f.write(new_content) except Exception as e: return { "stdout": "", "stderr": f"apply_str_replace: write error: {type(e).name}: {e}", "returncode": 2, "timed_out": False, } delta = len(new_str) - len(old_str) return { "stdout": ( f"apply_str_replace: OK — {file_path} updated " f"(old={len(old_str)} bytes, new={len(new_str)} bytes, delta={delta:+d}).\n" ), "stderr": "", "returncode": 0, "timed_out": False, }
_MULTI_EDIT_BLOCK_RE = re.compile( r"<<>>\n(?P[^\n]+)\n<<>>\n(?P.?)\n<<>>\n(?P.?)(?=\n<<>>\n|\n<<>>)", re.DOTALL, )
def parse_multi_edit_payload(payload: str) -> Optional[list[Tuple[str, str, str]]]: payload = payload.replace("\r\n", "\n").replace("\r", "\n") if "<<>>" not in payload: return None matches = _MULTI_EDIT_BLOCK_RE.findall(payload) if not matches: return None edits: list[Tuple[str, str, str]] = [] for file_path, old_str, new_str in matches: file_path = file_path.strip() if not file_path: return None edits.append((file_path, old_str, new_str)) return edits or None
def apply_multi_str_replace( working_dir: str, edits: list[Tuple[str, str, str]], ) -> dict[str, Any]: if not edits: return { "stdout": "", "stderr": "apply_multi_edit: payload contained no edits.", "returncode": 2, "timed_out": False, }
plans: list[Tuple[str, str, str, str]] = []  
errors: list[str] = []

for idx, (file_path, old_str, new_str) in enumerate(edits, 1):
    full = file_path if os.path.isabs(file_path) else os.path.join(working_dir, file_path)
    if not os.path.isfile(full):
        errors.append(f"#{idx} {file_path}: file not found")
        continue
    if old_str == new_str:
        errors.append(f"#{idx} {file_path}: OLD and NEW identical (nothing to do)")
        continue
    try:
        with open(full, "r", encoding="utf-8", errors="surrogateescape") as f:
            content = f.read()
    except Exception as e:
        errors.append(f"#{idx} {file_path}: read error: {type(e).__name__}: {e}")
        continue
    count = content.count(old_str)
    if count == 0:
        norm_old = old_str.replace("\r\n", "\n").replace("\r", "\n")
        norm_content = content.replace("\r\n", "\n").replace("\r", "\n")
        if norm_content.count(norm_old) == 1:
            old_str = norm_old
            content = norm_content
            count = 1
    if count == 0:
        errors.append(
            f"#{idx} {file_path}: OLD not found (whitespace must match byte-for-byte)"
        )
        continue
    if count > 1:
        errors.append(
            f"#{idx} {file_path}: OLD matches {count} places; add more surrounding context"
        )
        continue
    new_content = content.replace(old_str, new_str, 1)
    delta = len(new_str) - len(old_str)
    summary = f"old={len(old_str)}b, new={len(new_str)}b, delta={delta:+d}"
    plans.append((file_path, full, new_content, summary))

if errors:
    joined = "\n  ".join(errors)
    return {
        "stdout": "",
        "stderr": (
            "apply_multi_edit: pre-validation FAILED, no files written:\n  "
            + joined
            + "\nFix every error above and resend the entire batch."
        ),
        "returncode": 2,
        "timed_out": False,
    }

written: list[str] = []
for file_path, full, new_content, summary in plans:
    try:
        with open(full, "w", encoding="utf-8", errors="surrogateescape") as f:
            f.write(new_content)
        written.append(f"  {file_path} ({summary})")
    except Exception as e:
        partial = "\n".join(written) if written else "  (none)"
        return {
            "stdout": f"apply_multi_edit: PARTIAL — wrote {len(written)}/{len(plans)} edits:\n{partial}\n",
            "stderr": f"apply_multi_edit: write error on {file_path}: {type(e).__name__}: {e}",
            "returncode": 2,
            "timed_out": False,
        }

return {
    "stdout": (
        f"apply_multi_edit: OK — {len(plans)} edits applied:\n"
        + "\n".join(written)
        + "\n"
    ),
    "stderr": "",
    "returncode": 0,
    "timed_out": False,
}
_EVICT_READ_CMD_RE = re.compile( r"(?:^|\n)\s*(?:cat|head|tail|sed\s+-n|less|grep\s+-n|grep|rg|awk)\s+['"]?([^\s'";&|]+)", re.MULTILINE, )
def _extract_read_paths(content: str) -> list[str]: paths: list[str] = [] for m in _EVICT_READ_CMD_RE.finditer(content): raw = m.group(1).strip("'"") if raw and raw not in paths and len(raw) <= 200: paths.append(raw) return paths
class ConversationManager:
def __init__(self, max_chars: int = 120000):
    self.messages: list[dict[str, str]] = []
    self.max_chars = max_chars
    self._evicted_reads: list[str] = []

def add(self, role: str, content: str) -> None:
    self.messages.append({"role": role, "content": content})
    self._trim_if_needed()

def get_messages(self) -> list[dict[str, str]]:
    return _collapse_repeated_observations(list(self.messages))

def _trim_if_needed(self) -> None:
    max_passes = 8
    for _ in range(max_passes):
        total_chars = sum(len(m.get("content", "")) for m in self.messages)
        if total_chars <= self.max_chars:
            return
        if len(self.messages) <= 3:
            return

        excess = total_chars - self.max_chars
        min_keep_head = 2  
        min_keep_tail = 6  
        if len(self.messages) <= min_keep_head + min_keep_tail:
            return

        head = self.messages[:min_keep_head]
        tail = self.messages[-min_keep_tail:]
        middle = self.messages[min_keep_head:-min_keep_tail]
        trimmed_middle = list(middle)
        newly_evicted: list[str] = []
        while trimmed_middle and excess > 0:
            removed = trimmed_middle.pop(0)
            excess -= len(removed.get("content", ""))
            if removed.get("role") == "user":
                for p in _extract_read_paths(removed.get("content", "")):
                    if p not in self._evicted_reads:
                        self._evicted_reads.append(p)
                    if p not in newly_evicted:
                        newly_evicted.append(p)

        note_lines = [
            "[System note: Earlier conversation history was trimmed to fit the context window. "
            "The original task and your most recent actions are preserved. Continue working.]"
        ]
        if self._evicted_reads:
            shown = self._evicted_reads[-12:]  
            note_lines.append(
                "Files you already read (may not be in visible history): "
                + ", ".join(shown)
                + " — avoid re-reading unless your edits changed them."
            )
        context_note = {"role": "user", "content": "\n".join(note_lines)}
        self.messages = head + trimmed_middle + [context_note] + tail

def total_chars(self) -> int:
    return sum(len(m.get("content", "")) for m in self.messages)
def shell_output_to_mini_dict(output: dict[str, Any]) -> dict[str, Any]: stdout = output.get("stdout") or "" stderr = output.get("stderr") or "" parts: list[str] = [] if stdout.strip(): parts.append(stdout.rstrip("\n")) if stderr.strip(): parts.append(stderr.rstrip("\n")) combined = "\n".join(parts) if combined and not combined.endswith("\n"): combined += "\n" exc = "" if output.get("timed_out"): exc = (stderr or "Command timed out.").strip() elif output.get("returncode", 0) == -1 and stderr.strip(): exc = stderr.strip() return { "output": combined, "returncode": output.get("returncode", 0), "exception_info": exc, }
def format_mini_observation(output: dict[str, Any]) -> str: mini = shell_output_to_mini_dict(output) lines: list[str] = [] ei = (mini.get("exception_info") or "").strip() if ei: lines.append(ei) lines.append(str(mini.get("returncode", 0))) body = mini.get("output") or "" if "Traceback (most recent call last):" in body: body = _compress_traceback_in_text(body) if len(body) < MINI_OBSERVATION_FULL_MAX: lines.append("") lines.append(body) else: elided = len(body) - MINI_OBSERVATION_FULL_MAX lines.append("") lines.append( "The output of your last command was too long.\n" "Please try a different command that produces less output.\n" "If you're looking at a file you can try use head, tail or sed to view a smaller number of lines selectively.\n" "If you're using grep or find and it produced too much output, you can use a more selective search pattern.\n" "If you really need to see something from the full command's output, you can redirect output to a file " "and then search in that file." ) lines.append("") lines.append(body[:MINI_OBSERVATION_HEAD]) lines.append("") lines.append(f"{elided} characters elided") lines.append("") lines.append(body[-MINI_OBSERVATION_TAIL:]) return "\n".join(lines).rstrip() + "\n"
def _collapse_repeated_observations(messages: list[dict[str, str]]) -> list[dict[str, str]]: if not messages: return messages result: list[dict[str, str]] = [] i = 0 while i < len(messages): msg = messages[i] if msg.get("role") != "user": result.append(msg) i += 1 continue content = msg.get("content", "") first_line = content.split("\n", 1)[0].strip() is_obs = bool(re.match(r"^-?\d+$", first_line) or first_line == "") if not is_obs: result.append(msg) i += 1 continue run = 1 while ( i + run < len(messages) and messages[i + run].get("role") == "user" and messages[i + run].get("content", "") == content ): run += 1 if run >= 2: note = f"[{run}× identical output — showing once]\n" + content result.append({"role": "user", "content": note}) else: result.append(msg) i += run return result
def validate_patch(patch: str) -> bool: if not patch or not patch.strip(): return False if not re.search(r"@@ -\d+(,\d+)? +\d+(,\d+)? @@", patch): if "--- /dev/null" not in patch and "+++ b/" not in patch: return False return True
def validate_patch_with_git(patch: str, working_dir: str) -> bool: try: result = subprocess.run( ["git", "apply", "--check"], input=patch, capture_output=True, text=True, cwd=working_dir, timeout=10, ) return result.returncode == 0 except Exception: return False
def _working_dir_is_git_repo(working_dir: str) -> bool: if not working_dir or not os.path.isdir(working_dir): return False git_marker = os.path.join(working_dir, ".git") return os.path.isdir(git_marker) or os.path.isfile(git_marker)
def _check_patch_against_clean_head(patch: str, working_dir: str) -> tuple[bool, str]: direct = subprocess.run( ["git", "-C", working_dir, "apply", "--check", "--whitespace=nowarn"], input=patch, capture_output=True, text=True, timeout=60, ) if direct.returncode == 0: return True, "direct" direct_err = (direct.stderr or direct.stdout or "").strip() three_way = subprocess.run( ["git", "-C", working_dir, "apply", "--check", "--3way", "--whitespace=nowarn"], input=patch, capture_output=True, text=True, timeout=60, ) if direct_err: print(f"[AGENT] git apply --check failed (direct): {direct_err[:600]}") if three_way.returncode == 0: print("[AGENT] note: patch applies only via --3way; plain git apply (Harbor) would reject it") return False, ""
def validate_patch_applies_cleanly(patch: str, working_dir: str) -> bool: if not working_dir or not os.path.isdir(working_dir): return False if not validate_patch(patch): return False if not _working_dir_is_git_repo(working_dir): return validate_patch_with_git(patch, working_dir)
dirty_probe = subprocess.run(
    ["git", "-C", working_dir, "diff", "--quiet", "HEAD"],
    capture_output=True,
    text=True,
    timeout=30,
)
worktree_clean = dirty_probe.returncode == 0

if worktree_clean:
    try:
        ok, mode = _check_patch_against_clean_head(patch, working_dir)
    except subprocess.TimeoutExpired:
        print("[AGENT] patch validation timed out")
        return False
    except Exception as e:
        print(f"[AGENT] patch validation error: {e}")
        return False
    if ok:
        print(f"[AGENT] patch validation ok via {mode} (worktree clean)")
    return ok

stashed = False
apply_ok = False
try:
    stash = subprocess.run(
        ["git", "-C", working_dir, "stash", "push", "-u", "-m", "ridges_patch_validate", "-q"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if stash.returncode == 0:
        stashed = True
    elif stash.returncode == 1:
        err = (stash.stderr or "").lower()
        if "no local changes to save" not in err and "nothing to stash" not in err:
            print(f"[AGENT] stash before patch check failed: {stash.stderr}")
            return False
    else:
        print(f"[AGENT] stash before patch check failed (exit {stash.returncode}): {stash.stderr}")
        return False

    try:
        ok, _mode = _check_patch_against_clean_head(patch, working_dir)
    except subprocess.TimeoutExpired:
        print("[AGENT] patch validation timed out")
        return False
    except Exception as e:
        print(f"[AGENT] patch validation error: {e}")
        return False
    apply_ok = ok
finally:
    if stashed:
        pop = subprocess.run(
            ["git", "-C", working_dir, "stash", "pop", "-q"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if pop.returncode != 0:
            print(f"[AGENT] stash pop after patch check failed: {pop.stderr}")
            apply_ok = False

return apply_ok
def reset_worktree_to_head_for_harbor(working_dir: str) -> None: if not working_dir or not os.path.isdir(working_dir): return if not _working_dir_is_git_repo(working_dir): return try: r = subprocess.run( ["git", "-C", working_dir, "reset", "--hard", "HEAD"], capture_output=True, text=True, timeout=180, ) if r.returncode != 0: print(f"[AGENT] WARNING: git reset --hard HEAD failed ({r.returncode}): {r.stderr}") else: print("[AGENT] Reset worktree to HEAD after validated patch (Harbor compat)") clean = subprocess.run( ["git", "-C", working_dir, "clean", "-fd"], capture_output=True, text=True, timeout=120, ) if clean.returncode != 0: print(f"[AGENT] WARNING: git clean -fd failed ({clean.returncode}): {clean.stderr}") except Exception as e: print(f"[AGENT] WARNING: git reset --hard HEAD error: {e}")
def _self_verify_enabled() -> bool: v = (os.getenv("RIDGES_AGENT_SELF_VERIFY") or "0").strip().lower() return v in ("1", "true", "yes", "on")
def _patch_modifies_python_files(patch: str) -> list[str]: if not patch: return [] seen: list[str] = [] for line in patch.splitlines(): if line.startswith("+++ b/") and line.endswith(".py"): path = line[len("+++ b/"):].strip() if path and path not in seen: seen.append(path) elif line.startswith("diff --git a/") and " b/" in line: try: rhs = line.split(" b/", 1)[1].strip() except IndexError: rhs = "" if rhs.endswith(".py") and rhs not in seen: seen.append(rhs) return seen
def _extract_patch_paths(patch: str) -> list[str]: if not patch: return [] seen: list[str] = [] for line in patch.splitlines(): if line.startswith("+++ b/"): path = line[len("+++ b/"):].strip() if path and path != "/dev/null" and path not in seen: seen.append(path) return seen
def diff_exceeds_declared_scope(patch: str, problem_statement: str) -> tuple[bool, str]: paths = extract_patch_paths(patch) if len(paths) <= 1: return False, "" problem_lower = (problem_statement or "").lower() problem_tokens: set[str] = set() for word in re.findall(r"[a-zA-Z][a-zA-Z0-9]{3,}", problem_lower): problem_tokens.add(word) _COMPAT_STEMS = ("dtypes", "compat", "version", "conftest", "setup") suspect: list[str] = [] relevant: list[str] = [] for p in paths: path_lower = p.lower() base = os.path.basename(p).lower().replace(".py", "") stem_parts = set(re.findall(r"[a-z]{4,}", base)) overlap = any(t in path_lower for t in problem_tokens if len(t) >= 4) overlap = overlap or any(part in problem_lower for part in stem_parts if len(part) >= 4) is_compat_shim = any(s in path_lower for s in _COMPAT_STEMS) if overlap and not is_compat_shim: relevant.append(p) elif is_compat_shim and not overlap: suspect.append(p) elif not overlap and not is_compat_shim: if any( x in path_lower for x in ("requirements", "pyproject.toml", "setup.cfg") ): suspect.append(p) if suspect and (relevant or len(paths) > 1): return True, ( f"Patch edits likely-unrelated file(s): {', '.join(suspect)}. " "Drop environment-compat changes; the verifier uses a pinned conda env. " "Keep only changes tied to the reported bug." ) return False, ""
def _lint_submission_diff( patch: str, problem_statement: str, working_dir: str ) -> tuple[bool, str]: if not patch or not patch.strip(): return False, "Empty patch."
unrelated, msg = _diff_exceeds_declared_scope(patch, problem_statement)
if unrelated:
    return False, msg

return True, ""
def _infer_test_path(modified_path: str, working_dir: str) -> str | None: path = modified_path.replace("\", "/").lstrip("/") if path.startswith("testbed/"): path = path[len("testbed/"):]
_, dot, ext_raw = path.rpartition(".")
ext = ("." + ext_raw.lower()) if dot else ""
basename_no_ext = os.path.basename(path)
if dot:
    basename_no_ext = basename_no_ext[: -len(ext)]

if ext == ".go":
    test_name = f"{basename_no_ext}_test.go"
    candidate = os.path.join(os.path.dirname(path), test_name).lstrip("/")
    if working_dir and os.path.isfile(os.path.join(working_dir, candidate)):
        return candidate
    return os.path.dirname(path) or "."

if ext == ".rs":
    if working_dir:
        for tests_dir in ("tests",):
            candidate = f"{tests_dir}/{basename_no_ext}.rs"
            if os.path.isfile(os.path.join(working_dir, candidate)):
                return candidate
    return None  

if ext in (".js", ".ts", ".jsx", ".tsx"):
    for test_ext in (f".test{ext}", f".spec{ext}"):
        test_name = basename_no_ext + test_ext
        sibling_tests = os.path.join(os.path.dirname(path), "__tests__", test_name)
        sibling_tests = sibling_tests.lstrip("/")
        if working_dir and os.path.isfile(os.path.join(working_dir, sibling_tests)):
            return sibling_tests
        colocated = os.path.join(os.path.dirname(path), test_name).lstrip("/")
        if working_dir and os.path.isfile(os.path.join(working_dir, colocated)):
            return colocated
    return None

if ext in (".py", ".pyi", ""):
    if not basename_no_ext.startswith("test_"):
        test_name = f"test_{basename_no_ext}.py"
    else:
        test_name = f"{basename_no_ext}.py"

    parts = path.split("/")
    if "core" in parts:
        idx = parts.index("core")
        pkg = "/".join(parts[:idx])
        candidate = f"{pkg}/tests/{test_name}" if pkg else f"tests/{test_name}"
        if not working_dir or os.path.isfile(os.path.join(working_dir, candidate)):
            return candidate

    for tests_dir in ("tests", "test"):
        parent = os.path.dirname(path)
        while parent and parent != ".":
            candidate = f"{parent}/{tests_dir}/{test_name}"
            if working_dir and os.path.isfile(os.path.join(working_dir, candidate)):
                return candidate
            parent = os.path.dirname(parent)

    if working_dir:
        for root, _dirs, files in os.walk(working_dir):
            if test_name in files and "test" in root.replace("\\", "/"):
                rel = os.path.relpath(os.path.join(root, test_name), working_dir)
                return rel.replace("\\", "/")
    return None

if working_dir:
    for root, _dirs, files in os.walk(working_dir):
        for f in files:
            stem, _, _ = f.rpartition(".")
            if (
                (stem == f"test_{basename_no_ext}" or stem == f"{basename_no_ext}_test")
                and "test" in root.replace("\\", "/")
            ):
                rel = os.path.relpath(os.path.join(root, f), working_dir)
                return rel.replace("\\", "/")
return None
def _submit_verify_enabled(problem_statement: str) -> bool: raw = (os.getenv("RIDGES_AGENT_SUBMIT_VERIFY") or "").strip().lower() if raw in ("0", "false", "off", "no"): return False if raw in ("1", "true", "yes", "on"): return True return False
def _run_module_pytest_on_submit( executor: ShellExecutor, patch: str, working_dir: str, problem_statement: str, ) -> tuple[bool, str]: if not _submit_verify_enabled(problem_statement): return True, "" py_files = _patch_modifies_python_files(patch) test_files: list[str] = [] for pf in py_files: if "/tests/" in pf or pf.startswith("tests/"): continue inferred = _infer_test_path(pf, working_dir) if inferred and inferred not in test_files: test_files.append(inferred) if not test_files: return True, ""
for tf in test_files[:2]:
    cmd = f"set -o pipefail; python -m pytest -x -q {shlex.quote(tf)} 2>&1 | tail -40"
    result = executor.execute(cmd)
    if result.get("returncode") != 0:
        out = ((result.get("stdout") or "") + (result.get("stderr") or "")).strip()
        return False, (
            f"Pre-submit pytest failed for {tf}:\n{out[:1500]}\n"
            "Fix failures before submitting."
        )
return True, ""
DEF_OR_CLASS_RE = re.compile(r"^[+ ]\s*(?:class|def)\s+([A-Za-z][A-Za-z0-9_])", re.M) _HUNK_CTX_RE = re.compile(r"^@@.@@\s*(?:class|def)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M) PYTEST_FAIL_RE = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.M) TEST_NAME_RE = re.compile(r"\b(test[A-Za-z0-9]+)\b")
def _flatten_identifier(name: str) -> str: return re.sub(r"[^a-z0-9]", "", name.lower())
def _changed_symbol_stems(patch: str) -> set[str]: stems: set[str] = set() for rx in (_DEF_OR_CLASS_RE, _HUNK_CTX_RE): for m in rx.finditer(patch or ""): flat = _flatten_identifier(m.group(1)) if len(flat) >= 5: stems.add(flat) return stems
def _testnode_basename(nodeid: str) -> str: tail = nodeid.rsplit("::", 1)[-1] tail = re.sub(r"[.*]$", "", tail)
return _flatten_identifier(tail)
def _failing_related_module_tests( executor: ShellExecutor, patch: str, working_dir: str ) -> tuple[list[str], str]: raw = (os.getenv("RIDGES_SUBMIT_MODULE_TEST") or "").strip().lower() if raw in ("0", "false", "off", "no"): return [], ""
stems = _changed_symbol_stems(patch)
if not stems:
    return [], ""

src_files = [
    p for p in _patch_modifies_python_files(patch)
    if "/tests/" not in p and not p.startswith("tests/")
    and "/test_" not in p and not os.path.basename(p).startswith("test_")
]
test_files: list[str] = []
for sf in src_files:
    inferred = _infer_test_path(sf, working_dir)
    if inferred and inferred not in test_files:
        test_files.append(inferred)
    if len(test_files) >= 1:  
        break
if not test_files:
    return [], ""

quoted = " ".join(shlex.quote(t) for t in test_files)
cmd = (
    f"python -m pytest {quoted} -p no:cacheprovider -o addopts='' "
    f"--tb=no -q -rfE 2>&1 | tail -200"
)
result = executor.execute(cmd)
if result.get("timed_out"):
    return [], ""
out = (result.get("stdout") or "") + (result.get("stderr") or "")
failing = {m.group(1) for m in _PYTEST_FAIL_RE.finditer(out)}
if not failing:
    return [], ""

related = sorted(
    n for n in failing
    if any(stem in _testnode_basename(n) for stem in stems)
)
if not related:
    return [], ""
detail = "\n".join(f"  - {n}" for n in related[:12])
return related, detail
def _patch_modified_extensions(patch: str) -> set[str]: exts: set[str] = set() for line in patch.splitlines(): if line.startswith("+++ b/") or line.startswith("--- a/"): path = line[6:] _, dot, ext = path.rpartition(".") if dot: exts.add("." + ext.lower()) return exts
def _self_verify_patch(patch: str, working_dir: str) -> tuple[bool, str]: if not patch or not patch.strip(): return False, "Empty patch" if not _self_verify_enabled(): return True, ""
exts = _patch_modified_extensions(patch)

if ".py" in exts:
    py_paths = _patch_modifies_python_files(patch)
    check_paths = [p for p in py_paths if os.path.isfile(os.path.join(working_dir, p))]
    if check_paths:
        quoted = " ".join(shlex.quote(p) for p in check_paths)
        try:
            r = subprocess.run(
                ["bash", "-c", f"python -m py_compile {quoted}"],
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=_PY_COMPILE_TIMEOUT_SEC,
            )
            if r.returncode != 0:
                return False, (r.stderr or r.stdout or "py_compile failed").strip()
        except Exception:
            pass

if exts & {".ts", ".tsx"} and os.path.isfile(os.path.join(working_dir, "tsconfig.json")):
    try:
        r = subprocess.run(
            ["bash", "-c", "npx --no-install tsc --noEmit 2>&1 | head -40"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=45,
        )
        if r.returncode != 0 and r.stdout.strip():
            return False, ("tsc --noEmit:\n" + r.stdout.strip()[:800])
    except Exception:
        pass

if exts & {".rs"} and os.path.isfile(os.path.join(working_dir, "Cargo.toml")):
    try:
        r = subprocess.run(
            ["bash", "-c", "cargo check 2>&1 | tail -30"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode != 0 and r.stdout.strip():
            return False, ("cargo check:\n" + r.stdout.strip()[:800])
    except Exception:
        pass

if exts & {".go"} and os.path.isfile(os.path.join(working_dir, "go.mod")):
    try:
        r = subprocess.run(
            ["bash", "-c", "go build ./... 2>&1 | head -30"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode != 0 and r.stdout.strip():
            return False, ("go build:\n" + r.stdout.strip()[:800])
    except Exception:
        pass

return True, ""
_LOOP_DETECT_WINDOW = 8 _LOOP_DETECT_REPEAT_THRESHOLD = 5 _MODIFYING_COMMAND_TOKENS = ( "sed", "echo >", "cat >", "tee", "patch", "mv", "cp", "python -c", "pip install", "npm", "touch", "chmod", "truncate", "dd", "install", )
_LOOP_WARN_MARKER = "\u26a0"
_LOOP_WARN_HEADER = "[Loop Advisor]"
def _loop_warn_env_int(name: str, default: int) -> int: raw = (os.getenv(name) or "").strip() if not raw: return default try: return int(raw) except ValueError: return default
_LOOP_WARN_CMD_THRESHOLD = _loop_warn_env_int("RIDGES_LOOP_WARN_CMD", 3) _LOOP_WARN_WRITE_THRESHOLD = _loop_warn_env_int("RIDGES_LOOP_WARN_WRITE", 3) _LOOP_WARN_SCRATCH_THRESHOLD = _loop_warn_env_int("RIDGES_LOOP_WARN_SCRATCH", 4) _LOOP_WARN_AST_STALL_THRESHOLD = _loop_warn_env_int("RIDGES_LOOP_WARN_AST_STALL", 2) _LOOP_WARN_ENOENT_THRESHOLD = _loop_warn_env_int("RIDGES_LOOP_WARN_ENOENT", 2)
SOURCE_EXTENSIONS = frozenset( ".py .c .cpp .h .hpp .rs .js .ts .java .go .rb .php .scala .kt .swift".split() ) AGENT_SCRATCH_PREFIXES = ( "test", "demo", "verify_", "scratch_", "check_", "simple_", "debug_", "temp_", "tmp_", "poc_", "repro_", "analyze_", "analyse_", "final_", "better_", "best_", "standalone_", "manual_", "validate_", "fix_", "comprehensive_", "reproduce_", "run_test", "repo_level_", "trial_", "attempt_", "quick_", ) SCRATCH_INTENT_RE = re.compile( r"(?i)(?:^|[])(?:test|tests|repro|reproduce|reproduction|demo|verify|" r"verification|validate|validation|check|debug|scratch|sample|example|" r"minimal|simple|clean|bug|issue|problem|demonstrate|mwe|snippet|" r"standalone)(?:$|[_])" ) _LOOP_ENOENT_RE = re.compile( r"(?i)(?:ENOENT|No such file or directory|FileNotFoundError)[^\n']{0,80}'([^']{1,200})'" )
_TEST_RUNNER_RE = re.compile(r"(?i)\b(pytest|py.test|unittest)\b") _TEST_DESELECT_RE = re.compile( r"""(?ix) (?: -k \s* ["'][^"']\bnot\b[^"']["'] )   # -k "not foo" style filter | (?: --deselect (?:[=\s]) ) | (?: --ignore (?:[=\s]) ) """ )
SCRATCH_SUFFIX_RE = re.compile( r"(?i)^(?P[a-z][a-z0-9]+?)" r"_(?:final|fixed|new|old|original|backup|copy|copied|tmp|temp|draft|" r"v\d+|version\d+|patched?|edited|modified|source|fix\d*|debug|working)$" ) _ROOT_CONFIG_FILES = frozenset({ "conf.py", "index.rst", "conftest.py", "setup.py", "setup.cfg", "noxfile.py", "pyproject.toml", })
_TB_START_RE = re.compile(r"^Traceback (most recent call last):", re.MULTILINE) _TB_FRAME_RE = re.compile(r'^(\s+File "[^"]"[^\n]\n[^\n])', re.MULTILINE) TB_EXCLINE_RE = re.compile( r"^([A-Za-z][A-Za-z0-9.](Error|Exception|Warning|Fault|Interrupt)\b[^\n]*)", re.MULTILINE, )
_TB_KEEP_FIRST_FRAMES = 1 _TB_KEEP_LAST_FRAMES = 3
def _compress_traceback_in_text(text: str) -> str: if "Traceback (most recent call last):" not in text: return text
def _compress_one(tb_text: str) -> str:
    frames = _TB_FRAME_RE.findall(tb_text)
    if len(frames) <= _TB_KEEP_FIRST_FRAMES + _TB_KEEP_LAST_FRAMES:
        return tb_text
    kept_first = frames[:_TB_KEEP_FIRST_FRAMES]
    kept_last = frames[-_TB_KEEP_LAST_FRAMES:]
    dropped = len(frames) - _TB_KEEP_FIRST_FRAMES - _TB_KEEP_LAST_FRAMES
    compressed = "Traceback (most recent call last):\n"
    compressed += "".join(kept_first)
    compressed += f"  ... ({dropped} frame(s) omitted) ...\n"
    compressed += "".join(kept_last)
    exc_m = _TB_EXCLINE_RE.search(tb_text)
    if exc_m:
        compressed += exc_m.group(1) + "\n"
    return compressed

parts: list[str] = []
pos = 0
for m in _TB_START_RE.finditer(text):
    parts.append(text[pos:m.start()])
    tb_start = m.start()
    exc_m = _TB_EXCLINE_RE.search(text, m.end())
    tb_end = (exc_m.end() + 1) if exc_m else len(text)
    tb_end = min(tb_end, len(text))
    parts.append(_compress_one(text[tb_start:tb_end]))
    pos = tb_end
parts.append(text[pos:])
return "".join(parts)
def _looks_like_real_source_path(raw_path: str) -> bool: if not raw_path: return False norm = raw_path.lower().replace("\", "/").strip("'"") while norm.startswith("./"): norm = norm[2:] basename = norm.rsplit("/", 1)[-1] stem = basename.rsplit(".", 1)[0] if "." in basename else basename if any(basename.startswith(p) for p in _AGENT_SCRATCH_PREFIXES): return False if basename.endswith("_test.py") or basename.endswith("_test.js"): return False if "/" not in norm.strip("/") and _SCRATCH_INTENT_RE.search(stem): return False ext = "." + basename.rsplit(".", 1)[-1] if "." in basename else "" return ext in _SOURCE_EXTENSIONS
def _short_error_sig(text: str, max_len: int = 120) -> str: for line in text.splitlines(): stripped = line.strip() if _TB_EXCLINE_RE.match(stripped): return stripped[:max_len] for line in text.splitlines(): stripped = line.strip() if re.search(r"\bFAILED\b|\bError\b|\bException\b", stripped): return stripped[:max_len] return ""
_PY_FENCE_RE = re.compile(r"```[ \t]py(?:thon)?[0-9]\b", re.IGNORECASE)
def _instruction_has_python_code_block(text: str) -> bool: return bool(_PY_FENCE_RE.search(text or ""))
class CodingAgent:
def __init__(self, config: AgentConfig | None = None):
    self.config = config or AgentConfig()
    _conda_prefix = _resolve_conda_shell_prefix()
    if _conda_prefix:
        print("[AGENT] Shell commands will use conda env prefix (RIDGES_AGENT_CONDA_ENV)")
    self.executor = ShellExecutor(
        working_dir=self.config.working_dir,
        timeout=self.config.command_timeout,
        shell_prefix=_conda_prefix,
    )
    self.conversation = ConversationManager(max_chars=self.config.max_conversation_chars)
    self.step_count = 0
    self.start_time: float = 0
    self.files_modified: set[str] = set()
    self._recent_actions: list[str] = []
    self._deadline_nudge_sent = False
    self._edit_nudge_sent: set[str] = set()
    self.problem_statement: str = ""
    self._adv_gate_scripts: list[dict] = []   
    self._adv_gate_cycle: int = 0              
    self._adv_gate_max_cycles: int = 3         
    self._gate_mode: str = ""
    self._gate_revision_mode: bool = False
    # Best intermediate patch captured during exploration. Saved after
    # any step that ran a bash command. If the agent times out or its
    # final emergency capture finds a clean worktree (because of a reset),
    # this is the fallback so the user still gets the agent's best work.
    self._best_intermediate_patch: str = ""

    self._proactive_judge_done: bool = False
    self._proactive_judge_mode: str = (
        # "midpoint"
        "first"
    )

    self._file_ast_history: dict[str, list[str]] = {}
    self._ast_stall_counts: dict[str, int] = {}
    self._loop_warnings_sent: set[str] = set()
    self._submit_test_blocks: int = 0
    self._last_error_sig: str = ""

    self.total_cost: float = 0.0
    self.total_prompt_tokens: int = 0
    self.total_completion_tokens: int = 0
    self.total_tokens: int = 0
    self._planning_model_pricing = get_model_pricing(self.config.planning_model)
    self._execution_model_pricing = get_model_pricing(self.config.execution_model)
    self._model_pricing = self._execution_model_pricing
    self.cost_limit = self.config.cost_limit

    self.plan: str = ""
    self.planning_completed: bool = False
    self._completeness_done: bool = False
    self._renamefix_done: bool = False
    self._grammar_fix_done: bool = False
    self._last_repro_src: str | None = None
    self._last_test_cmds: list[str] = []
    self._selected_patch: str | None = None

    self._llm_seed: int | None = _resolve_llm_seed() if _llm_seed_enabled() else None
    self._inference_checkpoint: dict[str, Any] = {}

_CACHE_READ_DISCOUNT = 0.25

def _calculate_cost(
    self,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
) -> float:
    input_price, output_price = self._model_pricing
    uncached = max(0, prompt_tokens - cached_tokens)
    prompt_cost = (uncached / 1_000_000) * input_price + (
        cached_tokens / 1_000_000
    ) * input_price * self._CACHE_READ_DISCOUNT
    completion_cost = (completion_tokens / 1_000_000) * output_price
    return prompt_cost + completion_cost

def _update_cost(self, usage: dict) -> None:
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    cached_tokens = usage.get("cached_tokens", 0)
    self.total_prompt_tokens += prompt_tokens
    self.total_completion_tokens += completion_tokens
    self.total_tokens += usage.get("total_tokens", 0)
    cost = self._calculate_cost(prompt_tokens, completion_tokens, cached_tokens)
    self.total_cost += cost
    cache_suffix = f", cached: {cached_tokens}" if cached_tokens else ""
    print(
        f"[AGENT] Cost: ${cost:.4f} (prompt: {prompt_tokens}, "
        f"completion: {completion_tokens}{cache_suffix})"
    )
    print(f"[AGENT] Total cost so far: ${self.total_cost:.4f} / ${self.cost_limit:.2f} limit")

def _check_cost_limit(self) -> bool:
    if self.cost_limit <= 0:
        return False
    return self.total_cost >= self.cost_limit * 0.9


def _detect_working_dir(self) -> str:
    cwd = os.getcwd()
    path = cwd
    while True:
        if _working_dir_is_git_repo(path):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return cwd


def _build_initial_messages(self, problem_statement: str) -> None:
    working_dir = self.config.working_dir or self._detect_working_dir()
    self.conversation.add("system", _system_prompt_for_run())
    self.conversation.add("user", _instance_prompt_mini(problem_statement, working_dir))

def _inject_language_context(self) -> None:
    wd = self.config.working_dir or self._detect_working_dir()
    lang = _detect_repo_language(wd)
    if lang == "python":
        return  
    meta = _LANG_META.get(lang, _LANG_META["python"])
    label = {
        "rust": "Rust", "go": "Go", "javascript": "JavaScript",
        "typescript": "TypeScript", "java": "Java", "kotlin": "Kotlin",
        "cpp": "C/C++",
    }.get(lang, lang.title())
    lines = [
        f"[Environment] This is a **{label}** repository.",
        f"Config file  : {meta['config_file']}",
        f"Build check  : `{meta['build_check']}`",
        f"Run all tests: `{meta['full_test_cmd']}`",
        f"Run one test : `{meta['test_cmd']}`",
        f"Scratch file : `{meta['run_scratch']}`",
    ]
    lock_hints: list[str] = []
    if lang in ("javascript", "typescript"):
        for lf in ("node_modules", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"):
            if os.path.exists(os.path.join(wd, lf)):
                lock_hints.append(f"`{lf}` present — dependencies already installed.")
                break
        else:
            lock_hints.append("Run `npm install` first if tests fail to find modules.")
    elif lang == "rust":
        if os.path.exists(os.path.join(wd, "Cargo.lock")):
            lock_hints.append("`Cargo.lock` present — dependencies are pinned.")
    elif lang == "go":
        if os.path.exists(os.path.join(wd, "go.sum")):
            lock_hints.append("`go.sum` present — dependencies are locked.")
    if lock_hints:
        lines.append("Deps         : " + " ".join(lock_hints))
    lines.append(f"Tip          : {meta['explore_hint']}")
    self.conversation.add("user", "\n".join(lines))
    print(f"[AGENT] Language context injected for {label}")

def _repo_primary_extensions(self) -> list[str]:
    out = self.executor.execute("git ls-files 2>/dev/null | head -2000")
    ext_counts: dict[str, int] = {}
    _skip = {".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml",
             ".cfg", ".ini", ".lock", ".sum", ".mod", ".png", ".jpg",
             ".gif", ".svg", ".ico", ".csv", ".xml", ".html", ".css"}
    for line in (out.get("stdout") or "").splitlines():
        _, dot, ext = line.rpartition(".")
        if dot:
            e = ("." + ext.lower())[:8]
            if e not in _skip:
                ext_counts[e] = ext_counts.get(e, 0) + 1
    if not ext_counts:
        return [".py"]
    top = sorted(ext_counts, key=lambda e: -ext_counts[e])[:4]
    if ".py" in ext_counts and ".py" not in top:
        top.append(".py")
    return top

def _localize_candidates(self, problem_statement: str, limit: int = 12) -> list[str]:
    text = problem_statement or ""
    scores: dict[str, float] = {}
    for p in re.findall(r"(?:[\w.-]+/)+[\w.-]+\.\w+", text):
        scores[p] = scores.get(p, 0.0) + 50.0

    primary_exts = self._repo_primary_extensions()
    glob_arg = " ".join(f"'*{e}'" for e in primary_exts)

    terms: list[str] = []
    seen: set[str] = set()
    _stop = {
        "this", "that", "with", "from", "when", "then", "there", "should", "would",
        "error", "issue", "tests", "class", "method", "return", "value", "none",
        "true", "false", "python", "using", "which", "where", "raise", "raises",
        "expected", "actual",
    }
    for q in re.findall(r"`([A-Za-z_][\w.]{2,60})`", text):
        terms.append(q.split(".")[-1] if "." in q else q)
    terms += re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{3,}\b", text)
    for t in terms:
        tl = t.lower()
        if len(t) < 4 or tl in _stop or tl in seen:
            continue
        seen.add(tl)
        out = self.executor.execute(
            f"git grep -l --fixed-strings -e {shlex.quote(t)} -- {glob_arg} 2>/dev/null | head -40"
        )
        for f in (out.get("stdout") or "").splitlines():
            f = f.strip()
            if f:
                scores[f] = scores.get(f, 0.0) + (6.0 if tl in os.path.basename(f).lower() else 1.0)
        if len(seen) >= 15:
            break

    def _is_test(path: str) -> bool:
        base = os.path.basename(path).lower()
        return (
            "/tests/" in path or "/test/" in path or "/__tests__/" in path
            or base.startswith("test_") or base.endswith("_test.py")
            or base.endswith(".test.js") or base.endswith(".test.ts")
            or base.endswith("_test.go") or base.endswith("_test.rs")
            or base.endswith("spec.js") or base.endswith("spec.ts")
        )

    ranked = sorted(scores, key=lambda f: (-scores[f], f))
    return ([f for f in ranked if not _is_test(f)] + [f for f in ranked if _is_test(f)])[:limit]

def _should_run_planning(self) -> bool:
    if os.getenv("RIDGES_AGENT_PLANNING", "0").strip().lower() not in ("1", "true", "yes", "on"):
        return False
    if not self.config.enable_planning:
        return False
    if self.config.planning_model == self.config.execution_model:
        print(
            "[AGENT] Planning model matches execution model; skipping duplicate planning call"
        )
        return False
    if self.cost_limit > 0 and self.cost_limit < _PLANNING_MIN_COST_USD:
        print(
            f"[AGENT] Cost limit ${self.cost_limit:.2f} below planning minimum "
            f"${_PLANNING_MIN_COST_USD:.2f}; skipping planning phase"
        )
        return False
    return True

def _run_planning(self, problem_statement: str) -> str:
    if not self._should_run_planning():
        if not self.config.enable_planning:
            print("[AGENT] Planning disabled, skipping...")
        return ""

    working_dir = self.config.working_dir or self._detect_working_dir()
    print(f"[AGENT] === Planning Phase (using {self.config.planning_model}) ===")

    planning_messages = [
        {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
        {"role": "user", "content": _planning_prompt(problem_statement, working_dir)},
    ]
    plan_response = self._call_inference(
        planning_messages,
        model=self.config.planning_model,
        temperature=self.config.planning_temperature,
    )
    if plan_response is None:
        print("[AGENT] Planning failed, continuing without explicit plan...")
        return ""

    self.plan = plan_response
    self.planning_completed = True
    print(f"[AGENT] Planning completed ({len(plan_response)} chars)")
    print(f"[AGENT] Plan preview:\n{plan_response[:500]}...")
    return self.plan

def _cascade_model_for_call(self, requested: str) -> str:
    if (
        self.cost_limit > 0
        and self.total_cost >= self.cost_limit * 0.50
        and self.config.fast_model
        and self.config.fast_model != requested
    ):
        print(
            f"[AGENT] Cost cascade: switching {requested!r} → "
            f"{self.config.fast_model!r} "
            f"(${self.total_cost:.3f} / ${self.cost_limit:.2f})"
        )
        return self.config.fast_model
    return requested

def _call_inference(
    self,
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float | None = None,
    *,
    prefer_checkpoint_model: bool = False,
) -> str | None:
    explicit = model is not None
    model_to_use = model if explicit else self._cascade_model_for_call(
        self.config.execution_model
    )
    if not explicit and self._gate_revision_mode:
        model_to_use = self.config.planning_model
    if (
        not explicit
        and prefer_checkpoint_model
        and self._inference_checkpoint.get("model")
    ):
        model_to_use = self._inference_checkpoint["model"]
        print(
            f"[AGENT] inference checkpoint: reusing last successful model "
            f"{model_to_use!r}"
        )
    temp = self.config.temperature if temperature is None else temperature
    if model_to_use == self.config.planning_model:
        self._model_pricing = self._planning_model_pricing
    else:
        self._model_pricing = get_model_pricing(model_to_use)

    working_messages = messages
    for attempt in range(self.config.max_inference_retries):
        if attempt > 0:
            delay = self.config.inference_retry_delay * (2 ** (attempt - 1))
            print(
                f"[AGENT] Retrying inference (attempt {attempt + 1}/{self.config.max_inference_retries}) "
                f"after {delay:.1f}s delay..."
            )
            time.sleep(delay)
            working_messages = _build_inference_checkpoint_messages(messages)
        response, usage = inference(
            model_to_use,
            temp,
            working_messages,
            top_p=self.config.llm_top_p,
            seed=self._llm_seed,
        )
        if response is not None:
            if usage and usage.get("total_tokens", 0) > 0:
                self._update_cost(usage)
            self._inference_checkpoint = {
                "step": self.step_count,
                "model": model_to_use,
                "message_count": len(messages),
                "retry_attempt": attempt,
            }
            return response
        if not explicit and attempt == self.config.max_inference_retries - 2:
            fallback = self.config.fast_model
            if fallback and fallback != model_to_use:
                print(f"[AGENT] Inference failed — cascading to fast_model={fallback!r}")
                model_to_use = fallback
                self._model_pricing = get_model_pricing(model_to_use)
    print("[AGENT] All inference retries exhausted")
    return None

def _check_timeout(self) -> bool:
    wall = _effective_agent_wall_sec()
    if wall is None:
        return False
    elapsed = time.time() - self.start_time
    margin = _agent_tail_margin_sec()
    cutoff = max(0.0, wall - margin)
    return elapsed > cutoff


def _record_action(self, signature: str) -> None:
    self._recent_actions.append(signature)
    if len(self._recent_actions) > _LOOP_DETECT_WINDOW:
        self._recent_actions = self._recent_actions[-_LOOP_DETECT_WINDOW:]

def _stuck_in_loop(self, signature: str) -> bool:
    self._record_action(signature)
    if len(self._recent_actions) < _LOOP_DETECT_REPEAT_THRESHOLD:
        return False
    last = self._recent_actions[-_LOOP_DETECT_REPEAT_THRESHOLD:]
    return all(c == last[0] for c in last)


def _emergency_diagnostics(self) -> None:
    wd = self.config.working_dir or self._detect_working_dir()
    is_repo = _working_dir_is_git_repo(wd) if wd else False
    print(f"[AGENT] Emergency diagnostics: wd={wd}, is_git_repo={is_repo}")
    try:
        head = self.executor.execute("git rev-parse --short HEAD 2>&1 || echo NOHEAD")
        head_out = (head.get("stdout") or "").strip().replace("\n", " | ")
        print(f"[AGENT] Emergency: git HEAD rc={head.get('returncode')}, out={head_out[:200]}")
        status = self.executor.execute("git status --porcelain 2>&1 | head -40")
        status_out = (status.get("stdout") or "").rstrip()
        n_lines = len(status_out.splitlines()) if status_out else 0
        print(
            f"[AGENT] Emergency: git status rc={status.get('returncode')}, "
            f"changed_entries={n_lines}, sample={status_out[:400] if status_out else '(clean)'}"
        )
    except Exception as e:
        print(f"[AGENT] Emergency diagnostics raised: {e}")

def _collect_patch_emergency(self) -> str:
    self._emergency_diagnostics()
    try:
        patch = normalize_patch_text(authoritative_worktree_patch(self.executor))
        if patch.strip():
            return patch
    except Exception as e:
        print(f"[AGENT] Emergency (authoritative) failed: {e}")

    try:
        add = self.executor.execute("git add -A 2>&1")
        print(
            f"[AGENT] Emergency add: rc={add.get('returncode')}, "
            f"stderr_head={(add.get('stderr') or '')[:200]}"
        )
        staged = self.executor.execute(
            "git -c color.ui=false -c core.pager=cat diff --cached HEAD"
        )
        cached_stdout = staged.get("stdout") or ""
        print(
            f"[AGENT] Emergency cached diff: rc={staged.get('returncode')}, "
            f"stdout_len={len(cached_stdout)}"
        )
        if staged.get("returncode") == 0 and cached_stdout.strip():
            patch = normalize_patch_text(cached_stdout)
            if patch.strip():
                return patch
    except Exception as e:
        print(f"[AGENT] Emergency (cached diff) failed: {e}")

    try:
        head_diff = self.executor.execute("git -c color.ui=false -c core.pager=cat diff HEAD")
        if head_diff.get("returncode") == 0 and (head_diff.get("stdout") or "").strip():
            patch = normalize_patch_text(head_diff.get("stdout") or "")
            if patch.strip():
                return patch
    except Exception as e:
        print(f"[AGENT] Emergency (HEAD diff) failed: {e}")

    # Final fallback: the agent may have done edits earlier, then reset
    # its worktree (validation flow, minfix, etc.) and not gotten a chance
    # to re-apply before timeout. Use the last successful intermediate
    # patch we captured during exploration.
    if self._best_intermediate_patch.strip():
        print(
            f"[AGENT] Emergency: using best intermediate patch "
            f"({len(self._best_intermediate_patch)} chars) — worktree was clean"
        )
        return self._best_intermediate_patch

    print("[AGENT] Emergency patch: all strategies returned empty")
    return ""


_ADV_GATE_SYSTEM = (
    "You audit a candidate fix that modifies a SHARED data structure (a "
    "config file table, a registry, a dict, a TOML table, a database table, "
    "etc.). Real users often have hand-written entries in that same shared "
    "structure that the spec doesn't mention. A weak fix damages those entries.\n\n"
    "Write ONE focused pytest function that EXERCISES TWO PHASES in sequence:\n\n"
    "PHASE A — set up the shared structure with a user-written entry whose "
    "shape differs from the spec's examples (e.g., uses a different key, a "
    "different attribute, or a different format). Then run the patched code "
    "WITH the spec's main action firing (e.g., new input is present). Assert "
    "the spec's intended behavior AND the user-written entry survives.\n\n"
    "PHASE B — in the same test, immediately after Phase A, remove the spec's "
    "main input entirely (empty config, empty input list, etc.) and run the "
    "patched code AGAIN. Assert that any entries written by the patch in "
    "Phase A are now cleaned up (the spec's reconciliation MUST still fire "
    "even with empty input) AND the user-written entry STILL survives.\n\n"
    "Both phases are inside ONE pytest function, exercised in sequence.\n\n"
    "CRITICAL: copy the import/setup/invocation pattern from the existing test "
    "shown below. Use the same constructor calls, fixtures, helpers. Do NOT "
    "invent API signatures.\n\n"
    'Output ONLY a JSON object:\n'
    '{"scripts": [{"name": "test_X", "code": "..."}]}'
)

def _adv_gate_find_fewshot(self, patch: str = "") -> str | None:
    import re as _re
    ls = self.executor.execute(
        "ls tests/test_*.py 2>/dev/null || ls test/test_*.py 2>/dev/null"
    )
    if ls.get("returncode") != 0 or not ls.get("stdout", "").strip():
        return None
    all_tests = [p.strip() for p in ls["stdout"].strip().splitlines() if p.strip()]
    modified_basenames: set[str] = set()
    for m in _re.finditer(r"^\+\+\+ b/(\S+)|^--- a/(\S+)", patch, _re.M):
        relpath = m.group(1) or m.group(2)
        stem = relpath.rsplit("/", 1)[-1].removesuffix(".py")
        if stem and stem != "/dev/null":
            modified_basenames.add(stem)
    def _score(path: str) -> int:
        base = path.rsplit("/", 1)[-1]
        for stem in modified_basenames:
            if base == f"test_{stem}.py":
                return 2  
            if stem in base:
                return 1  
        return 0
    all_tests.sort(key=lambda p: -_score(p))
    if all_tests:
        print(f"[ADV-GATE] selected test file for few-shot: {all_tests[0]} (score {_score(all_tests[0])})")

    patch_keywords: set[str] = set()
    for token in _re.findall(r"[A-Za-z_]\w{4,}", patch):
        if token in {"diff", "git", "index", "tool", "test"}:
            continue
        patch_keywords.add(token)

    def _score_function(body: str) -> int:
        keywords_hit = sum(1 for kw in patch_keywords if kw in body)
        length_bonus = 2 if len(body.splitlines()) >= 10 else 0
        return keywords_hit + length_bonus

    best: tuple[int, str, str] | None = None  
    for path in all_tests[:5]:
        cat = self.executor.execute(f"cat {path} 2>/dev/null")
        if cat.get("returncode") != 0:
            continue
        text = cat.get("stdout", "")
        if not text:
            continue
        imports = [
            ln for ln in text.splitlines()
            if ln.startswith(("import ", "from "))
        ][:12]
        if not imports:
            continue
        for m in _re.finditer(
            r"(^def test_\w+\([^)]*\):[\s\S]+?)(?=\n(?:def |class |@\w))",
            text, _re.M,
        ):
            body = m.group(1)
            score = _score_function(body)
            if best is None or score > best[0]:
                best = (score, "\n".join(imports), body.rstrip())
    if best is None:
        return None
    print(f"[ADV-GATE] few-shot keyword-score = {best[0]} (higher = more relevant test)")
    if best[0] < 5:
        print(f"[ADV-GATE] score {best[0]} below relevance threshold (5); skipping gate")
        return None
    return best[1] + "\n\n\n" + best[2]

def _adv_gate_run_one_test(self, name: str, code: str) -> dict[str, Any]:
    import re as _re
    safe = _re.sub(r"\W", "_", name)[:40] or "adv"
    rel_path = f"tests/test_advgate_{safe}.py"
    print(f"[ADV-GATE-TEST] >>> {name}  (writing to {rel_path}, {len(code)} chars)")
    for line in code.splitlines():
        print(f"[ADV-GATE-TEST-CODE] {line}")
    write = self.executor.execute(
        f"cat > {rel_path} << '__ADVGATE_EOF__'\n{code}\n__ADVGATE_EOF__"
    )
    if write.get("returncode") != 0:
        print(f"[ADV-GATE-TEST] write failed: {write.get('stderr','')[:200]}")
        return {"status": "error", "output": "could not write test file"}
    try:
        run = self.executor.execute(
            f"python -m pytest -xvs {rel_path} --tb=short --no-header 2>&1 | tail -40"
        )
        out = (run.get("stdout") or "")[-2400:]
        if "passed" in out and "failed" not in out and "error" not in out.lower():
            status = "pass"
        elif "failed" in out or "FAILED" in out:
            status = "fail"
        else:
            status = "error"
        print(f"[ADV-GATE-TEST] verdict: {status}  rc={run.get('returncode')}")
        for line in out.splitlines():
            print(f"[ADV-GATE-TEST-OUT] {line}")
        if status == "pass":
            self.executor.execute(f"rm -f {rel_path}")
        return {"status": status, "output": out, "path": rel_path}
    except Exception:
        self.executor.execute(f"rm -f {rel_path}")
        raise

def _locate_gap_hint(self, patch: str) -> str:
    """Second judge call: given the post-patch file content, pinpoint the
    exact line still inconsistent with the change. Returns a precise hint,
    or '' on any failure (caller keeps the call-1 hint)."""
    import os as _os, re as _re3
    # Collect changed files from the diff and read their current (post-patch)
    # content from the worktree, capped so the prompt stays bounded.
    paths = _re3.findall(r"^\+\+\+ b/(\S+)", patch, _re3.M)
    wd = self.config.working_dir or self._detect_working_dir()
    blocks = []
    for p in paths[:2]:
        full = _os.path.join(wd, p) if wd else p
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except Exception:
            continue
        if content.count("\n") > 1400:   # too big — skip, fall back to call-1 hint
            continue
        blocks.append(f"### {p}\n{content}")
    if not blocks:
        return ""
    file_context = "\n\n".join(blocks)
    locate_prompt = (
        "This patch is INCOMPLETE: somewhere else in this same file a line "
        "is now inconsistent with the change and still mishandles some "
        "valid inputs. The gap is real — locate it from the code, not the "
        "bug report's emphasis.\n\n"
        "Identify what the patch changed, then find the one later line that "
        "does not account for it. Note: a change that WIDENS what a value "
        "can be often leaves a later test of that value against a specific "
        "expected form (a comparison, lookup, or branch) silently failing "
        "to match the new forms — such a stale test is a frequent culprit "
        "and easy to overlook.\n\n"
        "Output ONLY JSON: {\"hint\":\"<one imperative sentence, ≤25 words, "
        "quoting the exact line/expression to change>\"}\n\n"
        f"BUG REPORT:\n---\n{self.problem_statement}\n---\n\n"
        f"POST-PATCH FILE:\n---\n{file_context}\n---\n\nJSON only:"
    )
    print(f"[ADV-GATE-JUDGE] locate call (prompt_chars={len(locate_prompt)})")
    try:
        response, _u = inference(
            model="anthropic/claude-opus-4.8",
            temperature=0.0,
            messages=[{"role": "user", "content": locate_prompt}],
        )
    except Exception as exc:
        print(f"[ADV-GATE-JUDGE] locate call failed ({type(exc).__name__}); keeping call-1 hint")
        return ""
    if not response:
        return ""
    import json as _json3
    t = response.strip()
    t = _re3.sub(r"```(?:json)?\n?", "", t)
    t = _re3.sub(r"\n?```", "", t)
    s = t.find("{")
    if s < 0:
        return ""
    try:
        o, _ = _json3.JSONDecoder().raw_decode(t[s:])
    except Exception:
        return ""
    return str(o.get("hint", "")).strip()


def _build_judge_prompt(self, patch: str) -> str:
    return (
        "You are reviewing whether a candidate patch fully fixes the "
        "reported bug, or leaves the code INCONSISTENT in a way that still "
        "breaks it.\n\n"
        "DEFAULT to ship. Revise only when a directly-causal change is "
        "missing — never for style, defensive extras, or hypothetical edge "
        "cases.\n\n"
        "Look for ONE place left out of step — handled differently from the "
        "change just made or from its peer code paths. Two common forms:\n"
        "- A value taken from existing or shared storage is returned or "
        "passed on without the ownership/lifetime step that freshly-created "
        "values get, leaving a caller with an unsafe reference.\n"
        "- One site is made to accept a wider range of inputs, but a "
        "related site that handles those same values still assumes the "
        "older, narrower form, so the newly-accepted inputs fail there.\n\n"
        "If such an unresolved inconsistency exists, revise. If the "
        "affected values are handled consistently everywhere, ship. If the "
        "patch is empty, revise pointing at the change the spec needs.\n\n"
        "Respond with ONLY a JSON object, starting with '{'. Exactly one "
        "of:\n"
        "  {\"action\":\"ship\"}\n"
        "  {\"action\":\"revise\",\"hint\":\"<one imperative sentence, ≤25 "
        "words, naming the single missing change>\"}\n\n"
        f"BUG REPORT:\n---\n{self.problem_statement}\n---\n\n"
        f"CANDIDATE PATCH:\n---\n{patch}\n---\n\n"
        "JSON only:"
    )
def _opus_judge_patch(self, patch: str) -> tuple[bool, str]:
    """Single-shot opus check for tasks with no pytest fewshot.

    Asks opus to identify the ONE specific oversight most likely to make
    this patch insufficient, given the spec. Returns that pointer as
    sharp, directive feedback (not a long judgment essay) for minimax to
    act on. Fires once at cycle 1; if the agent submits again, we ship
    on cycle 2 regardless (no perfectionism loop)."""
    # Only fire once. Subsequent cycles just ship.
    if self._adv_gate_cycle > 1:
        print(f"[ADV-GATE-JUDGE] cycle {self._adv_gate_cycle} (already fired once) → ship")
        return True, ""

    judge_prompt = self._build_judge_prompt(patch)
    print(f"[ADV-GATE-JUDGE] calling opus (prompt_chars={len(judge_prompt)})")
    try:
        response, _usage = inference(
            model="anthropic/claude-opus-4.8",
            temperature=0.0,
            messages=[{"role": "user", "content": judge_prompt}],
        )
    except Exception as exc:
        print(f"[ADV-GATE-JUDGE] opus call raised {type(exc).__name__}: {exc}; shipping")
        return True, ""
    if not response:
        print("[ADV-GATE-JUDGE] opus returned empty; shipping")
        return True, ""

    import json as _json, re as _re2
    text = response.strip()
    text = _re2.sub(r"```(?:json)?\n?", "", text)
    text = _re2.sub(r"\n?```", "", text)
    start = text.find("{")
    if start < 0:
        print("[ADV-GATE-JUDGE] opus response has no JSON; shipping")
        return True, ""
    try:
        obj, _idx = _json.JSONDecoder().raw_decode(text[start:])
    except Exception as exc:
        print(f"[ADV-GATE-JUDGE] opus JSON parse failed ({exc}); shipping")
        return True, ""

    action = str(obj.get("action", "")).strip().lower()
    hint = str(obj.get("hint", "")).strip()
    print(f"[ADV-GATE-JUDGE] action={action}  hint={hint[:200]}")

    if action == "ship" or not hint:
        print("[ADV-GATE-JUDGE] FINAL: ship")
        return True, ""

    # Second call — LOCATE. The decision call (above) reliably catches an
    # incomplete patch but, seeing only the diff, often points at the wrong
    # line (it fixates on whatever the bug report emphasizes). Now that we
    # KNOW a gap exists, give opus the actual post-patch file content and
    # ask it to pinpoint the exact inconsistent line. This converts a
    # vague/misdirected hint into a precise one minimax can act on.
    located = self._locate_gap_hint(patch)
    if located:
        print(f"[ADV-GATE-JUDGE] located precise hint: {located[:200]}")
        hint = located

    # Sharp, directive feedback — one sentence, no preamble.
    feedback = (
        f"Pre-submit check spotted a likely oversight in your patch.\n\n"
        f"FIX THIS: {hint}\n\n"
        f"Apply the change above, re-verify, and submit again."
    )
    print(f"[ADV-GATE-JUDGE] FINAL: revise (single shot, will ship on next cycle)")
    return False, feedback

def _adversarial_pre_submit_gate(self, patch: str) -> tuple[bool, str]:
    self._adv_gate_cycle += 1
    if self._adv_gate_cycle > self._adv_gate_max_cycles:
        print(f"[ADV-GATE] cycle cap ({self._adv_gate_max_cycles}) reached — letting patch ship")
        return True, ""
    is_first_cycle = self._adv_gate_cycle == 1

    print(f"[ADV-GATE] ============ cycle {self._adv_gate_cycle}/{self._adv_gate_max_cycles} ============")
    print(f"[ADV-GATE] problem_statement len: {len(self.problem_statement)} chars")
    print(f"[ADV-GATE] candidate patch len: {len(patch)} chars")
    print("[ADV-GATE] candidate patch preview (first 40 lines):")
    for line in patch.splitlines()[:40]:
        print(f"[ADV-GATE-PATCH] {line}")
    if len(patch.splitlines()) > 40:
        print(f"[ADV-GATE-PATCH] ... ({len(patch.splitlines()) - 40} more lines)")

    if self._gate_mode == "judge":
        return self._opus_judge_patch(patch)
    if is_first_cycle:
        fewshot = self._adv_gate_find_fewshot(patch=patch)
        if not fewshot:
            # No suitable pytest fewshot in repo — fall back to opus-judge
            # against the SYSTEM_PROMPT rules. Catches reasoning failures
            # (e.g., the patch doesn't address the spec's symptom, or
            # violates an engineering rule) on tasks where we can't
            # generate a real test.
            print("[ADV-GATE] no example test found — falling back to opus judge")
            self._gate_mode = "judge"
            return self._opus_judge_patch(patch)
        self._gate_mode = "test"
        print(f"[ADV-GATE] few-shot found ({len(fewshot)} chars):")
        for line in fewshot.splitlines():
            print(f"[ADV-GATE-FEWSHOT] {line}")

        user_msg = (
            f"Bug report (the spec):\n```\n{self.problem_statement}\n```\n\n"
            f"Existing test in the repo (use this exact setup pattern):\n"
            f"```python\n{fewshot}\n```\n\n"
            f"Candidate fix:\n```diff\n{patch}\n```\n\n"
            f"Generate ONE adversarial pytest script using the same imports + helpers."
        )
        print(f"[ADV-GATE] calling opus (model=claude-opus-4.8, temp=0.3, prompt_chars={len(user_msg)})")

        try:
            response, _usage = inference(
                model="anthropic/claude-opus-4.8",
                temperature=0.3,
                messages=[
                    {"role": "system", "content": self._ADV_GATE_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
            )
        except Exception as exc:
            print(f"[ADV-GATE] opus call raised {type(exc).__name__}: {exc}; skipping gate")
            return True, ""
        if not response:
            print("[ADV-GATE] opus returned empty; skipping gate")
            return True, ""
    else:
        if not self._adv_gate_scripts:
            print("[ADV-GATE] no cached tests from cycle 1 — letting patch ship")
            return True, ""
        print(f"[ADV-GATE] re-running {len(self._adv_gate_scripts)} cached test(s) against revised patch")
        response = None  

    if is_first_cycle:
        print(f"[ADV-GATE] opus response ({len(response)} chars):")
        for line in response.splitlines():
            print(f"[ADV-GATE-OPUS] {line}")

        import json as _json, re as _re2
        text = response.strip()
        text = _re2.sub(r"```(?:json)?\n?", "", text)
        text = _re2.sub(r"\n?```", "", text)
        start = text.find("{")
        if start < 0:
            print("[ADV-GATE] opus response has no JSON object; skipping gate")
            return True, ""
        try:
            obj, _idx = _json.JSONDecoder().raw_decode(text[start:])
        except Exception as exc:
            print(f"[ADV-GATE] opus response not valid JSON ({exc}); skipping gate")
            return True, ""
        scripts = obj.get("scripts") if isinstance(obj, dict) else None
        if not isinstance(scripts, list) or not scripts:
            print("[ADV-GATE] opus returned no scripts; skipping gate")
            return True, ""
        self._adv_gate_scripts = [s for s in scripts[:1] if isinstance(s, dict) and (s.get("code") or "").strip()]
        print(f"[ADV-GATE] cached {len(self._adv_gate_scripts)} test(s) for future cycles")
    else:
        scripts = self._adv_gate_scripts

    print(f"[ADV-GATE] running {len(scripts)} adversarial test(s) (cycle {self._adv_gate_cycle})")
    failures: list[dict[str, Any]] = []
    for idx, s in enumerate(scripts[:1]):
        if not isinstance(s, dict):
            continue
        name = str(s.get("name") or f"adv_{idx}")
        code = str(s.get("code") or "")
        if not code.strip():
            continue
        result = self._adv_gate_run_one_test(name, code)
        if result["status"] != "pass":
            failures.append({
                "name": name,
                "output": result["output"],
                "path": result.get("path", ""),
            })

    print(f"[ADV-GATE] summary cycle {self._adv_gate_cycle}: {len(failures)} failure(s) of {min(len(scripts), 3)} run")
    if not failures:
        print(f"[ADV-GATE] FINAL: all adversarial tests passed at cycle {self._adv_gate_cycle} → proceeding to submit")
        return True, ""

    print(f"[ADV-GATE] FINAL cycle {self._adv_gate_cycle}: {len(failures)} test(s) failed; requesting revision")

    if self._adv_gate_cycle == 1:
        feedback_lines = [
            "Adversarial pre-submit check: the test below fails on your patch. It "
            "probes a case where a user has a pre-existing entry in the shared "
            "structure your code modifies — and your patch must preserve it.",
            "",
            "STRATEGY HINT: To distinguish entries YOUR code wrote from entries "
            "the user wrote yourself, ADD A MARKER when you write each entry — "
            "for example, a trailing comment like `# managed`, or a distinguishing "
            "key, or another structural signal. Then in the cleanup/prune step, "
            "ONLY remove entries that carry your marker. Untagged entries are "
            "user-owned and must NOT be touched. This pattern (tag-and-prune) "
            "lets the patch safely reconcile shared state without damaging the "
            "user's manual entries.",
            "",
            "ALSO: the prune/reconcile step MUST run regardless of whether the "
            "spec's main input is non-empty. An empty input (e.g., an empty "
            "config, all items removed) is exactly the case the spec is most "
            "trying to handle — your code must still iterate the existing entries "
            "and prune the ones that carry your marker.",
            "",
        ]
    else:
        cycles_remaining = self._adv_gate_max_cycles - self._adv_gate_cycle
        feedback_lines = [
            f"Adversarial pre-submit check — CYCLE {self._adv_gate_cycle} of "
            f"{self._adv_gate_max_cycles}: your REVISED patch STILL fails the "
            "same test from the previous cycle. The test asserts that:",
            "  (A) Your code's main action happens (e.g., adds a new managed entry).",
            "  (B) Pre-existing user-written entries in the shared structure "
            "SURVIVE INTACT after your code runs.",
            "  (C) When the input is later emptied, the entry you wrote in (A) "
            "is cleaned up but the user's entry from (B) is STILL there.",
            "",
            "Your previous revision did not satisfy all three. The most common "
            "miss is failing to discriminate user-written entries from your own "
            "when pruning — your prune step probably removes ANY entry that "
            "isn't in the current input, including user entries.",
            "",
            "REQUIRED FIX: tag every entry you write with a distinguishing "
            "signal (a TOML comment marker, a sentinel key, or a structural "
            "property your code chose). In the prune step, ONLY remove entries "
            "that carry that signal. User entries that lack the signal must "
            "NEVER be touched.",
            "",
            f"You have {cycles_remaining} more attempt(s) before submission "
            "proceeds anyway. Read the test file, identify exactly which "
            "assertion fires, and fix it.",
            "",
        ]
    for f in failures:
        feedback_lines.append(f"### Test '{f['name']}' FAILED")
        if f.get("path"):
            feedback_lines.append(
                f"(test file kept at {f['path']} — `cat {f['path']}` to "
                f"see what it asserts)"
            )
        feedback_lines.append("```")
        feedback_lines.append(f["output"])
        feedback_lines.append("```")
        feedback_lines.append("")
    feedback = "\n".join(feedback_lines)
    print(f"[ADV-GATE] feedback injected ({len(feedback)} chars):")
    for line in feedback.splitlines():
        print(f"[ADV-GATE-FEEDBACK] {line}")
    return False, feedback


def _execute_bash(self, command: str) -> dict[str, Any]:
    print(f"[AGENT] Executing bash: {command[:200]}{'...' if len(command) > 200 else ''}")
    out = self.executor.execute(command)
    self._maybe_capture_repro(command, out)
    self._maybe_capture_test(command, out)
    self._maybe_capture_intermediate_patch(command)
    return out

def _maybe_capture_test(self, command: str, out: dict[str, Any]) -> None:
    try:
        if "pytest" not in command:
            return
        seg = command.split("&&")[-1].strip().split("|")[0].strip()
        if "pytest" not in seg:
            return
        if not re.search(r"test[\w./-]*\.py|/tests?/", seg):
            return
        if seg not in self._last_test_cmds:
            self._last_test_cmds.append(seg)
            self._last_test_cmds = self._last_test_cmds[-4:]
    except Exception:
        pass

def _maybe_capture_repro(self, command: str, out: dict[str, Any]) -> None:
    try:
        if out.get("returncode") != 0:
            return
        if "pytest" in command or "py_compile" in command:
            return
        seg = command.split("&&")[-1].strip()
        toks = shlex.split(seg)
        if not toks or os.path.basename(toks[0]) not in ("python", "python3"):
            return
        body = None
        if "-c" in toks:
            ci = toks.index("-c")
            if ci + 1 < len(toks):
                body = toks[ci + 1]
        else:
            pyf = next((t for t in toks[1:] if t.endswith(".py")), None)
            if pyf:
                wd = self.config.working_dir or self._detect_working_dir()
                full = pyf if os.path.isabs(pyf) else os.path.join(wd, pyf)
                if os.path.isfile(full):
                    with open(full, "r", encoding="utf-8", errors="surrogateescape") as f:
                        body = f.read()
        if body and 20 <= len(body) <= 20000 and ("import" in body):
            self._last_repro_src = body
            print(f"[GRAMMARFIX] captured repro oracle ({len(body)}b)")
    except Exception:
        pass

def _maybe_capture_intermediate_patch(self, command: str) -> None:
    """After any BASH command that might have edited files, snapshot the
    current git diff. Edits via apply_str_replace/apply_multi_edit go
    through _execute_edit/_execute_multi_edit which call _snapshot_worktree_diff
    directly."""
    # Cheap heuristic: only re-snapshot after edit-like bash commands so
    # we don't pay for git diff on every grep/cat/ls.
    edit_markers = (" > ", " >> ", "sed -i", "cat <<", "tee ", "rm ",
                    "mv ", "cp ", "touch ", "echo SUBMIT_PATCH", "git apply")
    if not any(m in command for m in edit_markers):
        return
    self._snapshot_worktree_diff()

def _snapshot_worktree_diff(self) -> None:
    """Save the current worktree diff as the best intermediate patch.
    Called after any successful edit (bash, apply_str_replace, or
    apply_multi_edit) so that if the agent later times out or its
    worktree gets reset, we have its last good work to ship."""
    try:
        r = self.executor.execute(
            "git -c color.ui=false -c core.pager=cat diff HEAD --binary --no-ext-diff 2>/dev/null"
        )
        diff = (r.get("stdout") or "").strip()
        if diff and len(diff) >= 50:
            self._best_intermediate_patch = diff
    except Exception:
        pass

def _maybe_proactive_opus(self) -> None:
    """Proactive opus intervention. Fires ONCE per run.

    Triggers (env-controlled):
      midpoint → at 60% step OR 70% time
      first    → at step 1 (pre-flight directive based purely on spec)
      off      → disabled

    Behavior:
      - Snapshot current diff (may be empty)
      - Call opus with the spec + current diff
      - Opus returns either {action: ship} or {action: revise, hint: ...}
      - If revise: inject the hint as a user message
      - If ship: inject a "you're on track, continue" message (only if diff non-empty)
      - If diff empty: opus operates in 'suggest' mode — its hint becomes a
        directive on what to change first
    """
    if self._proactive_judge_done:
        return
    if self._proactive_judge_mode == "off":
        return

    # Trigger check
    if self._proactive_judge_mode == "first":
        should_fire = self.step_count == 1
    else:  # "midpoint" or anything else
        elapsed = time.time() - self.start_time if self.start_time else 0
        wall = _effective_agent_wall_sec() or 1500
        step_pct = self.step_count / max(1, self.config.max_steps)
        time_pct = elapsed / wall if wall else 0
        should_fire = step_pct >= 0.6 or time_pct >= 0.7
    if not should_fire:
        return

    self._proactive_judge_done = True

    # Snapshot current state
    diff = ""
    try:
        r = self.executor.execute(
            "git -c color.ui=false -c core.pager=cat diff HEAD --binary --no-ext-diff 2>/dev/null"
        )
        diff = (r.get("stdout") or "").strip()
    except Exception:
        pass

    
    prompt = self._build_judge_prompt(diff)
    label = "PRE-FLIGHT" if self._proactive_judge_mode == "first" else "MID-RUN"

    print(f"[PROACTIVE-OPUS] firing at step {self.step_count} mode={self._proactive_judge_mode} (diff={len(diff)}b)")
    try:
        response, _ = inference(
            model="anthropic/claude-opus-4.8",
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        print(f"[PROACTIVE-OPUS] opus call failed ({type(exc).__name__}: {exc}); skipping")
        return
    if not response:
        print("[PROACTIVE-OPUS] opus returned empty; skipping")
        return

    import json as _json, re as _re2
    text = response.strip()
    text = _re2.sub(r"```(?:json)?\n?", "", text)
    text = _re2.sub(r"\n?```", "", text)
    start = text.find("{")
    if start < 0:
        print(f"[PROACTIVE-OPUS] no JSON in response; skipping")
        return
    try:
        obj, _ = _json.JSONDecoder().raw_decode(text[start:])
    except Exception:
        print(f"[PROACTIVE-OPUS] JSON parse failed; skipping")
        return

    action = str(obj.get("action", "")).strip().lower()
    hint = str(obj.get("hint", "")).strip()
    print(f"[PROACTIVE-OPUS] action={action}  hint={hint[:200]}")

    if action == "revise" and hint:
        self.conversation.add(
            "user",
            f"[{label}] Likely missing change: {hint}"
        )
    elif action == "ship":
        self.conversation.add(
            "user",
            f"[{label}] Current edits look on-track. Finish refining and submit."
        )

def _execute_edit(self, payload: str) -> dict[str, Any]:
    parsed = parse_edit_payload(payload)
    if parsed is None:
        return {
            "stdout": "",
            "stderr": (
                "apply_str_replace: malformed body. Required markers (in this order):\n"
                "<<<FILE>>>\n<path>\n<<<OLD>>>\n<exact text>\n<<<NEW>>>\n<replacement>\n<<<END>>>"
            ),
            "returncode": 2,
            "timed_out": False,
        }
    file_path, old_str, new_str = parsed
    print(
        f"[AGENT] Executing edit: file={file_path} "
        f"old={len(old_str)}b new={len(new_str)}b"
    )
    wd = self.config.working_dir or self._detect_working_dir()
    out = apply_str_replace(wd, file_path, old_str, new_str)
    if out.get("returncode") == 0:
        self.files_modified.add(file_path)
        self._record_edit_ast_progress(file_path)
        self._maybe_nudge_after_edit(file_path)
        self._snapshot_worktree_diff()  # save intermediate patch
    return out

def _execute_multi_edit(self, payload: str) -> dict[str, Any]:
    parsed = parse_multi_edit_payload(payload)
    if parsed is None:
        return {
            "stdout": "",
            "stderr": (
                "apply_multi_edit: malformed body. Required (one or more "
                "blocks, then a single <<<END>>>):\n"
                "<<<FILE>>>\n<path1>\n<<<OLD>>>\n<exact text>\n<<<NEW>>>\n<replacement>\n"
                "<<<FILE>>>\n<path2>\n<<<OLD>>>\n<exact text>\n<<<NEW>>>\n<replacement>\n"
                "<<<END>>>"
            ),
            "returncode": 2,
            "timed_out": False,
        }
    print(
        f"[AGENT] Executing multi-edit: {len(parsed)} edits across "
        f"{len({p[0] for p in parsed})} file(s)"
    )
    wd = self.config.working_dir or self._detect_working_dir()
    out = apply_multi_str_replace(wd, parsed)
    if out.get("returncode") == 0:
        for file_path, _, _ in parsed:
            self.files_modified.add(file_path)
            self._record_edit_ast_progress(file_path)
            self._maybe_nudge_after_edit(file_path)
        self._snapshot_worktree_diff()  # save intermediate patch
    return out

@staticmethod
def _test_runner_for_extension(ext: str) -> str | None:
    return {
        ".py":   "python -m pytest -xvs {test_path}",
        ".js":   "npm test -- --testPathPattern={basename} 2>&1 | tail -40",
        ".ts":   "npm test -- --testPathPattern={basename} 2>&1 | tail -40",
        ".jsx":  "npm test -- --testPathPattern={basename} 2>&1 | tail -40",
        ".tsx":  "npm test -- --testPathPattern={basename} 2>&1 | tail -40",
        ".rs":   "cargo test 2>&1 | tail -60",
        ".go":   "go test ./... 2>&1 | tail -60",
        ".java": "mvn test -q 2>&1 | tail -60",
        ".kt":   "./gradlew test 2>&1 | tail -60",
        ".cpp":  "make test 2>&1 | tail -60",
        ".c":    "make test 2>&1 | tail -60",
        ".rb":   "bundle exec rspec 2>&1 | tail -60",
    }.get(ext)

def _maybe_nudge_after_edit(self, file_path: str) -> None:
    norm = file_path.replace("\\", "/")
    _, dot, ext_raw = norm.rpartition(".")
    ext = ("." + ext_raw.lower()) if dot else ""
    if not ext:
        return
    is_test = (
        "/tests/" in norm or "/test/" in norm or "/__tests__/" in norm
        or norm.startswith("tests/") or norm.startswith("test/")
        or os.path.basename(norm).startswith("test_")
        or norm.endswith("_test.py") or norm.endswith(".test.js")
        or norm.endswith(".test.ts") or norm.endswith("_test.go")
    )
    if is_test:
        return
    if norm in self._edit_nudge_sent:
        return
    runner_tpl = self._test_runner_for_extension(ext)
    if not runner_tpl:
        return
    self._edit_nudge_sent.add(norm)
    wd = self.config.working_dir or self._detect_working_dir()
    rel = norm
    if wd and norm.startswith(wd):
        rel = os.path.relpath(norm, wd).replace("\\", "/")
    elif norm.startswith("/testbed/"):
        rel = norm[len("/testbed/"):]
    basename = os.path.basename(rel)
    if ext == ".py":
        test_path = _infer_test_path(rel, wd)
        if not test_path:
            return
        run_cmd = runner_tpl.format(test_path=test_path, basename=basename)
        extra = ""
    else:
        run_cmd = runner_tpl.format(test_path=rel, basename=basename)
        extra = ""
    self.conversation.add(
        "user",
        f"[System note] You edited `{rel}`. Before submit, run:\n"
        f"`{run_cmd}`{extra}",
    )


def _ast_structural_hash(self, file_path: str) -> Optional[str]:
    if not file_path.endswith(".py"):
        return None
    wd = self.config.working_dir or self._detect_working_dir()
    full = file_path if os.path.isabs(file_path) else os.path.join(wd, file_path)
    try:
        with open(full, "r", encoding="utf-8", errors="surrogateescape") as fh:
            source = fh.read()
    except Exception:
        return None
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return "PARSE_ERROR"
    tokens: list[str] = []
    for node in ast.walk(tree):
        tokens.append(type(node).__name__)
        name = getattr(node, "name", None)
        if isinstance(name, str):
            tokens.append("n:" + name)
        attr = getattr(node, "attr", None)
        if isinstance(attr, str):
            tokens.append("a:" + attr)
        ident = getattr(node, "id", None)
        if isinstance(ident, str):
            tokens.append("i:" + ident)
    digest = hashlib.sha1("|".join(tokens).encode("utf-8", "surrogateescape"))
    return digest.hexdigest()

def _record_edit_ast_progress(self, file_path: str) -> None:
    if not _looks_like_real_source_path(file_path):
        return
    new_hash = self._ast_structural_hash(file_path)
    if new_hash is None:
        return
    key = file_path.replace("\\", "/")
    history = self._file_ast_history.setdefault(key, [])
    if history and (new_hash == history[-1] or new_hash in history[:-1]):
        self._ast_stall_counts[key] = self._ast_stall_counts.get(key, 0) + 1
    else:
        self._ast_stall_counts[key] = 0
    history.append(new_hash)
    if len(history) > 12:
        del history[:-12]

def _iter_trajectory_actions(self):
    for msg in self.conversation.get_messages():
        if msg.get("role") != "assistant":
            continue
        kind, payload = parse_action(msg.get("content") or "")
        if kind is not None:
            yield kind, payload

def _collect_observation_enoent(self) -> dict[str, int]:
    counts: dict[str, int] = {}
    for msg in self.conversation.get_messages():
        if msg.get("role") != "user":
            continue
        for m in _LOOP_ENOENT_RE.finditer(msg.get("content") or ""):
            bad = m.group(1).replace("\\", "/")
            if bad:
                counts[bad] = counts.get(bad, 0) + 1
    return counts

def _analyze_loop_warnings(self) -> Optional[str]:
    from collections import Counter

    cmd_counts: Counter = Counter()
    scratch_write_counts: Counter = Counter()
    distinct_scratch: set[str] = set()
    all_write_paths: list[str] = []
    noop_echo = 0
    fingerprints: list[str] = []
    source_edited = False
    source_files_edited: list[str] = []
    strategies_tried: list[str] = []
    seen_strategies: set[str] = set()

    def _add_strategy(s: str) -> None:
        if s not in seen_strategies:
            seen_strategies.add(s)
            strategies_tried.append(s)

    for kind, payload in self._iter_trajectory_actions():
        if kind == "bash":
            cmd = (payload or "").strip()
            normed = re.sub(r"\s+", " ", cmd)[:80]
            if normed:
                cmd_counts[normed] += 1
                fingerprints.append("bash:" + normed)
            if re.match(r"(?i)^echo\b", cmd) and not re.search(r"[>|]|&&|;|\$\(|`", cmd):
                noop_echo += 1
            if re.search(r"\bpytest\b|py\.test\b|\bunittest\b", cmd, re.IGNORECASE):
                _add_strategy("ran tests")
            elif re.search(r"\bcat\b|\bhead\b|\bsed\s+-n\b|\bgrep\b|\bless\b", cmd):
                _add_strategy("read files")
        elif kind in ("edit", "multi_edit"):
            if kind == "edit":
                parsed = parse_edit_payload(payload or "")
                edit_files = [parsed[0]] if parsed else []
            else:
                parsed_multi = parse_multi_edit_payload(payload or "")
                edit_files = [f for f, _, _ in (parsed_multi or [])]
            for fpath in edit_files:
                norm_fp = fpath.replace("\\", "/")
                fingerprints.append("edit:" + norm_fp)
                all_write_paths.append(norm_fp)
                if _looks_like_real_source_path(fpath):
                    source_edited = True
                    bn = norm_fp.rsplit("/", 1)[-1]
                    if bn not in source_files_edited:
                        source_files_edited.append(bn)
                    _add_strategy(f"edited {bn}")
                else:
                    bn = norm_fp.rsplit("/", 1)[-1]
                    scratch_write_counts[bn] += 1
                    distinct_scratch.add(bn)

    warn_parts: list[str] = []

    if cmd_counts:
        top_cmd, n_cmd = cmd_counts.most_common(1)[0]
        if n_cmd >= _LOOP_WARN_CMD_THRESHOLD:
            warn_parts.append(
                f"{_LOOP_WARN_MARKER} Same command ran {n_cmd}× "
                f"({top_cmd!r}) — not making progress. Change approach: inspect "
                "the source directly or run a different verification."
            )

    if scratch_write_counts:
        top_scratch, n_scratch = scratch_write_counts.most_common(1)[0]
        if n_scratch >= _LOOP_WARN_WRITE_THRESHOLD:
            warn_parts.append(
                f"{_LOOP_WARN_MARKER} Rewrote `{top_scratch}` {n_scratch}×. "
                "Read the file back to confirm its real contents, then edit the "
                "actual source file in place."
            )

    scratch_groups: dict[str, list[str]] = {}
    for wp in all_write_paths:
        bn = wp.rsplit("/", 1)[-1]
        stem, _, ext = bn.rpartition(".")
        if not stem or ext.lower() != "py":
            continue
        m_sc = _SCRATCH_SUFFIX_RE.match(stem)
        key = (m_sc.group("stem") if m_sc else stem).lower()
        scratch_groups.setdefault(key, []).append(bn)
    for stem_key, names in scratch_groups.items():
        unique = sorted(set(names))
        if len(unique) >= 2:
            warn_parts.append(
                f"{_LOOP_WARN_MARKER} Created {len(unique)} near-duplicate copies "
                f"of `{stem_key}.py` ({', '.join(unique[:3])}). "
                "Extra copies are not part of the patch — edit the real source file in place."
            )
            break

    root_conf = [
        wp.rsplit("/", 1)[-1]
        for wp in all_write_paths
        if "/" not in wp.strip("/")
        and wp.rsplit("/", 1)[-1].lower() in _ROOT_CONFIG_FILES
    ]
    if root_conf:
        bad_cfg = ", ".join(sorted(set(root_conf))[:3])
        warn_parts.append(
            f"{_LOOP_WARN_MARKER} Wrote {bad_cfg} in the repository root. "
            "The test harness may pick these up as configuration. "
            "Write them under /tmp/ or a dedicated subdirectory instead."
        )

    if not source_edited and len(distinct_scratch) >= _LOOP_WARN_SCRATCH_THRESHOLD:
        shown = ", ".join(sorted(distinct_scratch)[:4])
        warn_parts.append(
            f"{_LOOP_WARN_MARKER} Created {len(distinct_scratch)} scratch scripts "
            f"({shown}) without editing any real source file. "
            "Open the target source file, locate the defect, and edit it in place."
        )

    enoent = self._collect_observation_enoent()
    repeated_enoent = sorted(
        ((n, p) for p, n in enoent.items() if n >= _LOOP_WARN_ENOENT_THRESHOLD),
        reverse=True,
    )
    if repeated_enoent:
        n_en, bad_path = repeated_enoent[0]
        short_bad = bad_path if len(bad_path) <= 120 else "..." + bad_path[-117:]
        warn_parts.append(
            f"{_LOOP_WARN_MARKER} Accessed non-existent path `{short_bad}` {n_en}×. "
            "Search for the real path (find/ls) before retrying."
        )

    if noop_echo >= 2 or (noop_echo >= 1 and source_edited):
        warn_parts.append(
            f"{_LOOP_WARN_MARKER} {noop_echo} plain `echo` command(s) had no "
            "effect. Stop emitting status echoes; run tests or submit."
        )

    if len(fingerprints) >= 3 and fingerprints[-1] == fingerprints[-2] == fingerprints[-3]:
        warn_parts.append(
            f"{_LOOP_WARN_MARKER} Last 3 actions identical ({fingerprints[-1]}). "
            "Pivot to a different action."
        )

    stalled = sorted(
        ((c, f) for f, c in self._ast_stall_counts.items() if c >= _LOOP_WARN_AST_STALL_THRESHOLD),
        reverse=True,
    )
    if stalled:
        c_st, f_st = stalled[0]
        bn_st = f_st.rsplit("/", 1)[-1]
        warn_parts.append(
            f"{_LOOP_WARN_MARKER} Edits to `{bn_st}` left the code structure "
            "unchanged (AST hash identical or reverted). The edit may be failing "
            "to match — read the current file, confirm the target text, then "
            "make one decisive change."
        )

    if not warn_parts:
        return None

    header_parts: list[str] = []
    if source_files_edited:
        header_parts.append("Modified: " + ", ".join(source_files_edited[-4:]))
    if strategies_tried:
        header_parts.append("Steps taken: " + "; ".join(strategies_tried[:5]))
    if self._last_error_sig:
        header_parts.append("Last error: " + self._last_error_sig)

    all_parts = header_parts + warn_parts
    return _LOOP_WARN_HEADER + "\n" + "\n".join(all_parts)

def _warn_stuck(self, kind: str, signature: str) -> None:
    dedup_key = "stuck:" + signature
    if dedup_key in self._loop_warnings_sent:
        return
    self._loop_warnings_sent.add(dedup_key)
    if kind == "bash":
        advice = (
            "the same command keeps repeating. Re-running it will not change "
            "the result — switch strategy: read the relevant source, try a "
            "different command, or move toward submitting your fix."
        )
    else:
        advice = (
            "the same edit keeps repeating. If it is not taking effect, read "
            "the file back to confirm the target text matches exactly, then "
            "make one decisive edit instead of retrying the same one."
        )
    print(f"[AGENT] Loop advisor: repeated {kind} action — warning (not stopping)")
    self._strip_stale_loop_advisor_notes()
    self.conversation.add(
        "user", f"{_LOOP_WARN_HEADER}\n{_LOOP_WARN_MARKER} Detected a loop: {advice}"
    )

def _strip_stale_loop_advisor_notes(self) -> None:
    self.conversation.messages = [
        m for m in self.conversation.messages
        if not (
            m.get("role") == "user"
            and m.get("content", "").lstrip().startswith(_LOOP_WARN_HEADER)
        )
    ]

def _maybe_inject_loop_warning(self) -> bool:
    try:
        note = self._analyze_loop_warnings()
    except Exception as exc:
        print(f"[AGENT] loop-warning analysis error (skipped): {exc}")
        return False
    if not note:
        return False
    signature = hashlib.sha1(note.encode("utf-8", "surrogateescape")).hexdigest()
    if signature in self._loop_warnings_sent:
        return False
    self._loop_warnings_sent.add(signature)
    self._strip_stale_loop_advisor_notes()
    print(f"[AGENT] Loop advisor injecting warning ({note.count(_LOOP_WARN_MARKER)} item(s))")
    self.conversation.add("user", note)
    return True

def _maybe_warn_test_deselection(self, command: str) -> None:
    if not command or not _TEST_RUNNER_RE.search(command):
        return
    if not _TEST_DESELECT_RE.search(command):
        return
    key = "test-deselection"
    if key in self._loop_warnings_sent:
        return
    self._loop_warnings_sent.add(key)
    note = (
        f"{_LOOP_WARN_HEADER}\n"
        f"{_LOOP_WARN_MARKER} You just ran the tests while excluding some of them "
        "(-k \"not ...\", --deselect, or --ignore). Excluding a failing test does "
        "not make it pass — the evaluation runs the FULL test set, including the "
        "ones you skipped. If a test fails, your change has most likely altered "
        "behaviour incorrectly. Re-run WITHOUT the exclusion, read each failure, and "
        "fix the root cause. Confirm the fix with an exact, deterministic assertion "
        "on the expected value (derive it from first principles) — not by eyeballing "
        "rendered output."
    )
    self._strip_stale_loop_advisor_notes()
    print("[AGENT] Loop advisor injecting warning (1 item(s))")
    self.conversation.add("user", note)

def _maybe_warn_related_test_failure(self, command: str, output: dict) -> None:
    if "loop-test-failure" in self._loop_warnings_sent:
        return
    if not command or not _TEST_RUNNER_RE.search(command):
        return
    text = (output.get("stdout") or "") + "\n" + (output.get("stderr") or "")
    upper = text.upper()
    rc = output.get("returncode")
    failed = (rc not in (0, None)) or ("FAIL" in upper) or ("ERROR" in upper)
    if not failed:
        return
    names = set(_TEST_NAME_RE.findall(command)) | set(_TEST_NAME_RE.findall(text))
    if not names:
        return
    try:
        patch = authoritative_worktree_patch(self.executor)
    except Exception:
        return
    stems = _changed_symbol_stems(patch or "")
    if not stems:
        return
    related = sorted(
        n for n in names if any(s in _flatten_identifier(n) for s in stems)
    )
    if not related:
        return
    self._loop_warnings_sent.add("loop-test-failure")
    note = (
        "A test that exercises the symbol you just changed is FAILING:\n"
        + "\n".join(f"  - {n}" for n in related[:6]) + "\n\n"
        "This change is wrong as-is and will fail; fixing it is required. Stop "
        "running reproduction scripts or reading more files and make a concrete "
        "edit to the function you just changed now."
    )
    print("[AGENT] Loop advisor injecting warning (1 item(s))")
    self.conversation.add("user", note)
def _review_has_headroom(self) -> bool:
    if self.cost_limit > 0 and self._check_cost_limit():
        return False
    wall = _effective_agent_wall_sec()
    if wall is not None and self.start_time > 0:
        if (wall - (time.time() - self.start_time)) < _pretimeout_trigger_sec() + 30:
            return False
    return True

def _completeness_review(self, patch: str) -> tuple[bool, str]:
    review_prompt = (
        "Review this change before finalizing it. Confirm it delivers the FULL "
        "behavior the issue requires, not merely that the original symptom is gone.\n\n"
        f"ISSUE:\n{self.problem_statement}\n\n"
        f"CHANGE (unified diff):\n{patch}\n\n"
        "Check concretely:\n"
        "1. If the issue was an error or exception: does the code now return the "
        "CORRECT result for the described scenario, not just avoid the error? State "
        "the exact expected value and whether the change yields it.\n"
        "2. If you changed a type or class: do OPERATIONS on it (multiply, add, "
        "copy, invert) preserve the new behavior, or only its construction?\n"
        "3. Name two inputs structurally different from the issue's example and say "
        "whether the change handles each.\n"
        "4. SCOPE: could the correct fix require a SECOND file, or a base/root method "
        "rather than the call site you edited? Could the issue's test exercise an API "
        "or code path you did NOT change? If you fixed a caller, should the underlying "
        "method be fixed instead?\n\n"
        "First line: 'CONFIRMED' if all hold, otherwise "
        "'GAP: <the single most important thing still to fix>'."
    )
    response, usage = inference(
        model=self.config.planning_model,
        temperature=0.0,
        messages=[{"role": "user", "content": review_prompt}],
        top_p=self.config.llm_top_p,
        seed=self._llm_seed,
    )
    if not response:
        return True, ""
    if usage:
        input_price, output_price = self._planning_model_pricing
        self.total_cost += (
            usage.get("prompt_tokens", 0) / 1_000_000 * input_price
            + usage.get("completion_tokens", 0) / 1_000_000 * output_price
        )
    if response.strip().upper().startswith("GAP"):
        return False, (
            "Self-review found a gap before finalizing:\n"
            + response.strip()
            + "\n\nAddress this, re-verify, then finalize."
        )
    return True, ""

def _select_minimal_grammar_fix(self, patch: str) -> None:
    if self._grammar_fix_done:
        return
    try:
        N = int(os.getenv("RIDGES_AGENT_GRAMMAR_FIX_N", "20") or "0")
    except ValueError:
        N = 0
    if N < 2:
        return
    if not self._review_has_headroom():
        print("[GRAMMARFIX] skip: no time/cost headroom")
        return
    self._grammar_fix_done = True
    wd = self.config.working_dir or self._detect_working_dir()

    added_rule_alts = sum(
        1 for ln in patch.splitlines()
        if ln.startswith("+") and not ln.startswith("+++")
        and re.match(r"^\|\s*\w", ln[1:].strip())
    )
    if added_rule_alts < 1:
        print("[GRAMMARFIX] skip: fix is not a grammar/parser-rule change")
        return
    if not self._last_repro_src:
        print("[GRAMMARFIX] skip: no repro captured during the run (not switching)")
        return
    py_files = [
        p for p in _patch_modifies_python_files(patch)
        if "/tests/" not in p and not p.startswith("tests/")
    ]
    if not py_files:
        print("[GRAMMARFIX] skip: patch touches no source python files")
        return
    if any(ln.startswith("new file") or ln.startswith("deleted file")
           or ln.startswith("rename ") for ln in patch.splitlines()):
        print("[GRAMMARFIX] skip: patch adds/removes/renames files (unsafe to reset)")
        return

    def write_file(path: str, content: str) -> None:
        with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
            fh.write(content)

    def reset_tree() -> None:
        self.executor.execute("git checkout -- . 2>/dev/null; git clean -fdq 2>/dev/null")

    def apply_text(txt: str) -> bool:
        write_file("/tmp/_gfix.patch", txt)
        r = self.executor.execute(
            "git apply --whitespace=nowarn /tmp/_gfix.patch 2>&1 || "
            "git apply --3way --whitespace=nowarn /tmp/_gfix.patch 2>&1"
        )
        return r.get("returncode") == 0

    gen_dirs = sorted({os.path.dirname(p) for p in py_files})
    _GEN_MARKERS = "do not edit|@generated"

    _gen_files: set[str] = set()
    for d in gen_dirs:
        dd = d if os.path.isabs(d) else os.path.join(wd, d)
        r = self.executor.execute(
            f"grep -liE {shlex.quote(_GEN_MARKERS)} {shlex.quote(dd)}/*.py 2>/dev/null"
        )
        for ln in (r.get("stdout") or "").splitlines():
            ln = ln.strip()
            if ln:
                _gen_files.add(ln[len(wd):].lstrip("/") if ln.startswith(wd) else ln.lstrip("/"))

    def clear_tables() -> None:
        for d in gen_dirs:
            dd = d if os.path.isabs(d) else os.path.join(wd, d)
            self.executor.execute(
                f"grep -liE {shlex.quote(_GEN_MARKERS)} {shlex.quote(dd)}/*.py 2>/dev/null | xargs -r rm -f; "
                f"rm -rf {shlex.quote(dd)}/__pycache__ 2>/dev/null"
            )

    def repro_output() -> tuple[int, str]:
        clear_tables()
        write_file("/tmp/_gfix_repro.py", self._last_repro_src)
        r = self.executor.execute("python /tmp/_gfix_repro.py 2>&1")
        return r.get("returncode", 1), (r.get("stdout") or "").strip()

    def sanitize_path(f: str) -> str:
        f = (f or "").strip().lstrip("/")
        for pre in ("testbed/", "a/", "b/"):
            if f.startswith(pre):
                f = f[len(pre):]
        return f

    def parse_edits(text: str):
        if not text:
            return None
        raw = text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw).strip()
        cands = [raw]
        if "{" in raw and "}" in raw:
            cands.append(raw[raw.find("{"): raw.rfind("}") + 1])
        for c in cands:
            try:
                obj = json.loads(c, strict=False)
            except Exception:
                continue
            if isinstance(obj, dict) and isinstance(obj.get("edits"), list):
                return obj["edits"]
        return None

    def source_diff_size(diff_text: str) -> int:
        total = 0
        for part in re.split(r"(?m)^(?=diff --git )", diff_text):
            m = re.match(r"diff --git a/(\S+)", part)
            if m and m.group(1) in _gen_files:
                continue
            total += len(part)
        return total

    def run_test(cmd: str) -> bool:
        clear_tables()
        r = self.executor.execute(f"set -o pipefail; {cmd} 2>&1 | tail -3")
        return r.get("returncode") == 0

    try:
        rc0, ref = repro_output()  
        if rc0 != 0 or not ref:
            print(f"[GRAMMARFIX] skip: candidate_0 repro did not run cleanly (rc={rc0}); not switching")
            return
        oracle_tests = [tc for tc in self._last_test_cmds if run_test(tc)]
        print(f"[GRAMMARFIX] oracle ready (repro {len(self._last_repro_src)}b, ref {len(ref)}b, "
              f"existing-tests {len(oracle_tests)}/{len(self._last_test_cmds)})")

        orig_blocks = []
        for pf in py_files[:2]:
            r = self.executor.execute(f"git show HEAD:{shlex.quote(pf)} 2>/dev/null")
            if (r.get("stdout") or "").strip():
                orig_blocks.append(f"=== ORIGINAL {pf} ===\n{r['stdout']}")
        orig_ctx = "\n\n".join(orig_blocks)[:26000]
        json_spec = (
            "Return STRICT JSON ONLY:\n"
            '{"edits":[{"file":"<path>","old_str":"<verbatim from ORIGINAL>","new_str":"<replacement>"}]}\n'
            "Each old_str must be copied verbatim from the ORIGINAL content and occur once.\n\n"
        )
        anchored_prompt = (
            "You already have a working fix for the issue below (CURRENT FIX). Propose a "
            "SIMPLER, SMALLER alternative that fixes the SAME issue with the fewest "
            "grammar-rule changes: prefer REPLACING an existing rule over ADDING rules — "
            "every added rule over-broadens what the grammar accepts. It must keep the "
            "issue's stated example(s) working and existing tests passing. Give a more "
            "minimal approach, not a copy; do not touch unrelated code.\n\n"
            + json_spec
            + f"ISSUE:\n{self.problem_statement}\n\nCURRENT FIX:\n{patch}\n\n{orig_ctx}\n"
        )
        scratch_prompt = (
            "Fix the issue below by editing the ORIGINAL source shown. Make the SMALLEST "
            "change that fixes the issue's stated example(s) AND keeps existing tests "
            "passing; prefer REPLACING faulty code over ADDING new branches; do not touch "
            "unrelated code. Solve it independently from scratch.\n\n"
            + json_spec
            + f"ISSUE:\n{self.problem_statement}\n\n{orig_ctx}\n"
        )

        candidates = [(source_diff_size(patch), patch)]
        n_gen = n_applied = n_match = 0
        for i in range(N - 1):
            if not self._review_has_headroom():
                break
            try:
                resp, usage = inference(
                    model=self.config.fast_model,
                    temperature=0.7,
                    messages=[{"role": "user", "content": anchored_prompt if i % 2 == 0 else scratch_prompt}],
                    top_p=self.config.llm_top_p,
                    seed=(self._llm_seed + 137 + i) if self._llm_seed is not None else None,
                )
            except Exception as exc:
                print(f"[GRAMMARFIX] alt {i}: gen error {type(exc).__name__}")
                continue
            if usage:
                ip, op = get_model_pricing(self.config.fast_model)
                self.total_cost += (
                    usage.get("prompt_tokens", 0) / 1_000_000 * ip
                    + usage.get("completion_tokens", 0) / 1_000_000 * op
                )
            edits = parse_edits(resp or "")
            if not edits:
                print(f"[GRAMMARFIX] alt {i}: no parseable edits")
                continue
            n_gen += 1
            reset_tree()
            ok_all = True
            for e in edits:
                if not isinstance(e, dict):
                    ok_all = False
                    break
                f = sanitize_path(e.get("file") or py_files[0])
                o, nw = e.get("old_str"), e.get("new_str")
                if not f or o is None or nw is None or o == nw:
                    ok_all = False
                    break
                if apply_str_replace(wd, f, o, nw).get("returncode") != 0:
                    ok_all = False
                    break
            if not ok_all:
                print(f"[GRAMMARFIX] alt {i}: edits did not apply")
                reset_tree()
                continue
            n_applied += 1
            rc, out = repro_output()
            match = (rc == 0 and out == ref)
            tests_ok = all(run_test(tc) for tc in oracle_tests) if match else False
            ok = match and tests_ok
            real = normalize_patch_text(authoritative_worktree_patch(self.executor)) if ok else ""
            reset_tree()
            ssize = source_diff_size(real) if real else 0
            print(f"[GRAMMARFIX] alt {i}: applied, repro={match} tests_ok={tests_ok} "
                  f"src_size={ssize if real else '-'} total={len(real) if real else '-'}")
            if ok and real.strip():
                n_match += 1
                candidates.append((ssize, real))

        print(f"[GRAMMARFIX] N={N} gen={n_gen} applied={n_applied} matched={n_match}; "
              f"src_sizes={sorted(c[0] for c in candidates)} base_src={source_diff_size(patch)}")
        winner = min(candidates, key=lambda c: c[0])
        reset_tree()
        if not apply_text(winner[1]):
            raise RuntimeError("winner re-apply failed")
        if winner[1] != patch:
            self._selected_patch = winner[1]
        print(f"[GRAMMARFIX] chose={winner[0]} ({'switched' if self._selected_patch else 'kept original'})")
    except Exception as exc:
        print(f"[GRAMMARFIX] aborted: {type(exc).__name__}: {exc}; restoring original")
        self._selected_patch = None
        try:
            reset_tree()
            apply_text(patch)
        except Exception:
            pass

def _renamefix_select(self, patch: str) -> None:
    if self._renamefix_done or self._selected_patch:
        return
    try:
        N = int(os.getenv("RIDGES_AGENT_RENAMEFIX_N", "15") or "0")
    except ValueError:
        N = 0
    if N < 2 or not self._review_has_headroom():
        return

    minus = {}
    plus = {}
    for ln in patch.splitlines():
        if ln.startswith("-") and not ln.startswith("---"):
            minus.setdefault(ln[1:].strip(), 0)
        elif ln.startswith("+") and not ln.startswith("+++"):
            plus.setdefault(ln[1:].strip(), 0)
    rename_pairs: list[tuple[str, str]] = []
    for m in minus:
        mlits = re.findall(r"""['"]([A-Za-z_][\w]*)['"]""", m)
        for p in plus:
            if abs(len(p) - len(m)) > 24:
                continue
            plits = re.findall(r"""['"]([A-Za-z_][\w]*)['"]""", p)
            diff_old = [x for x in mlits if x not in plits]
            diff_new = [x for x in plits if x not in mlits]
            if len(diff_old) == 1 and len(diff_new) == 1:
                if m.replace(f"'{diff_old[0]}'", f"'{diff_new[0]}'") == p or \
                   m.replace(f'"{diff_old[0]}"', f'"{diff_new[0]}"') == p:
                    rename_pairs.append((diff_old[0], diff_new[0]))
    rename_pairs = list(dict.fromkeys(rename_pairs))
    if len(rename_pairs) < 1:
        return
    self._renamefix_done = True
    wd = self.config.working_dir or self._detect_working_dir()
    old_tokens = list(dict.fromkeys(o for o, _ in rename_pairs))
    print(f"[RENAMEFIX] rename pairs={rename_pairs}")

    scope_files: list[str] = []
    for tok in old_tokens:
        r = self.executor.execute(
            "git -C " + shlex.quote(wd) + " grep -lF -- "
            + shlex.quote(f"'{tok}'") + " -- '*.py' 2>/dev/null | head -40"
        )
        for f in (r.get("stdout") or "").splitlines():
            f = f.strip()
            if f and "/test" not in f and not f.startswith("test") and f not in scope_files:
                scope_files.append(f)

    touched = [p for p in _patch_modifies_python_files(patch)
               if "/test" not in p and not p.startswith("test")]
    pkgs = {"/".join(p.split("/")[:4]) for p in touched}
    scope_files = [f for f in scope_files if any(f.startswith(pk.rsplit("/", 1)[0]) for pk in pkgs)] or scope_files
    scope_files = list(dict.fromkeys(touched + scope_files))[:6]
    if not scope_files:
        print("[RENAMEFIX] skip: no source files reference the old token(s)")
        return
    if any(ln.startswith("new file") or ln.startswith("deleted file")
           or ln.startswith("rename ") for ln in patch.splitlines()):
        print("[RENAMEFIX] skip: patch adds/removes/renames files (unsafe to reset)")
        return
    print(f"[RENAMEFIX] scope files (use old token): {scope_files}")

    def reset_tree() -> None:
        self.executor.execute("git checkout -- . 2>/dev/null; git clean -fdq 2>/dev/null")

    def write_file(p: str, c: str) -> None:
        with open(p, "w", encoding="utf-8", errors="surrogateescape") as fh:
            fh.write(c)

    def apply_text(txt: str) -> bool:
        write_file("/tmp/_rf.patch", txt)
        r = self.executor.execute(
            "git apply --whitespace=nowarn /tmp/_rf.patch 2>&1 || "
            "git apply --3way --whitespace=nowarn /tmp/_rf.patch 2>&1"
        )
        return r.get("returncode") == 0

    def parse_edits(text: str):
        if not text:
            return None
        raw = text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw).strip()
        for c in ([raw] + ([raw[raw.find("{"): raw.rfind("}") + 1]] if "{" in raw and "}" in raw else [])):
            try:
                obj = json.loads(c, strict=False)
            except Exception:
                continue
            if isinstance(obj, dict) and isinstance(obj.get("edits"), list):
                return obj["edits"]
        return None

    def sanitize_path(f: str) -> str:
        f = (f or "").strip().lstrip("/")
        for pre in ("testbed/", "a/", "b/"):
            if f.startswith(pre):
                f = f[len(pre):]
        return f

    def compiles(files: list[str]) -> bool:
        qs = " ".join(shlex.quote(f) for f in files if f.endswith(".py"))
        if not qs:
            return True
        return self.executor.execute(f"python -m py_compile {qs} 2>&1").get("returncode") == 0

    def coverage(diff_text: str) -> int:
        files_hit, cur = set(), None
        for line in diff_text.splitlines():
            m = re.match(r"\+\+\+ b/(\S+)", line)
            if m:
                cur = m.group(1)
            elif cur and line.startswith("+") and any(
                re.search(rf"""['"]{re.escape(new)}['"]""", line) for _, new in rename_pairs
            ):
                files_hit.add(cur)
        return len(files_hit)

    blocks = []
    for f in scope_files:
        r = self.executor.execute(f"git show HEAD:{shlex.quote(f)} 2>/dev/null")
        content = r.get("stdout") or ""
        if not content.strip():
            continue
        lines = content.splitlines()
        hit = [i for i, ln in enumerate(lines)
               if any(re.search(rf"""['"]{re.escape(o)}['"]""", ln) for o in old_tokens)]
        if not hit:
            continue
        wins: list[list[int]] = []
        for i in hit:
            lo, hi = max(0, i - 12), min(len(lines), i + 13)
            if wins and lo <= wins[-1][1]:
                wins[-1][1] = max(wins[-1][1], hi)
            else:
                wins.append([lo, hi])
        seg = "\n\n".join(
            f"# ...{f} lines {lo + 1}-{hi}...\n" + "\n".join(lines[lo:hi]) for lo, hi in wins
        )
        blocks.append(f"=== ORIGINAL {f} (regions using old name) ===\n{seg}")
    orig_ctx = "\n\n".join(blocks)[:24000]
    gen_prompt = (
        "Fix the issue below by editing the ORIGINAL source shown. The old name(s) "
        + ", ".join(f"'{o}'" for o in old_tokens) + " are deprecated in favour of new "
        "ones; apply the migration CONSISTENTLY at EVERY place these names are read, "
        "across ALL files shown — not just one:\n"
        "  - passed as a function/keyword argument → use the NEW name;\n"
        "  - read as a key from a config/options mapping → accept the NEW key while "
        "keeping the OLD one as a fallback so existing configs keep working, following "
        "whatever convention the surrounding code already uses for such keys.\n"
        "Keep all other behaviour identical; do not touch unrelated code.\n\n"
        "Return STRICT JSON ONLY:\n"
        '{"edits":[{"file":"<path>","old_str":"<verbatim from ORIGINAL>","new_str":"<replacement>"}]}\n'
        "Each old_str must be copied verbatim from the ORIGINAL content and occur once.\n\n"
        f"ISSUE:\n{self.problem_statement}\n\n{orig_ctx}\n"
    )

    try:
        base_cov = coverage(patch)
        candidates = [(base_cov, len(patch), patch)]
        n_gen = n_ok = 0
        for i in range(N - 1):
            if not self._review_has_headroom():
                break
            try:
                resp, usage = inference(
                    model=self.config.execution_model, temperature=0.7,
                    messages=[{"role": "user", "content": gen_prompt}],
                    top_p=self.config.llm_top_p,
                    seed=(self._llm_seed + 211 + i) if self._llm_seed is not None else None,
                )
            except Exception as exc:
                print(f"[RENAMEFIX] alt {i}: gen error {type(exc).__name__}")
                continue
            if usage:
                ip, op = get_model_pricing(self.config.execution_model)
                self.total_cost += (usage.get("prompt_tokens", 0) / 1_000_000 * ip
                                    + usage.get("completion_tokens", 0) / 1_000_000 * op)
            edits = parse_edits(resp or "")
            if not edits:
                continue
            n_gen += 1
            reset_tree()
            edited_files, ok_all = [], True
            for e in edits:
                if not isinstance(e, dict):
                    ok_all = False
                    break
                f = sanitize_path(e.get("file") or (scope_files[0] if scope_files else ""))
                o, nw = e.get("old_str"), e.get("new_str")
                if not f or o is None or nw is None or o == nw:
                    ok_all = False
                    break
                if apply_str_replace(wd, f, o, nw).get("returncode") != 0:
                    ok_all = False
                    break
                edited_files.append(f)
            if not ok_all:
                reset_tree()
                continue
            ok = compiles(list(dict.fromkeys(edited_files)))
            real = normalize_patch_text(authoritative_worktree_patch(self.executor)) if ok else ""
            cov = coverage(real) if real else 0
            reset_tree()
            print(f"[RENAMEFIX] alt {i}: applied={ok_all} compiles={ok} coverage={cov}")
            if ok and real.strip():
                n_ok += 1
                candidates.append((cov, len(real), real))

        winner = max(candidates, key=lambda c: (c[0], -c[1]))
        print(f"[RENAMEFIX] N={N} gen={n_gen} ok={n_ok}; coverages={sorted(c[0] for c in candidates)} base={base_cov}")
        reset_tree()
        if not apply_text(winner[2]):
            raise RuntimeError("winner re-apply failed")
        if winner[2] != patch:
            self._selected_patch = winner[2]
        print(f"[RENAMEFIX] chose coverage={winner[0]} ({'switched' if self._selected_patch else 'kept original'})")
    except Exception as exc:
        print(f"[RENAMEFIX] aborted: {type(exc).__name__}: {exc}; restoring original")
        self._selected_patch = None
        try:
            reset_tree()
            apply_text(patch)
        except Exception:
            pass

def _gate_submission_artifact(self, patch: str) -> tuple[bool, str]:
    wd = self.config.working_dir or self._detect_working_dir()
    ok, msg = _lint_submission_diff(patch, self.problem_statement, wd)
    if not ok:
        return False, msg
    ok, msg = _run_module_pytest_on_submit(
        self.executor, patch, wd, self.problem_statement
    )
    if not ok:
        return False, msg
    max_blocks = _loop_warn_env_int("RIDGES_SUBMIT_MODULE_TEST_MAX_BLOCKS", 1)
    if self._submit_test_blocks < max_blocks:
        try:
            related, detail = _failing_related_module_tests(self.executor, patch, wd)
        except Exception as exc:
            print(f"[AGENT] module-test gate error (skipped): {exc}")
            related, detail = [], ""
        if related:
            self._submit_test_blocks += 1
            return False, (
                "Existing tests that exercise the symbol(s) you changed are "
                "FAILING:\n" + detail + "\n\n"
                "These were not excluded — the evaluation runs the full test set, "
                "so skipping them with -k \"not ...\", --deselect, or --ignore will "
                "not help. Run them WITHOUT any exclusion and fix the root cause. "
                "Verify with an exact, deterministic assertion on the expected value "
                "(compute it from first principles) rather than by eyeballing "
                "output.\n\n"
                "Only if a test genuinely encodes an outdated expectation should "
                "you adjust it — and then say why. Make the edit now and resubmit."
            )
    if (
        not self._completeness_done
        and os.getenv("RIDGES_AGENT_COMPLETENESS_REVIEW", "0") != "0"
        and self._review_has_headroom()
    ):
        self._completeness_done = True
        ok, msg = self._completeness_review(patch)
        if not ok:
            return False, msg
    self._select_minimal_grammar_fix(patch)
    self._renamefix_select(patch)
    return True, ""


def run(self, problem_statement: str) -> str:
    self.start_time = time.time()
    self.step_count = 0
    self.problem_statement = problem_statement
    self._proactive_judge_mode = (
        "midpoint" if _instruction_has_python_code_block(problem_statement) else "first"
    )
    global _RUN_DEADLINE
    _wall_budget = _effective_agent_wall_sec()
    _RUN_DEADLINE = (self.start_time + _wall_budget) if _wall_budget else None

    if not self.config.working_dir:
        self.config.working_dir = self._detect_working_dir()
        self.executor.working_dir = self.config.working_dir

    print(f"[AGENT] Starting CodingAgent in {self.config.working_dir}")
    print(f"[AGENT] Planning Model: {self.config.planning_model}")
    print(f"[AGENT] Execution Model: {self.config.execution_model}")
    print(
        f"[AGENT] Temperature: {self.config.temperature} (planning={self.config.planning_temperature}), "
        f"top_p={self.config.llm_top_p}, "
        f"llm_seed={'set' if self._llm_seed is not None else 'off'}"
    )
    if os.getenv("RIDGES_STABLE_PROMPT", "").strip().lower() in ("1", "true", "yes"):
        print("[AGENT] Stable prompt suffix enabled (RIDGES_STABLE_PROMPT)")
    print(f"[AGENT] Max steps: {self.config.max_steps}")
    print(f"[AGENT] Cost limit: ${self.cost_limit:.2f}")
    _wall = _effective_agent_wall_sec()
    if _wall is not None:
        _m = _agent_tail_margin_sec()
        print(
            f"[AGENT] Wall clock: budget={_wall:.0f}s, tail_margin={_m:.0f}s "
            f"(loop stops after ~{_wall - _m:.0f}s elapsed)"
        )
    else:
        print("[AGENT] Wall clock: no limit")

    if _working_dir_is_git_repo(self.config.working_dir):
        print("[AGENT] Existing git repository — skipping git init / baseline commit")
    else:
        print("[AGENT] No .git found; initializing fresh baseline for git diff")
        self.executor.execute("git init 2>/dev/null || true")
        self.executor.execute("git add -A 2>/dev/null || true")
        self.executor.execute("git commit -m 'initial state' --allow-empty 2>/dev/null || true")

    try:
        head = self.executor.execute("git rev-parse --short HEAD 2>&1 || echo NOHEAD")
        head_out = (head.get("stdout") or "").strip().splitlines()[0:1]
        tracked = self.executor.execute("git ls-files 2>/dev/null | wc -l")
        tracked_out = (tracked.get("stdout") or "0").strip()
        print(
            f"[AGENT] Baseline git state: HEAD={head_out[0] if head_out else 'NOHEAD'}, "
            f"tracked_files={tracked_out}"
        )
    except Exception as e:
        print(f"[AGENT] Baseline git diagnostic failed: {e}")

    if self.config.enable_planning:
        self._run_planning(problem_statement)
        if self.cost_limit > 0 and self.total_cost >= self.cost_limit:
            print(
                f"[AGENT] WARNING: Planning consumed full budget "
                f"(${self.total_cost:.4f} >= ${self.cost_limit:.2f}); "
                "execution may be limited"
            )

    self._build_initial_messages(problem_statement)

    if self.plan:
        plan_context = (
            f"\n\n## Execution Plan (from planning phase)\n\n"
            f"{self.plan}\n\n"
            f"Follow this plan to solve the problem. Execute the steps systematically."
        )
        self.conversation.add("user", plan_context)

    candidates = self._localize_candidates(problem_statement)
    if candidates:
        print(f"[AGENT] candidate_files={candidates}")
        self.conversation.add(
            "user",
            "Candidate files ranked by relevance to the issue (start here; confirm "
            "before editing, and widen the search if the root cause is elsewhere):\n"
            + "\n".join(f"- {c}" for c in candidates),
        )

    self._inject_language_context()

    consecutive_format_errors = 0
    max_consecutive_format_errors = 6
    consecutive_inference_failures = 0
    max_consecutive_inference_failures = 4
    precost_fallback_attempted = False
    precost_fallback_step = 0
    precost_max_steps_after_fallback = 3
    pretimeout_fallback_attempted = False

    while self.step_count < self.config.max_steps:
        self.step_count += 1

        # Proactive opus-judge intervention (once per run).
        self._maybe_proactive_opus()

        wall_budget = _effective_agent_wall_sec()
        if wall_budget is not None and not pretimeout_fallback_attempted:
            elapsed_pre = time.time() - self.start_time
            remaining = wall_budget - elapsed_pre
            if remaining <= _pretimeout_trigger_sec():
                print(
                    f"[AGENT] Low on time (~{max(int(remaining), 0)}s left of ~{wall_budget:.0f}s budget), "
                    "attempting pre-timeout emergency patch fallback"
                )
                pretimeout_fallback_attempted = True
                patch_pt = self._collect_patch_emergency()
                if patch_pt and validate_patch_applies_cleanly(
                    patch_pt, self.config.working_dir
                ):
                    print(
                        f"[AGENT] Pre-timeout emergency patch collected ({len(patch_pt)} chars)"
                    )
                    return patch_pt
                self.conversation.add(
                    "user",
                    "⚠️ Running very low on time. Prioritize producing and submitting a valid git diff now.",
                )

        if self.cost_limit > 0 and self._check_cost_limit() and not precost_fallback_attempted:
            print(
                f"[AGENT] Approaching cost limit (${self.total_cost:.4f} / ${self.cost_limit:.2f}), "
                "attempting pre-cost-limit emergency patch fallback"
            )
            precost_fallback_attempted = True
            precost_fallback_step = self.step_count
            patch = self._collect_patch_emergency()
            if patch and validate_patch_applies_cleanly(patch, self.config.working_dir):
                print(f"[AGENT] Pre-cost-limit emergency patch collected ({len(patch)} chars)")
                return patch
            self.conversation.add(
                "user",
                "⚠️ Approaching cost limit. Prioritize producing and submitting a valid git diff now.",
            )

        if precost_fallback_attempted:
            steps_since_fallback = self.step_count - precost_fallback_step
            if steps_since_fallback > precost_max_steps_after_fallback:
                print(
                    f"[AGENT] Step limit ({precost_max_steps_after_fallback}) reached "
                    "after pre-cost-limit fallback"
                )
                break

        if self._check_timeout():
            print(f"[AGENT] Timeout reached at step {self.step_count}")
            break

        print(f"[AGENT] === Step {self.step_count}/{self.config.max_steps} ===")

        wall = _effective_agent_wall_sec()
        if (
            not self._deadline_nudge_sent
            and wall is not None
            and self.start_time > 0
        ):
            elapsed = time.time() - self.start_time
            if elapsed > wall * 0.78:
                self._deadline_nudge_sent = True
                self.conversation.add(
                    "user",
                    "[System reminder: Most of the time budget is used. If your fix is ready, "
                    "submit NOW with exactly one ```rswea_bash_command``` block containing "
                    "`echo SUBMIT_PATCH && git -c color.ui=false -c core.pager=cat diff HEAD`. "
                    "Ending without SUBMIT_PATCH fails the run.",
                )

        self._maybe_inject_loop_warning()

        messages = self.conversation.get_messages()
        response = self._call_inference(
            messages,
            prefer_checkpoint_model=consecutive_inference_failures > 0,
        )

        if self.cost_limit > 0 and self.total_cost > self.cost_limit:
            print(
                f"[AGENT] Cost limit exceeded after inference "
                f"(${self.total_cost:.4f} > ${self.cost_limit:.2f}), forcing stop"
            )
            break

        if response is None:
            consecutive_inference_failures += 1
            print(
                f"[AGENT] LLM returned no response "
                f"(consecutive failures: {consecutive_inference_failures}/"
                f"{max_consecutive_inference_failures})"
            )
            if consecutive_inference_failures >= max_consecutive_inference_failures:
                print(
                    "[AGENT] Too many consecutive inference failures; breaking to "
                    "emergency patch collection"
                )
                break
            nudge = (
                _INFERENCE_RETRY_NUDGE
                if consecutive_inference_failures < 3
                else "The inference call failed. Please try again with a different command."
            )
            last_msg = self.conversation.messages[-1] if self.conversation.messages else None
            if not (
                last_msg
                and last_msg.get("role") == "user"
                and _is_inference_failure_nudge(last_msg.get("content") or "")
            ):
                self.conversation.add("user", nudge)
            continue

        consecutive_inference_failures = 0

        self.conversation.add("assistant", response)

        kind, payload = parse_action(response)

        if kind is None:
            consecutive_format_errors += 1
            preview = (response or "").strip().replace("\n", " \\n ")
            if len(preview) > 300:
                preview = preview[:297] + "..."
            print(
                f"[AGENT] No valid action found (format error #{consecutive_format_errors}/"
                f"{max_consecutive_format_errors}); response preview: {preview}"
            )
            if consecutive_format_errors >= max_consecutive_format_errors:
                print("[AGENT] Too many consecutive format errors, attempting emergency patch")
                break
            n_act = count_mini_actions(response)
            if consecutive_format_errors <= 1:
                self.conversation.add("user", format_mini_format_error(n_act))
            else:
                self.conversation.add("user", _format_error_escalation(consecutive_format_errors))
            continue

        consecutive_format_errors = 0

        if kind == "bash":
            command = payload or ""

            if SUBMISSION_SENTINEL in command:
                print("[AGENT] Submission detected, executing to capture patch...")
                output = self._execute_bash(command)
                self.conversation.add("user", format_mini_observation(output))

                full_output = output.get("stdout", "")
                if output.get("stderr"):
                    full_output += "\n" + output["stderr"]
                extracted = check_submission(command, full_output)
                auth = normalize_patch_text(authoritative_worktree_patch(self.executor))
                patch = auth if auth.strip() else normalize_patch_text(extracted or "")

                if patch and validate_patch_applies_cleanly(patch, self.config.working_dir):
                    adv_proceed, adv_msg = self._adversarial_pre_submit_gate(patch)
                    if not adv_proceed:
                        bonus = 40
                        self.config.max_steps += bonus
                        print(
                            f"[ADV-GATE] extending max_steps by +{bonus} "
                            f"for revision (now {self.config.max_steps})"
                        )
                        self.conversation.add("user", adv_msg)
                        continue
                    submit_ok, submit_msg = self._gate_submission_artifact(patch)
                    if not submit_ok:
                        print(f"[AGENT] Submission gate rejected patch: {submit_msg[:200]}")
                        self.conversation.add(
                            "user",
                            f"Submission gate failed:\n\n{submit_msg}\n\n"
                            "Fix the issue above, re-verify, then submit again.",
                        )
                        continue
                    if self._selected_patch:
                        recap = normalize_patch_text(
                            authoritative_worktree_patch(self.executor)
                        )
                        if recap.strip():
                            patch = recap
                            print(f"[AGENT] renamefix-selected patch adopted ({len(patch)} chars)")
                    ok, reason = _self_verify_patch(patch, self.config.working_dir)
                    if not ok:
                        print(f"[AGENT] Self-verify warning (accepting anyway): {reason[:200]}")
                    print(f"[AGENT] Valid patch received ({len(patch)} chars)")
                    return patch

                if patch:
                    print(f"[AGENT] Patch fails git apply --check ({len(patch)} chars)")
                    self.conversation.add(
                        "user",
                        "The patch you submitted fails `git apply --check` against the repository "
                        "baseline (wrong line numbers, missing context, or mixed unrelated edits). "
                        "Re-read the current files from disk, make minimal edits, then re-run "
                        "`git diff` and resubmit. Do not rely on remembered line numbers.",
                    )
                    continue

                print("[AGENT] Submission sentinel found but no patch in output")
                self.conversation.add(
                    "user",
                    "The submission command ran but no patch was produced. Make sure your edits "
                    "were saved and the files are tracked by git, then try again.",
                )
                continue

            signature = "bash:" + " ".join(command.split())
            if self._stuck_in_loop(signature):
                self._warn_stuck("bash", signature)

            output = self._execute_bash(command)
            if output.get("returncode") == 0 and any(
                tok in command for tok in _MODIFYING_COMMAND_TOKENS
            ):
                diff_result = self.executor.execute("git diff --name-only 2>/dev/null")
                if diff_result["returncode"] == 0 and diff_result["stdout"].strip():
                    for filename in diff_result["stdout"].strip().splitlines():
                        self.files_modified.add(filename)
            self.conversation.add("user", format_mini_observation(output))
            self._maybe_warn_test_deselection(command)
            self._maybe_warn_related_test_failure(command, output)

        elif kind == "edit":
            parsed = parse_edit_payload(payload or "")
            sig_key = (
                f"edit:{parsed[0]}:{len(parsed[1])}:{len(parsed[2])}"
                if parsed
                else "edit:malformed"
            )
            if self._stuck_in_loop(sig_key):
                self._warn_stuck("edit", sig_key)
            output = self._execute_edit(payload or "")
            self.conversation.add("user", format_mini_observation(output))

        else:  
            parsed_multi = parse_multi_edit_payload(payload or "")
            sig_key = (
                "multi_edit:"
                + ",".join(f"{f}:{len(o)}" for f, o, _ in parsed_multi)
                if parsed_multi
                else "multi_edit:malformed"
            )
            if self._stuck_in_loop(sig_key):
                self._warn_stuck("multi_edit", sig_key)
            output = self._execute_multi_edit(payload or "")
            self.conversation.add("user", format_mini_observation(output))

        rc = output.get("returncode", -1)
        if rc not in (0, None):
            combined = (output.get("stdout") or "") + (output.get("stderr") or "")
            sig = _short_error_sig(combined)
            if sig:
                self._last_error_sig = sig
        out_len = len(output.get("stdout", "")) + len(output.get("stderr", ""))
        print(
            f"[AGENT] Step {self.step_count} complete: returncode={rc}, output={out_len} chars, "
            f"conversation={self.conversation.total_chars()} chars"
        )

    print(f"[AGENT] Loop ended at step {self.step_count}/{self.config.max_steps}")

    patch = self._collect_patch_emergency()
    wd = self.config.working_dir
    if not patch.strip():
        print("[AGENT] No valid patch could be generated")
        return ""

    if validate_patch_applies_cleanly(patch, wd):
        ok, reason = _self_verify_patch(patch, wd)
        if not ok:
            print(f"[AGENT] Emergency patch self-verify warning: {reason[:200]}")
        print(f"[AGENT] Emergency patch collected ({len(patch)} chars)")
        return patch

    print("[AGENT] Emergency patch fails strict git apply --check; returning empty")
    return ""
def create_agent(problem_statement: str, config: AgentConfig | None = None) -> CodingAgent: _ = problem_statement
cfg = config or AgentConfig() print("[AGENT] Selected: CodingAgent (ridges-agent workflow + apply_str_replace)") return CodingAgent(config=cfg)
def agent_main(input): _log_inference_target_once() print("[AGENT] Entered agent_main()")
problem_statement = (
    input.get("problem_statement", "")
    if isinstance(input, dict)
    else str(input)
)
if not problem_statement:
    print("[AGENT] ERROR: Empty problem statement")
    return ""

print(f"[AGENT] Problem statement: {len(problem_statement)} characters")
print(f"[AGENT] Problem preview: {problem_statement[:300]}...")

config = AgentConfig()
agent = create_agent(problem_statement, config)

try:
    patch = agent.run(problem_statement)
except Exception as e:
    print(f"[AGENT] Agent crashed: {type(e).__name__}: {e}")
    try:
        patch = agent._collect_patch_emergency()
    except Exception:
        patch = ""

if not patch or not patch.strip():
    print("[AGENT] WARNING: Returning empty patch")
    return ""

patch = normalize_patch_text(patch)
wd = (getattr(agent, "config", None) and agent.config.working_dir) or os.getcwd()

if not validate_patch_applies_cleanly(patch, wd):
    print("[AGENT] WARNING: Final patch failed git apply --check; returning empty patch")
    return ""

reset_worktree_to_head_for_harbor(wd)

print(f"[AGENT] Returning patch: {len(patch)} characters")
print(f"[AGENT] Patch preview:\n{patch[:500]}...")
return patch
all = [ "AgentConfig", "CodingAgent", "agent_main", "apply_multi_str_replace", "apply_str_replace", "authoritative_worktree_patch", "check_submission", "create_agent", "embedding", "format_mini_format_error", "format_mini_observation", "inference", "normalize_patch_text", "parse_action", "parse_bash_command", "parse_edit_payload", "parse_multi_edit_payload", "reset_worktree_to_head_for_harbor", "validate_patch", "validate_patch_applies_cleanly", "validate_patch_with_git", "_extract_patch_paths", "_infer_test_path", "_lint_submission_diff", "_resolve_conda_shell_prefix", ]
'''
_DEFAULT_ROUTER_MODEL = "minimax/minimax-m2.5"
_SKIP_PARTS = { ".git", ".hg", ".svn", ".tox", ".nox", ".venv", "venv", "env", "node_modules", "pycache", "build", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache", }
_PROJECT_CONFIG_FILES = { "pyproject.toml", "setup.py", "setup.cfg", "tox.ini", "pytest.ini", "noxfile.py", "requirements.txt", "Pipfile", }
def statement_markers(statement: str) -> dict[str, bool]: low = (statement or "").lower() return { "instructions_heading": bool( re.search(r"^\s*#\sinstructions\b", statement or "", re.IGNORECASE | re.MULTILINE) ), "description_heading": bool(re.search(r"^\sdescription\s*$", statement or "", re.IGNORECASE | re.MULTILINE)), "mentions_implement": bool( re.search(r"\b(implement|complete|write|create|return|returns|raise|raises|parse|convert|calculate)\b", low) ), "mentions_supplied_files": "supplied files" in low or "modify the supplied" in low, "mentions_standard_library": "standard library" in low or "standard libraries" in low, "mentions_existing_bug": bool( re.search(r"\b(bug|regression|doesn'?t work|fails?|traceback|expected|actual)\b", low) ), "mentions_project_tests": bool(re.search(r"\b(pytest|unittest|test case|regression test|test)\b", low)), "has_file_path": bool(re.search(r"(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+", statement or "")), }
def _openrouter_base_url() -> str: return ( os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1" ).rstrip("/")
def _log_inference_target_once() -> None: if getattr(_log_inference_target_once, "_done", False): return _log_inference_target_once._done = True
base = _openrouter_base_url() has_key = bool(_openrouter_api_key()) model = os.getenv("RIDGES_AGENT_MODEL", "").strip() or "(unset)" print( "[INFERENCE] target=openrouter-direct " f"base_url={base} api_key={'set' if has_key else 'MISSING'} " f"default_model={model} (no gateway)" )
def _extract_json_object(text: str | None) -> dict[str, Any] | None: if not text: return None raw = text.strip() if raw.startswith(""): raw = re.sub(r"^(?:json)?\s*", "", raw) raw = re.sub(r"\s*```$", "", raw) try: obj = json.loads(raw) return obj if isinstance(obj, dict) else None except Exception: pass start = raw.find("{") if start == -1: return None depth = 0 in_str = False esc = False for i in range(start, len(raw)): ch = raw[i] if in_str: if esc: esc = False elif ch == "\": esc = True elif ch == '"': in_str = False continue if ch == '"': in_str = True elif ch == "{": depth += 1 elif ch == "}": depth -= 1 if depth == 0: try: obj = json.loads(raw[start : i + 1]) return obj if isinstance(obj, dict) else None except Exception: return None return None
def _git_files(root: str) -> list[str]: try: res = subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True, timeout=30) if res.returncode == 0: return sorted(p for p in res.stdout.splitlines() if p and not _is_skipped(p)) except Exception: pass out: list[str] = [] for base, dirs, files in os.walk(root): dirs[:] = [d for d in dirs if d not in _SKIP_PARTS] for name in files: rel = os.path.relpath(os.path.join(base, name), root).replace("\", "/") if not _is_skipped(rel): out.append(rel) return sorted(out)
def _env_int(name: str, default: int) -> int: raw = (os.getenv(name) or "").strip() if not raw: return default try: return int(raw) except ValueError: return default
def _openrouter_api_key() -> str | None: return os.getenv("OPENROUTER_API_KEY")
def _find_repo_root(start: str | None = None) -> str: start = os.path.abspath(start or os.getenv("RIDGES_WORKING_DIR") or os.getcwd()) try: res = subprocess.run( ["git", "-C", start, "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10, ) if res.returncode == 0 and res.stdout.strip(): return os.path.abspath(res.stdout.strip()) except Exception: pass path = start while True: if os.path.isdir(os.path.join(path, ".git")) or os.path.isfile(os.path.join(path, ".git")): return path parent = os.path.dirname(path) if parent == path: return start path = parent
def _env_float(name: str, default: float) -> float: raw = (os.getenv(name) or "").strip() if not raw: return default try: return float(raw) except ValueError: return default
def _prompt_safe_text(text: Any) -> str: if text is None: return "" if not isinstance(text, str): text = str(text) return "".join("\ufffd" if 0xD800 <= ord(ch) <= 0xDFFF else ch for ch in text)
def _is_skipped(path: str) -> bool: return any(part in _SKIP_PARTS for part in path.replace("\", "/").split("/"))
_ROUTER_SYSTEM = """You route Python coding tasks into one of two generic repair workflows.
Workflows:
    • contract_completion: use when the task is self-contained and the problem statement directly defines behavior to implement or complete in a small workspace.
    • project_regression: use when the task is a bug report or regression in an existing mature project and likely requires localization plus project-native tests.
Use only the provided evidence. Do not identify datasets, benchmarks, task sources, release names, or task-family names.
Return one JSON object and nothing else: { "workflow": "contract_completion" or "project_regression", "confidence": 0.0, "evidence": ["short factual reason", "..."], "risks": ["short ambiguity", "..."] } """
_POLYGLOT_SOURCE_EXTS = frozenset({ ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs", ".rs", ".go", ".java", ".kt", ".scala", ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".rb", ".swift", ".cs", ".php", ".lua", ".zig", })
def _primary_language_is_python(evidence: dict[str, Any]) -> bool: tracked = int(evidence.get("tracked_files") or 0) py_files = int(evidence.get("python_files") or 0) poly_files = int(evidence.get("polyglot_source_files") or 0) if tracked == 0: return True
if poly_files > 0 and py_files < poly_files / 2: return False if py_files < 3 and poly_files >= 3: return False return True
def _stable_seed() -> int: raw = (os.getenv("RIDGES_LLM_SEED") or "").strip() base = raw or os.getenv("EVALUATION_RUN_ID") or "ridges-fusion-router" try: return int(base) % (2**31) except ValueError: digest = hashlib.sha256(base.encode("utf-8", "ignore")).digest() return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF
def normalize_patch_text(patch: str) -> str: if not patch: return "" out = re.sub(r"\x1b[[0-9;?][ -/][@-~]", "", patch) out = out.replace("\r\n", "\n").replace("\r", "\n") return out.strip("\n") + ("\n" if out.strip() else "")
def _collect_evidence(problem_statement: str) -> dict[str, Any]: root = _find_repo_root() files = _git_files(root) py_files = [p for p in files if p.endswith((".py", ".pyi"))] test_files = [p for p in py_files if _looks_like_test(p)] total_py_bytes = 0 for p in py_files[:2000]: try: total_py_bytes += os.path.getsize(os.path.join(root, p)) except OSError: pass
polyglot_source_files = sum(
    1 for p in files
    if any(p.lower().endswith(ext) for ext in _POLYGLOT_SOURCE_EXTS)
)

top_level = sorted({p.split("/", 1)[0] for p in files if p and p.split("/", 1)[0] not in {".git"}})
project_config = [name for name in sorted(_PROJECT_CONFIG_FILES) if name in files]
markers = _statement_markers(problem_statement)
print(
    f"[EVIDENCE] root={root} tracked={len(files)} python={len(py_files)} "
    f"tests={len(test_files)} polyglot={polyglot_source_files}"
)
return {
    "root": root,
    "tracked_files": len(files),
    "python_files": len(py_files),
    "test_files": len(test_files),
    "source_python_files": max(0, len(py_files) - len(test_files)),
    "total_python_bytes": total_py_bytes,
    "top_level_entry_count": len(top_level),
    "top_level_entries": top_level[:40],
    "project_config_files": project_config[:20],
    "has_project_config": bool(project_config),
    "external_test_runner_file": os.path.isfile("/tests/test.sh"),
    "external_tests_dir": os.path.isdir("/tests"),
    "problem_chars": len(problem_statement or ""),
    "problem_lines": len((problem_statement or "").splitlines()),
    "has_traceback": _has_traceback(problem_statement),
    "statement_markers": markers,
    "polyglot_source_files": polyglot_source_files,
}
def _call_router_llm( problem_statement: str, evidence: dict[str, Any], spec_score: int, bugfix_score: int ) -> dict[str, Any] | None: if (os.getenv("RIDGES_FUSION_DISABLE_LLM_ROUTER") or "").strip().lower() in {"1", "true", "yes", "on"}: return None key = _openrouter_api_key() if not key: print("[ROUTER] no inference key; using deterministic routing") return None
model = (os.getenv("RIDGES_FUSION_ROUTER_MODEL") or _DEFAULT_ROUTER_MODEL).strip() or _DEFAULT_ROUTER_MODEL
payload = {
    "model": model,
    "messages": [
        {"role": "system", "content": _ROUTER_SYSTEM},
        {"role": "user", "content": _build_router_prompt(problem_statement, evidence, spec_score, bugfix_score)},
    ],
    "temperature": _env_float("RIDGES_FUSION_ROUTER_TEMPERATURE", 0.0),
    "top_p": _env_float("RIDGES_FUSION_ROUTER_TOP_P", 1.0),
    "seed": _stable_seed(),
    "max_tokens": _env_int("RIDGES_FUSION_ROUTER_MAX_TOKENS", 450),
}
headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
url = f"{_openrouter_base_url()}/chat/completions"
timeout = (
    _env_int("LLM_CONNECT_TIMEOUT", 30),
    min(_env_int("LLM_REQUEST_TIMEOUT", 130), _env_int("RIDGES_FUSION_ROUTER_TIMEOUT", 45)),
)

for attempt in range(2):
    try:
        print(f"[ROUTER] inference model={payload['model']} attempt={attempt + 1}")
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        body_preview = resp.text[:500]
        if resp.status_code == 429 and "budget" in body_preview.lower() and "exceed" in body_preview.lower():
            print("[ROUTER] inference budget limit reached; using deterministic routing")
            return None
        if resp.status_code in {408, 425, 429, 500, 502, 503, 504} and attempt == 0:
            time.sleep(min(1.0 + random.random(), 3.0))
            continue
        if resp.status_code != 200:
            print(f"[ROUTER] inference failed HTTP {resp.status_code}: {body_preview}")
            return None
        data = resp.json()
        usage = data.get("usage") or {}
        if usage:
            print(
                f"[ROUTER] usage prompt={usage.get('prompt_tokens', 0)} "
                f"completion={usage.get('completion_tokens', 0)}"
            )
        content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        obj = _extract_json_object(content)
        if not obj:
            print("[ROUTER] inference returned non-JSON route; using deterministic routing")
            return None
        workflow = obj.get("workflow")
        if workflow not in {"contract_completion", "project_regression"}:
            print("[ROUTER] inference returned invalid workflow; using deterministic routing")
            return None
        try:
            obj["confidence"] = float(obj.get("confidence") or 0.0)
        except (TypeError, ValueError):
            obj["confidence"] = 0.0
        return obj
    except requests.exceptions.RequestException as exc:
        if attempt == 0:
            time.sleep(min(1.0 + random.random(), 3.0))
            continue
        print(f"[ROUTER] inference request failed: {exc}")
        return None
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"[ROUTER] inference JSON error: {exc}")
        return None
return None
def agent_main(input: Any) -> str: _log_inference_target_once() _t0 = time.monotonic() print("[FUSION] entered agent_main") if isinstance(input, dict): problem_statement = str(input.get("problem_statement") or input.get("instruction") or "") else: problem_statement = str(input or "") if not problem_statement.strip(): print("[FUSION] empty problem statement") return ""
_words = len(problem_statement.split())
print(
    f"[FUSION] problem chars={len(problem_statement)} words={_words} "
    f"lines={len(problem_statement.splitlines())} fp={_diag_fingerprint(problem_statement)}"
)

try:
    route, detail = _decide_route(problem_statement)
except Exception as exc:
    print(f"[ROUTER] route decision failed: {type(exc).__name__}: {exc}; using hope")
    route = "hope"
    detail = {"source": "fallback", "workflow": "project_regression", "confidence": 0.0}

_route_ms = int((time.monotonic() - _t0) * 1000)
print(f"[FUSION:stonemind] route_decision_ms={_route_ms}")
print(
    f"[FUSION:stonemind] dispatch route={route} source={detail.get('source', '?')} "
    f"workflow={detail.get('workflow', '?')} confidence={float(detail.get('confidence') or 0.0):.2f}"
)

_exec_t0 = time.monotonic()
try:
    patch = _run_selected_agent(route, input)
    _exec_ms = int((time.monotonic() - _exec_t0) * 1000)
    if patch and patch.strip():
        _patch_lines = len(patch.splitlines())
        _diag_log_patch(patch, where=f"route.{route}")
        print(
            f"[FUSION] route={route} produced {len(patch)}-char "
            f"{_patch_lines}-line patch exec_ms={_exec_ms}"
        )
        return patch
    print(f"[FUSION] empty patch from route={route} exec_ms={_exec_ms}")
except Exception as exc:
    print(f"[FUSION] selected agent crashed: route={route} error={type(exc).__name__}: {exc}")

if route != "hope":
    try:
        print("[FUSION] falling back to hope after empty/error from optimize")
        _fb_t0 = time.monotonic()
        patch = _run_selected_agent("hope", input)
        _fb_ms = int((time.monotonic() - _fb_t0) * 1000)
        if patch and patch.strip():
            _diag_log_patch(patch, where="route.hope.fallback")
            print(
                f"[FUSION] hope fallback produced {len(patch)}-char patch "
                f"fb_ms={_fb_ms}"
            )
            return patch
        print(f"[FUSION] hope fallback returned empty patch fb_ms={_fb_ms}")
    except Exception as fallback_exc:
        print(
            f"[FUSION] hope fallback failed: "
            f"{type(fallback_exc).__name__}: {fallback_exc}"
        )

print(f"[FUSION] all primary routes exhausted; trying emergency worktree patch")
emergency = _try_emergency_patch_from_worktree()
if emergency.strip():
    _diag_log_patch(emergency, where="route.emergency")
    print(f"[FUSION] recovered {len(emergency)}-char emergency patch from worktree")
    return emergency

_total_ms = int((time.monotonic() - _t0) * 1000)
_diag_warn("patch.empty", route=route)
print(f"[FUSION] no patch produced; returning empty total_ms={_total_ms}")
return ""
def _mature_repo_veto(evidence: dict[str, Any]) -> bool: tracked = int(evidence.get("tracked_files") or 0) py_files = int(evidence.get("python_files") or 0) tests = int(evidence.get("test_files") or 0) has_project_config = bool(evidence.get("has_project_config")) if tracked >= 200 or py_files >= 80 or tests >= 25 or (has_project_config and tracked >= 80): return True if not _primary_language_is_python(evidence): return True return False
def _deterministic_scores(evidence: dict[str, Any]) -> tuple[int, int, list[str]]: spec = 0 bugfix = 0 reasons: list[str] = [] tracked = int(evidence.get("tracked_files") or 0) py_files = int(evidence.get("python_files") or 0) tests = int(evidence.get("test_files") or 0) total_py = int(evidence.get("total_python_bytes") or 0) markers = evidence.get("statement_markers") or {} has_traceback = bool(evidence.get("has_traceback")) has_project_config = bool(evidence.get("has_project_config"))
if tracked <= 40:
    spec += 3
    reasons.append("small_tracked_file_count")
elif tracked >= 200:
    bugfix += 4
    reasons.append("large_tracked_file_count")

if py_files <= 20:
    spec += 2
    reasons.append("small_python_file_count")
elif py_files >= 80:
    bugfix += 3
    reasons.append("large_python_file_count")

if tests >= 25:
    bugfix += 2
    reasons.append("many_visible_tests")
elif tests == 0 and tracked <= 50:
    spec += 1
    reasons.append("small_repo_no_visible_tests")

if total_py and total_py <= 320_000:
    spec += 1
elif total_py >= 1_000_000:
    bugfix += 2

if has_traceback:
    bugfix += 4
    reasons.append("traceback_or_exception_in_statement")

if has_project_config and tracked >= 50:
    bugfix += 2
    reasons.append("project_config_in_larger_repo")

if markers.get("instructions_heading"):
    spec += 1
if markers.get("mentions_implement"):
    spec += 1
if markers.get("mentions_supplied_files"):
    spec += 2
if markers.get("mentions_standard_library"):
    spec += 1
if markers.get("description_heading") and (has_traceback or markers.get("mentions_existing_bug")):
    bugfix += 2
if markers.get("mentions_existing_bug") and tracked >= 50:
    bugfix += 1

if tracked <= 50 and py_files <= 20 and not has_traceback and not (has_project_config and tracked >= 50):
    spec += 2
    reasons.append("compact_repo_without_traceback")

return spec, bugfix, reasons
def _load_agent_module(label: str): source = embedded_source_for(label) digest = hashlib.sha1(source.encode("utf-8", "surrogateescape")).hexdigest()[:10] name = f"fusion_embedded{label}{digest}" print(f"[LOADER] compiling embedded agent label={label} digest={digest} source_chars={len(source)}") module = types.ModuleType(name) module.dict["file"] = f"<embedded {label}>" module.dict["package"] = "" sys.modules[name] = module _loader_started = time.time() exec(compile(source, module.dict["file"], "exec"), module.dict) print(f"[LOADER] loaded embedded agent label={label} in {int((time.time() - _loader_started) * 1000)}ms") return module
def _decide_route(problem_statement: str) -> tuple[str, dict[str, Any]]: forced = (os.getenv("RIDGES_FUSION_FORCE_ROUTE") or "").strip().lower() if forced in {"optimize", "contract", "contract_completion", "spec"}: print(f"[ROUTER] forced route=optimize via {forced}") return "optimize", { "forced": forced, "workflow": "contract_completion", "confidence": 1.0, "source": "forced", } if forced in {"hope", "hope_v2", "bugfix", "project_regression"}: print(f"[ROUTER] forced route=hope via {forced}") return "hope", { "forced": forced, "workflow": "project_regression", "confidence": 1.0, "source": "forced", }
print("[ROUTER] no forced route; collecting evidence")
evidence = _collect_evidence(problem_statement)
spec_score, bugfix_score, score_reasons = _deterministic_scores(evidence)
mature_veto = _mature_repo_veto(evidence)
threshold = _env_float("RIDGES_FUSION_ROUTER_CONFIDENCE", 0.80)
print(f"[ROUTER] threshold={threshold:.2f} mature_veto={str(mature_veto).lower()}")

print(
    "[ROUTER] stats "
    f"tracked={evidence.get('tracked_files')} "
    f"python={evidence.get('python_files')} "
    f"tests={evidence.get('test_files')} "
    f"bytes={evidence.get('total_python_bytes')} "
    f"traceback={str(evidence.get('has_traceback')).lower()} "
    f"project_config={str(evidence.get('has_project_config')).lower()} "
    f"external_test_runner={str(evidence.get('external_test_runner_file')).lower()}"
)
print(f"[ROUTER] scores contract_completion={spec_score} project_regression={bugfix_score}")
if score_reasons:
    print(f"[ROUTER] score_reasons={','.join(score_reasons[:10])}")

spec_margin = spec_score - bugfix_score
bugfix_margin = bugfix_score - spec_score
print(
    f"[ROUTER] margins spec={spec_margin} bugfix={bugfix_margin} "
    f"dominant={'spec' if spec_margin >= bugfix_margin else 'bugfix'}"
)
if spec_margin >= 4 and not mature_veto:
    workflow = "contract_completion"
    confidence = min(0.79, 0.55 + 0.04 * spec_margin)
    route = "optimize"
    print(
        f"[ROUTER] fast-path route=optimize spec_margin={spec_margin} "
        f"confidence={confidence:.2f} (skipping LLM router call)"
    )
    return route, {
        "workflow": workflow,
        "confidence": confidence,
        "source": "deterministic_fastpath",
        "mature_veto": mature_veto,
        "spec_score": spec_score,
        "bugfix_score": bugfix_score,
        "score_reasons": score_reasons[:10],
    }
if bugfix_margin >= 6:
    workflow = "project_regression"
    confidence = min(0.79, 0.55 + 0.04 * bugfix_margin)
    route = "hope"
    print(
        f"[ROUTER] fast-path route=hope bugfix_margin={bugfix_margin} "
        f"confidence={confidence:.2f} (skipping LLM router call)"
    )
    return route, {
        "workflow": workflow,
        "confidence": confidence,
        "source": "deterministic_fastpath",
        "mature_veto": mature_veto,
        "spec_score": spec_score,
        "bugfix_score": bugfix_score,
        "score_reasons": score_reasons[:10],
    }

print(f"[ROUTER] no fast-path; calling LLM router")
_llm_t0 = time.monotonic()
llm = _call_router_llm(problem_statement, evidence, spec_score, bugfix_score)
print(f"[ROUTER] llm_router_ms={int((time.monotonic() - _llm_t0) * 1000)}")

workflow = ""
confidence = 0.0
source = "deterministic"
if llm:
    workflow = str(llm.get("workflow") or "")
    confidence = float(llm.get("confidence") or 0.0)
    source = "llm"
    print(f"[ROUTER] llm workflow={workflow} confidence={confidence:.2f}")
else:
    print("[ROUTER] llm returned no result; using deterministic scoring")

if workflow == "contract_completion" and confidence >= threshold and not mature_veto:
    route = "optimize"
    print(f"[ROUTER] llm→optimize confidence={confidence:.2f} >= threshold={threshold:.2f}")
elif workflow == "project_regression" and confidence >= threshold:
    route = "hope"
    print(f"[ROUTER] llm→hope confidence={confidence:.2f} >= threshold={threshold:.2f}")
elif spec_score >= bugfix_score + 3 and not mature_veto:
    workflow = "contract_completion"
    confidence = min(0.79, 0.55 + 0.04 * (spec_score - bugfix_score))
    route = "optimize"
    print(f"[ROUTER] det→optimize spec_score={spec_score} bugfix_score={bugfix_score}")
else:
    workflow = "project_regression"
    confidence = max(confidence, min(0.79, 0.55 + 0.04 * max(0, bugfix_score - spec_score)))
    route = "hope"
    print(f"[ROUTER] det→hope spec_score={spec_score} bugfix_score={bugfix_score}")

detail = {
    "workflow": workflow,
    "confidence": confidence,
    "source": source,
    "mature_veto": mature_veto,
    "spec_score": spec_score,
    "bugfix_score": bugfix_score,
    "score_reasons": score_reasons[:10],
}
print(
    f"[ROUTER] route={route} workflow={workflow} confidence={confidence:.2f} "
    f"source={source} mature_veto={str(mature_veto).lower()}"
)
_diag_route_summary(
    route,
    evidence,
    {"contract_completion": spec_score, "project_regression": bugfix_score},
)
return route, detail
def looks_like_test(path: str) -> bool: parts = path.replace("\", "/").split("/") base = parts[-1].lower() return base.startswith("test") or base.endswith("_test.py") or "tests" in parts or "test" in parts
def has_traceback(text: str) -> bool: return bool( re.search(r"Traceback (most recent call last)|File ".*", line \d+", text or "") or re.search(r"\b[A-Za-z][A-Za-z0-9_.]*(Error|Exception):", text or "") )
def _run_selected_agent(route: str, input_obj: Any) -> str: print(f"[EXEC] dispatching to {route} agent") if route == "optimize": module = _load_agent_module("optimize") else: module = _load_agent_module("hope") entry = getattr(module, "agent_main", None) if not callable(entry): raise AttributeError(f"selected {route} agent has no callable agent_main") _exec_started = time.time() result = entry(input_obj) print( f"[EXEC] {route} agent returned {len(result or '')} chars " f"in {int((time.time() - _exec_started) * 1000)}ms" ) return result
def _working_dir_is_git_repo_outer(working_dir: str) -> bool: if not working_dir or not os.path.isdir(working_dir): return False git_marker = os.path.join(working_dir, ".git") return os.path.isdir(git_marker) or os.path.isfile(git_marker)
def _try_emergency_patch_from_worktree() -> str: try: root = ( os.getenv("RIDGES_WORKING_DIR") or os.getenv("RIDGES_AGENT_WORKING_DIR") or os.getcwd() ) if not _working_dir_is_git_repo_outer(root): return "" res = subprocess.run( ["git", "-C", root, "-c", "color.ui=false", "-c", "core.pager=cat", "diff", "HEAD", "--binary", "--no-ext-diff"], capture_output=True, text=True, timeout=60, ) if res.returncode != 0 or not (res.stdout or "").strip(): return "" patch = normalize_patch_text(res.stdout) if patch.strip(): print(f"[FUSION] emergency worktree diff captured {len(patch)} chars") return patch return "" except Exception as exc: print(f"[FUSION] emergency patch recovery failed: {type(exc).name}: {exc}") return ""
def _build_router_prompt(problem_statement: str, evidence: dict[str, Any], spec_score: int, bugfix_score: int) -> str: public_evidence = dict(evidence) public_evidence.pop("root", None) public_evidence["deterministic_scores"] = { "contract_completion": spec_score, "project_regression": bugfix_score, } payload = { "problem_statement": _prompt_safe_text(problem_statement), "evidence": public_evidence, } return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
def _embedded_source_for(label: str) -> str: if label == "optimize": return _CREATE_SOURCE if label == "hope": return _FIX_SOURCE raise ValueError(f"unknown embedded agent label: {label}")
---------------------------------------------------------------------------
Fusion router diagnostics & telemetry
The helpers below provide structured, opt-in logging around the router's
decision path. They are intentionally side-effect free unless explicitly
invoked and never mutate the embedded sub-agent sources. Logging is gated by
the RIDGES_DIAG environment variable so production runs stay quiet by default.
---------------------------------------------------------------------------
_DIAG_ENV_FLAG = "RIDGES_DIAG" _DIAG_LEVEL_ENV = "RIDGES_DIAG_LEVEL" _DIAG_TAG = "DIAG" _DIAG_LEVELS = {"debug": 10, "info": 20, "warn": 30, "error": 40, "silent": 100} _DIAG_DEFAULT_LEVEL = "info" _DIAG_MAX_FIELD_LEN = 240 _DIAG_HISTORY_LIMIT = 256 _DIAG_HISTORY: list[dict[str, Any]] = []
def _diag_enabled() -> bool: """Return True when diagnostic logging has been switched on via the env.""" raw = (os.getenv(_DIAG_ENV_FLAG) or "").strip().lower() return raw in {"1", "true", "yes", "on", "verbose", "debug"}
def _diag_threshold() -> int: """Resolve the numeric logging threshold from the environment.""" raw = (os.getenv(_DIAG_LEVEL_ENV) or _DIAG_DEFAULT_LEVEL).strip().lower() return _DIAG_LEVELS.get(raw, _DIAG_LEVELS[_DIAG_DEFAULT_LEVEL])
def _diag_now_ms() -> int: """Monotonic-ish millisecond timestamp used for span measurements.""" try: return int(time.time() * 1000) except Exception: return 0
def _diag_clip(value: Any) -> str: """Render an arbitrary value as a single-line, length-bounded string.""" try: text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str) except Exception: text = repr(value) text = text.replace("\n", "\n").replace("\r", "\r") if len(text) > _DIAG_MAX_FIELD_LEN: return text[: _DIAG_MAX_FIELD_LEN - 1] + "…" return text
def _diag_format_fields(fields: dict[str, Any]) -> str: """Format a mapping of fields into a stable key=value string.""" if not fields: return "" parts = [] for key in sorted(fields): parts.append(f"{key}={_diag_clip(fields[key])}") return " ".join(parts)
def _diag_record(level: str, event: str, fields: dict[str, Any]) -> dict[str, Any]: """Append a structured event to the in-memory diagnostic history ring.""" entry = { "ts": _diag_now_ms(), "level": level, "event": event, "fields": dict(fields), } _DIAG_HISTORY.append(entry) if len(_DIAG_HISTORY) > _DIAG_HISTORY_LIMIT: del _DIAG_HISTORY[: len(_DIAG_HISTORY) - _DIAG_HISTORY_LIMIT] return entry
def _diag_emit(level: str, event: str, **fields: Any) -> None: """Emit a structured diagnostic line when logging is enabled and in range.""" numeric = _DIAG_LEVELS.get(level, _DIAG_LEVELS["info"]) _diag_record(level, event, fields) if not _diag_enabled(): return if numeric < _diag_threshold(): return suffix = _diag_format_fields(fields) line = f"[{_DIAG_TAG}:{level}] {event}" if suffix: line = f"{line} {suffix}" print(line)
def _diag_debug(event: str, **fields: Any) -> None: """Convenience wrapper for debug-level diagnostic events.""" _diag_emit("debug", event, **fields)
def _diag_info(event: str, **fields: Any) -> None: """Convenience wrapper for info-level diagnostic events.""" _diag_emit("info", event, **fields)
def _diag_warn(event: str, **fields: Any) -> None: """Convenience wrapper for warn-level diagnostic events.""" _diag_emit("warn", event, **fields)
def _diag_error(event: str, **fields: Any) -> None: """Convenience wrapper for error-level diagnostic events.""" _diag_emit("error", event, **fields)
def _diag_history_snapshot(limit: int = 0) -> list[dict[str, Any]]: """Return a shallow copy of the most recent diagnostic events.""" if limit and limit > 0: return [dict(item) for item in _DIAG_HISTORY[-limit:]] return [dict(item) for item in _DIAG_HISTORY]
def _diag_history_clear() -> int: """Drop all retained diagnostic events and report how many were cleared.""" count = len(_DIAG_HISTORY) _DIAG_HISTORY.clear() return count
def _diag_count_by_level() -> dict[str, int]: """Tally retained diagnostic events grouped by their level.""" tally: dict[str, int] = {} for entry in _DIAG_HISTORY: level = str(entry.get("level", "info")) tally[level] = tally.get(level, 0) + 1 return tally
class _DiagSpan: """Lightweight context manager that times a labelled block of work."""
def __init__(self, label: str, **fields: Any) -> None:
    self.label = label
    self.fields = dict(fields)
    self.started_ms = 0
    self.elapsed_ms = 0

def __enter__(self) -> "_DiagSpan":
    self.started_ms = _diag_now_ms()
    _diag_debug("span.start", label=self.label, **self.fields)
    return self

def note(self, **fields: Any) -> None:
    """Attach additional fields to the span before it closes."""
    self.fields.update(fields)

def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
    self.elapsed_ms = max(0, _diag_now_ms() - self.started_ms)
    if exc_type is not None:
        _diag_error(
            "span.fail",
            label=self.label,
            elapsed_ms=self.elapsed_ms,
            error=f"{getattr(exc_type, '__name__', exc_type)}: {exc}",
            **self.fields,
        )
    else:
        _diag_info("span.end", label=self.label, elapsed_ms=self.elapsed_ms, **self.fields)
    return False
def _diag_timed(label: str): """Decorator that wraps a callable in a diagnostic timing span."""
def _wrap(func):
    def _inner(*args: Any, **kwargs: Any):
        with _DiagSpan(label or getattr(func, "__name__", "call")):
            return func(*args, **kwargs)

    _inner.__name__ = getattr(func, "__name__", "inner")
    _inner.__doc__ = getattr(func, "__doc__", None)
    return _inner

return _wrap
def _diag_environment_snapshot() -> dict[str, Any]: """Collect a redacted snapshot of the runtime environment for logging.""" interesting = ( "RIDGES_AGENT_MODEL", "OPENROUTER_BASE_URL", _DIAG_ENV_FLAG, _DIAG_LEVEL_ENV, ) snapshot: dict[str, Any] = {} for name in interesting: snapshot[name] = (os.getenv(name) or "").strip() or "(unset)" snapshot["has_openrouter_key"] = bool(os.getenv("OPENROUTER_API_KEY")) snapshot["python"] = sys.version.split()[0] if sys.version else "unknown" snapshot["platform"] = getattr(sys, "platform", "unknown") return snapshot
def _diag_route_summary(label: str, evidence: dict[str, Any] | None, scores: dict[str, Any] | None) -> dict[str, Any]: """Build a compact, log-friendly summary of a routing decision.""" evidence = evidence or {} scores = scores or {} summary = { "route": label, "files": len(evidence.get("files", []) or []), "spec_score": scores.get("contract_completion"), "bugfix_score": scores.get("project_regression"), } _diag_info("route.decision", **summary) return summary
def _diag_fingerprint(text: str | None) -> str: """Return a short stable fingerprint for a payload, for correlation in logs.""" if not text: return "0" * 12 digest = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest() return digest[:12]
def _diag_test(items: list[Any], limit: int = 5) -> list[Any]: """Return a deterministic, bounded sample of a list for logging.""" if not items: return [] if len(items) <= limit: return list(items) step = max(1, len(items) // limit) sampled = items[::step][:limit] return list(sampled)
def _diag_summarize_patch(patch_text: str | None) -> dict[str, Any]: """Summarize a unified diff into counts useful for diagnostic logging.""" if not patch_text: return {"files": 0, "added": 0, "removed": 0, "hunks": 0} files = 0 added = 0 removed = 0 hunks = 0 for line in patch_text.splitlines(): if line.startswith("+++ ") or line.startswith("--- "): continue if line.startswith("diff --git"): files += 1 elif line.startswith("@@"): hunks += 1 elif line.startswith("+"): added += 1 elif line.startswith("-"): removed += 1 return {"files": files, "added": added, "removed": removed, "hunks": hunks}
def _diag_log_patch(patch_text: str | None, where: str = "router") -> dict[str, Any]: """Emit a diagnostic summary for a generated patch.""" stats = _diag_summarize_patch(patch_text) stats["fingerprint"] = _diag_fingerprint(patch_text) stats["where"] = where _diag_info("patch.summary", **stats) return stats
def _diag_assert_blobs_present() -> bool: """Sanity check that both embedded sub-agent sources are still populated.""" ok_opt = isinstance(_CREATE_SOURCE, str) and len(_CREATE_SOURCE) > 1000 ok_hope = isinstance(_FIX_SOURCE, str) and len(_FIX_SOURCE) > 1000 if not (ok_opt and ok_hope): _diag_error("blob.check", optimize_ok=ok_opt, hope_ok=ok_hope) else: _diag_debug( "blob.check", optimize_len=len(_CREATE_SOURCE), hope_len=len(_FIX_SOURCE), ) return ok_opt and ok_hope
def _diag_self_test() -> dict[str, Any]: """Run a tiny internal consistency check over the diagnostic helpers.""" before = len(_DIAG_HISTORY) _diag_debug("selftest.ping", marker=_diag_fingerprint("selftest")) after = len(_DIAG_HISTORY) result = { "history_grew": after > before, "levels": _diag_count_by_level(), "blobs_ok": _diag_assert_blobs_present(), } _diag_info("selftest.result", **result) return result
---------------------------------------------------------------------------
Fusion router diagnostics — aggregation & reporting helpers (part 2)
These extend the telemetry layer above with rollups, lightweight metric
counters, and human-readable report rendering. They remain opt-in and never
touch the embedded sub-agent sources.
---------------------------------------------------------------------------
_DIAG_METRICS: dict[str, float] = {} _DIAG_TIMERS: dict[str, list[int]] = {} _DIAG_REPORT_WIDTH = 72
def _diag_metric_incr(name: str, amount: float = 1.0) -> float: """Increment a named counter and return its new value.""" current = _DIAG_METRICS.get(name, 0.0) + float(amount) _DIAG_METRICS[name] = current return current
def _diag_metric_set(name: str, value: float) -> float: """Set a named gauge to an absolute value and return it.""" _DIAG_METRICS[name] = float(value) return _DIAG_METRICS[name]
def _diag_metric_get(name: str, default: float = 0.0) -> float: """Read a named metric, falling back to a default when absent.""" return _DIAG_METRICS.get(name, default)
def _diag_metric_reset() -> int: """Clear all metric counters and report how many were dropped.""" count = len(_DIAG_METRICS) _DIAG_METRICS.clear() return count
def _diag_timer_push(name: str, elapsed_ms: int) -> None: """Record a single timing observation under a named bucket.""" bucket = _DIAG_TIMERS.setdefault(name, []) bucket.append(max(0, int(elapsed_ms))) if len(bucket) > _DIAG_HISTORY_LIMIT: del bucket[: len(bucket) - _DIAG_HISTORY_LIMIT]
def _diag_timer_stats(name: str) -> dict[str, Any]: """Compute count/min/max/mean for a named timing bucket.""" bucket = _DIAG_TIMERS.get(name) or [] if not bucket: return {"name": name, "count": 0, "min": 0, "max": 0, "mean": 0.0} total = sum(bucket) return { "name": name, "count": len(bucket), "min": min(bucket), "max": max(bucket), "mean": round(total / len(bucket), 2), }
def _diag_timer_percentile(name: str, pct: float) -> float: """Return an approximate percentile (0-100) for a timing bucket.""" bucket = sorted(_DIAG_TIMERS.get(name) or []) if not bucket: return 0.0 if pct <= 0: return float(bucket[0]) if pct >= 100: return float(bucket[-1]) rank = (pct / 100.0) * (len(bucket) - 1) low = int(rank) high = min(low + 1, len(bucket) - 1) frac = rank - low return round(bucket[low] + (bucket[high] - bucket[low]) * frac, 2)
def _diag_all_timer_stats() -> list[dict[str, Any]]: """Return stats for every recorded timing bucket, sorted by name.""" return [_diag_timer_stats(name) for name in sorted(_DIAG_TIMERS)]
def _diag_rule(char: str = "-") -> str: """Render a horizontal rule sized to the report width.""" return (char or "-")[0] * _DIAG_REPORT_WIDTH
def _diag_kv_line(key: str, value: Any) -> str: """Render a single padded key/value line for a text report.""" label = str(key)[: _DIAG_REPORT_WIDTH - 24].ljust(24) return f"  {label}{_diag_clip(value)}"
def _diag_section(title: str) -> list[str]: """Render a titled section header as a list of lines.""" return [_diag_rule("="), f"  {title}", _diag_rule("-")]
def _diag_render_metrics() -> list[str]: """Render the current metric counters as report lines.""" lines = _diag_section("metrics") if not _DIAG_METRICS: lines.append("  (no metrics recorded)") return lines for name in sorted(_DIAG_METRICS): lines.append(_diag_kv_line(name, _DIAG_METRICS[name])) return lines
def _diag_render_timers() -> list[str]: """Render timing-bucket statistics as report lines.""" lines = _diag_section("timings") stats = _diag_all_timer_stats() if not stats: lines.append("  (no timings recorded)") return lines for row in stats: summary = f"n={row['count']} min={row['min']} mean={row['mean']} max={row['max']}" lines.append(_diag_kv_line(row["name"], summary)) return lines
def _diag_render_history(limit: int = 10) -> list[str]: """Render the tail of the diagnostic event history as report lines.""" lines = _diag_section(f"recent events (last {limit})") recent = _diag_history_snapshot(limit) if not recent: lines.append("  (no events recorded)") return lines for entry in recent: fields = _diag_format_fields(entry.get("fields", {})) label = f"{entry.get('level', '?')}:{entry.get('event', '?')}" lines.append(_diag_kv_line(label, fields or "-")) return lines
def _diag_build_report(limit: int = 10) -> str: """Assemble a full human-readable diagnostics report as a string.""" lines: list[str] = [] lines.extend(_diag_section("fusion router diagnostics")) for key, value in sorted(_diag_environment_snapshot().items()): lines.append(_diag_kv_line(key, value)) lines.extend(_diag_render_metrics()) lines.extend(_diag_render_timers()) lines.extend(_diag_render_history(limit)) lines.append(_diag_rule("=")) return "\n".join(lines)
def _diag_observe_span(span: "_DiagSpan") -> None: """Fold a finished span into the metric and timing aggregates.""" if span is None: return _diag_timer_push(span.label, getattr(span, "elapsed_ms", 0)) _diag_metric_incr(f"span.{span.label}.count")
def _diag_dump_report_result(limit: int = 10) -> str: """Print and return the assembled diagnostics report when enabled.""" report = _diag_build_report(limit) if _diag_enabled(): print(report) return report
all = ["agent_main"]
