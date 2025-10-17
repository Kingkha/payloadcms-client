import sys
import types
from typing import Any, List

try:
    import yaml  # type: ignore  # pragma: no cover
except ModuleNotFoundError:  # pragma: no cover - testing fallback for offline envs
    def _parse_scalar(value: str) -> str:
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        return value

    def _safe_load(text: str) -> dict[str, Any]:
        result: dict[str, Any] = {}
        lines = text.splitlines()
        index = 0

        while index < len(lines):
            line = lines[index]
            index += 1
            if not line.strip():
                continue
            if ':' not in line:
                raise ValueError(f"Invalid line in YAML stub: {line!r}")
            key, rest = line.split(':', 1)
            key = key.strip()
            rest = rest.strip()

            if rest == '|':
                block_lines: List[str] = []
                while index < len(lines) and (lines[index].startswith('  ') or not lines[index].strip()):
                    current = lines[index]
                    if current.startswith('  '):
                        block_lines.append(current[2:])
                    else:
                        block_lines.append('')
                    index += 1
                result[key] = '\n'.join(block_lines)
                continue

            if rest == '':
                items: List[str] = []
                while index < len(lines) and lines[index].lstrip().startswith('- '):
                    item_line = lines[index].lstrip()[2:]
                    items.append(_parse_scalar(item_line))
                    index += 1
                result[key] = items
                continue

            result[key] = _parse_scalar(rest)

        return result

    class _YamlStub(types.ModuleType):
        class YAMLError(Exception):
            pass

        @staticmethod
        def safe_load(text: str) -> dict[str, Any]:
            try:
                return _safe_load(text)
            except Exception as exc:  # pragma: no cover - defensive
                raise _YamlStub.YAMLError(str(exc)) from exc

    yaml = _YamlStub("yaml")
    sys.modules["yaml"] = yaml
else:  # pragma: no cover
    yaml  # noqa: F401 - re-export real PyYAML if available
