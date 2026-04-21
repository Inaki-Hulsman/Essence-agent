## Quickstart

1. Create and activate a virtual environment (Windows example):

```powershell
conda create -n essence-agent python=3.11
conda activate essence-agent


uvicorn app.main4:app --reload

streamlit run streamlit_app.py
```
