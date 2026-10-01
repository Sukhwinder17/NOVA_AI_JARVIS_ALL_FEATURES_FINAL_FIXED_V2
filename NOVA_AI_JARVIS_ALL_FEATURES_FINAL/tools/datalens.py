from __future__ import annotations
import webbrowser
from core.config import DATALENS_URL

def open_datalens():
    try:
        ok=webbrowser.open(DATALENS_URL)
        return f'DataLens opened: {DATALENS_URL}' if ok else f'Could not open DataLens: {DATALENS_URL}'
    except Exception as e:
        return f'Could not open DataLens: {e}'
