import importlib
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MODULES = ["test_indicators", "test_analysis", "test_data", "test_scalper", "test_web"]


def main() -> int:
    passed = 0
    failed = 0
    for name in MODULES:
        mod = importlib.import_module(f"tests.{name}")
        for attr in sorted(dir(mod)):
            if not attr.startswith("test_"):
                continue
            func = getattr(mod, attr)
            try:
                func()
                passed += 1
                print(f"PASS  tests.{name}.{attr}")
            except Exception:
                failed += 1
                print(f"FAIL  tests.{name}.{attr}")
                traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())