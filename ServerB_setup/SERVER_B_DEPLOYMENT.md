# Server B Deployment Guide

This guide explains how to set up the Server B API environment on your Server B machine.

## Files to Transfer

Copy these files from the main DRC_GUI project to Server B:

1. `server_b_api_setup.py` - Main API server
2. `requirements_server_b.txt` - Python dependencies (see below)
3. `.env` - Environment configuration (create from template below)

## Step 1: Install Python Dependencies

Create a `requirements_server_b.txt` file with these dependencies:
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
python-dotenv==1.0.0
```

Then install:
```bash
# If using conda (recommended)
conda create --name server-b-api python=3.10
conda activate server-b-api
pip install -r requirements_server_b.txt

# Or using system Python
pip install -r requirements_server_b.txt
```

## Step 2: Configure Environment

Create a `.env` file on Server B with your production settings:

```bash
# Server B API Configuration
SERVER_B_PORT=8001
SERVER_B_HOST=0.0.0.0
SERVER_B_API_KEY=YOUR-SECURE-API-KEY-HERE
SERVER_B_UPLOAD_DIR=uploads
SERVER_B_RESULTS_DIR=results  
SERVER_B_PROCESSING_DIR=processing

# Optional: Callback URL to your main AI server
CALLBACK_URL=http://your-ai-server-ip:8000/api/v1/callback
```

**Important Security Notes:**
- Change `SERVER_B_API_KEY` to a secure, unique value
- Use the same API key in your main system's `.env` file (`API_SERVER_B_KEY`)
- Consider using HTTPS in production
- Configure firewall rules appropriately

## Step 3: Update Main System Configuration

Update your main system's `.env` file to point to the real Server B:

```bash
# In your main DRC_GUI/.env file
API_SERVER_B_URL=http://your-server-b-ip:8001
API_SERVER_B_KEY=YOUR-SECURE-API-KEY-HERE
```

## Step 4: Start Server B API

On Server B machine:
```bash
# If using conda
conda activate server-b-api
python server_b_api_setup.py

# Or as a service (recommended for production)
# Create systemd service file: /etc/systemd/system/server-b-api.service
```

## Step 5: Test Connection

From your main system, test the connection:
```bash
# Test health endpoint
curl -X GET http://your-server-b-ip:8001/health

# Should return: {"status":"healthy","timestamp":"...","active_tasks":0}
```

## Production Deployment Options

### Option 1: Direct Python Run
```bash
python server_b_api_setup.py
```

### Option 2: Systemd Service (Recommended)
Create `/etc/systemd/system/server-b-api.service`:
```ini
[Unit]
Description=Server B API for DRC Processing
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/server-b-api
Environment=PATH=/path/to/conda/envs/server-b-api/bin
ExecStart=/path/to/conda/envs/server-b-api/bin/python server_b_api_setup.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable server-b-api
sudo systemctl start server-b-api
sudo systemctl status server-b-api
```

### Option 3: Docker (Advanced)
If you prefer Docker, we can create a Dockerfile for containerized deployment.

## Customizing Processing Logic

The current `server_b_api_setup.py` includes a mock processing function. To integrate your real processing:

1. **Locate the `simulate_processing()` function** (line 58-131)
2. **Replace mock logic** with your actual DRC processing
3. **Update file generation** to create your real output files
4. **Modify processing time** (currently 5 seconds simulation)

## Monitoring and Logs

- API access logs: Check console output or redirect to log files
- Task status: Available via `/api/v1/tasks` endpoint
- Health monitoring: Use `/health` endpoint
- Active tasks: Tracked in memory (consider database for production)

## Security Considerations

1. **API Key Security**: Store securely, never commit to version control
2. **Network Security**: Consider VPN or secure network between servers
3. **File Permissions**: Ensure upload/results directories have appropriate permissions
4. **HTTPS**: Consider adding SSL/TLS for production
5. **Rate Limiting**: Add if needed for production workloads

## Troubleshooting

### Common Issues:
- **Port conflicts**: Change `SERVER_B_PORT` if 8001 is occupied
- **Permission errors**: Check file/directory permissions for upload/results directories
- **Network connectivity**: Ensure firewall allows connections on your chosen port
- **Authentication failures**: Verify API keys match between main system and Server B

### Debug Mode:
Add `reload=True` in `uvicorn.run()` for development, but remove for production.