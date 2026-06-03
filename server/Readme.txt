# activate venv (if not already)
source venv/bin/activate

# change into server (recommended)
cd server

# run the app
streamlit run app.py
# optionally: streamlit run app.py --server.port 8501

kill 26842 (stops the Streamlit on :8000)
cd /Users/amirschnabel/eclipse-workspace/MindVideo/mind-videos && source venv/bin/activate && uvicorn server:app --reload --port 8000  