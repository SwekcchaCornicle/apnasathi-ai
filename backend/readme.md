# ApnaSathi backend

Install dependencies and start the API from this folder:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app:app --reload --port 8000
```

The frontend's Vite dev server proxies `/api/v1` to `http://192.168.1.4:8006`, matching the running Swagger server and avoiding browser CORS errors. It checks `GET /api/v1/health` and sends recordings as multipart form data to `POST /api/v1/upload-audio` using the `audio` field. Uploaded files are stored in `C:\audio_files`.

If the backend address changes, update the proxy target in `frontend/vite.config.js`. For a production frontend, set `VITE_API_BASE_URL` to the API base URL.
