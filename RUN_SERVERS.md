# How to Run Both Servers

## ✅ Backend is Running!
The backend server is currently running on **http://127.0.0.1:8000**

You can verify it's working by visiting:
- API: http://127.0.0.1:8000
- API Docs: http://127.0.0.1:8000/docs

## Starting the Frontend

### Option 1: Using Command Prompt (Recommended)
Open a **new Command Prompt** (not PowerShell) and run:
```cmd
cd E:\herbalplant2\frontend
npm start
```

### Option 2: Using the Batch File
Double-click `start_servers.bat` in the project root, or run:
```cmd
start_servers.bat
```

### Option 3: Manual Start
1. Open a new terminal/command prompt
2. Navigate to the frontend directory:
   ```cmd
   cd E:\herbalplant2\frontend
   ```
3. Start the React app:
   ```cmd
   npm start
   ```

The frontend will automatically open in your browser at **http://localhost:3000**

## Current Status

✅ **Backend**: Running on port 8000
⏳ **Frontend**: Starting on port 3000

## Troubleshooting

### If frontend doesn't start:
1. Make sure you're using **Command Prompt** (cmd.exe) not PowerShell
2. Check if port 3000 is already in use:
   ```cmd
   netstat -ano | findstr :3000
   ```
3. If node_modules is missing, install dependencies:
   ```cmd
   cd frontend
   npm install
   ```

### If you see PowerShell execution policy errors:
- Use Command Prompt (cmd.exe) instead of PowerShell
- Or run: `start_servers.bat` which uses cmd.exe

## Stopping the Servers

- **Backend**: Press `Ctrl+C` in the backend terminal window
- **Frontend**: Press `Ctrl+C` in the frontend terminal window

