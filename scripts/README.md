# Scripts Documentation

| Script | Purpose | Usage |
|--------|---------|-------|
| `test_fast.py` | Runs a fast subset of core tests | `python scripts/test_fast.py` |
| `test_full.py` | Runs the complete test suite | `python scripts/test_full.py` |
| `test_mvp.py` | Runs MVP smoke tests only | `python scripts/test_mvp.py` |
| `seed_test_data.py` | Creates a test learner with complete journey for demo | `python scripts/seed_test_data.py` |

## Adding New Scripts

1. Create a new Python file in `scripts/`
2. Add an entry to this README
3. Follow the naming pattern: `<action>_<target>.py`
