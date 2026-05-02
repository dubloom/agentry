import json
from pathlib import Path


REGISTRY_PATH = Path.home() / ".glyph" / "glyphs.json"
LOCAL_GLYPHS_DIR = Path(".glyph") / "glyphs"

class GlyphRegistryError(Exception):
    """Raised when the named glyph registry cannot satisfy a request."""

def add_glyph(name: str, workflow_path: Path) -> Path:
    """Register ``name`` for ``workflow_path`` and return the stored path."""

    resolved_path = workflow_path.expanduser().resolve()
    if not resolved_path.is_file():
        raise GlyphRegistryError(f"workflow file does not exist: {resolved_path}")

    if resolved_path.suffix.lower() != ".md":
        raise GlyphRegistryError(f"workflow file must be a markdown file: {resolved_path}")

    registry = _load_registry()
    if name in registry:
        raise GlyphRegistryError(f"glyph name is already taken: {name}")

    registry[name] = str(resolved_path)
    _save_registry(registry)
    return resolved_path


def _load_registry() -> dict[str, str]:
    path = REGISTRY_PATH
    if not path.exists():
        return {}

    try:
        raw_registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GlyphRegistryError(f"invalid glyph registry at {path}: {exc}") from exc

    if not isinstance(raw_registry, dict):
        raise GlyphRegistryError(f"invalid glyph registry at {path}: expected a JSON object")

    registry: dict[str, str] = {}
    for name, workflow_path in raw_registry.items():
        if not isinstance(name, str) or not isinstance(workflow_path, str):
            raise GlyphRegistryError(f"invalid glyph registry at {path}: names and paths must be strings")
        registry[name] = workflow_path
    return registry


def _save_registry(registry: dict[str, str]) -> None:
    path = REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _discover_local_glyphs(cwd: Path | None = None) -> dict[str, str]:
    search_root = (cwd or Path.cwd()).resolve()
    glyphs_dir = search_root / LOCAL_GLYPHS_DIR
    if not glyphs_dir.is_dir():
        return {}

    local_glyphs: dict[str, str] = {}
    for workflow_path in glyphs_dir.glob("*.md"):
        if workflow_path.is_file():
            local_glyphs[workflow_path.stem] = str(workflow_path.resolve())
    return local_glyphs


def list_available_glyphs(cwd: Path | None = None) -> list[tuple[str, str]]:
    """Return all available glyphs from local folder and global registry."""

    available = _load_registry()
    available.update(_discover_local_glyphs(cwd))
    return sorted(available.items(), key=lambda item: item[0])


def resolve_glyph(name: str, cwd: Path | None = None) -> Path:
    """Resolve a glyph name to its markdown workflow path."""

    local_registry = _discover_local_glyphs(cwd)
    local_path = local_registry.get(name)
    if local_path is not None:
        return Path(local_path)

    global_registry = _load_registry()
    workflow_path = global_registry.get(name)
    if workflow_path is None:
        searched_dir = ((cwd or Path.cwd()).expanduser().resolve() / LOCAL_GLYPHS_DIR).as_posix()
        raise GlyphRegistryError(
            f"unknown glyph: {name}. Searched local glyphs in {searched_dir} and {REGISTRY_PATH}"
        )

    return Path(workflow_path).expanduser()


def remove_glyph(name: str) -> None:
    """Remove a registered glyph name from the registry."""

    registry = _load_registry()
    if name not in registry:
        raise GlyphRegistryError(f"unknown glyph: {name}")

    del registry[name]
    _save_registry(registry)
