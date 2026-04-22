## Quickstart

1. Create and activate a virtual environment (Windows example):

```powershell
conda create -n essence-agent python=3.11
conda activate essence-agent


uvicorn app.main2:app --reload --host 0.0.0.0

streamlit run streamlit_app.py
```
