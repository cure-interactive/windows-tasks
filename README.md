# Windows Tasks

Windows utility app for small maintenance tasks.

## Current Tasks

- Clear the Windows icon cache
- Uninstall all pip packages from the current Python interpreter except pip itself

## Requirements

- Python 3.10+
- Windows for task behavior
- Dependencies from `requirements.txt`

## Install

```bash
python setup.py --venv
```

Or manually:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

```bash
python windows_tasks.py
```

Some tasks may require administrator privileges. Review the UI text before running destructive maintenance actions.
