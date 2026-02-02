// ─────────────────────────────────────────────────────────────
//  MAIN DEPENDENCIES
// ─────────────────────────────────────────────────────────────
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const sqlite3 = require('sqlite3').verbose();
const { exec, spawn, spawnSync } = require("child_process");
const dbPath = path.join(__dirname, 'db/metadata.db');

let mainWindow;
let nasaWindow;
let noaaWindow;
let nocturnoWindow;
let db;

// ─────────────────────────────────────────────────────────────
//  OPTIMIZED LOGGING
// ─────────────────────────────────────────────────────────────

/**
 * Single logging helper that adapts to provided parameters
 * @param {string} messageOrSection - Message or section
 * @param {string} [messageOrLevel] - If section is provided: message. Otherwise: level
 * @param {string} [levelOrFile] - If section is provided: level. Otherwise: file
 * @param {string} [file] - Log file (only when section is provided)
 */
function logCustom(messageOrSection, messageOrLevel, levelOrFile, file) {
    const logScript = path.join(__dirname, 'scripts', 'utils', 'log.py');

    let section = null;
    let finalMessage = null;
    let level = 'INFO';
    let logFile = 'logs/iss/general.log';

    // Detect whether it is section + message or only message
    if (messageOrLevel && !['INFO', 'WARNING', 'ERROR'].includes(messageOrLevel) && !messageOrLevel.includes('.log')) {
        // Case: logCustom('Section', 'Message', 'INFO', 'file.log')
        section = messageOrSection;
        finalMessage = messageOrLevel;
        level = levelOrFile || 'INFO';
        logFile = file || 'logs/iss/general.log';
    } else {
        // Case: logCustom('Message', 'INFO', 'file.log') or logCustom('Message')
        section = null;
        finalMessage = messageOrSection;
        level = (['INFO', 'WARNING', 'ERROR'].includes(messageOrLevel)) ? messageOrLevel : 'INFO';
        logFile = (levelOrFile && levelOrFile.includes('.log')) ? levelOrFile : 'logs/iss/general.log';
    }

    const child = spawn('python3', [
        logScript, 'log_custom',
        section || 'None',
        finalMessage || 'None',
        level,
        logFile
    ], {
        stdio: ['pipe', 'inherit', 'pipe'],
        cwd: __dirname
    });

    let errorOutput = '';

    child.stderr.on('data', (data) => {
        errorOutput += data.toString();
    });

    child.on('close', (code) => {
        if (code !== 0) {
            console.error(`[ERROR] Log failed - code: ${code}`);
            if (errorOutput) {
                console.error(`   Error: ${errorOutput.trim()}`);
            }
        }
    });

    child.on('error', (error) => {
        console.error(`[ERROR] Error executing log_custom: ${error.message}`);
    });
}

// ─────────────────────────────────────────────────────────────
//  WINDOW FUNCTIONS
// ─────────────────────────────────────────────────────────────

function createMainWindow() {
    const { screen } = require('electron');
    const { width, height } = screen.getPrimaryDisplay().workAreaSize;

    mainWindow = new BrowserWindow({
        width: width,
        height: height,
        webPreferences: {
            contextIsolation: false,
            nodeIntegration: true,
            preload: path.join(__dirname, 'scripts', 'automatica', 'ui', 'renderer.js')
        }
    });

    mainWindow.loadFile(path.join(__dirname, 'scripts', 'automatica', 'ui', 'index.html'));
    mainWindow.on("closed", () => { mainWindow = null; });
}

function createPeriodicWindow() {
    nasaWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
        }
    });

    nasaWindow.loadFile(path.join(__dirname, 'scripts', 'periodic_tasks', 'periodica.html'));
    nasaWindow.on("closed", () => { nasaWindow = null; });
}

function createNOAA() {
    noaaWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
        }
    });

    noaaWindow.loadFile(path.join(__dirname, 'scripts', 'noaa', 'ui', 'noaa.html'));
    noaaWindow.on("closed", () => { noaaWindow = null; });
}

function createNocturno() {
    nocturnoWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
        }
    });

    nocturnoWindow.loadFile(path.join(__dirname, 'scripts', 'giras', 'nocturno.html'));
    nocturnoWindow.on("closed", () => { nocturnoWindow = null; });
}

// ─────────────────────────────────────────────────────────────
//  DATABASE INITIALIZATION
// ─────────────────────────────────────────────────────────────

function initializeDatabase() {
    db = new sqlite3.Database(dbPath, sqlite3.OPEN_READWRITE, (err) => {
        if (err) {
            logCustom('Database Error', `Connection error: ${err.message}`, 'ERROR');
        } else {
            logCustom('Database connection established', 'INFO');
        }
    });
}

// ─────────────────────────────────────────────────────────────
// IPC HANDLERS
// ─────────────────────────────────────────────────────────────

function setupIpcHandlers() {
    // Handler for log_custom from renderer
    ipcMain.on('log_custom', (event, args) => {
        const { section, message, level, file } = args;
        logCustom(section, message, level, file);
    });

    // NASA ID verification in database
    ipcMain.handle('verificar-nasa-id', async (_, nasaId) => {
        return new Promise((resolve) => {
            db.get("SELECT COUNT(*) AS count FROM Image WHERE nasa_id = ?", [String(nasaId)], (err, row) => {
                if (err) {
                    logCustom('Database Error', `Error querying NASA_ID ${nasaId}: ${err.message}`, 'ERROR');
                    resolve(false);
                } else {
                    const exists = row && row.count > 0;
                    resolve(exists);
                }
            });
        });
    });

    // Scheduled task management
    ipcMain.handle("eliminarTareaWindows", async (_, taskName) => {
        logCustom('Task Management', `Deleting task: ${taskName}`);

        const result = spawnSync("/mnt/c/Windows/System32/schtasks.exe", [
            "/Delete", "/TN", taskName, "/F"
        ], { encoding: "utf-8" });

        if (result.status === 0 || result.status === 1) {
            logCustom(`Task deleted successfully: ${taskName}`);
            return { message: "Task deleted successfully." };
        } else {
            logCustom('Deletion Error', `Error deleting ${taskName}: ${result.stderr}`, 'ERROR');
            throw new Error(result.stderr || "Error deleting task");
        }
    });

    ipcMain.handle("crearTareaPeriodica", async (_, args) => {
        const { taskId, jsonPath, hora, frecuencia, intervalo } = args;

        logCustom('NASA Task Creation', `Creating task: ${taskId} - ${frecuencia} at ${hora}`, 'INFO');

        const command = `cmd.exe /c start /min "" wsl -d Ubuntu-24.04 -- bash /home/jose/API-NASA/map/scripts/launch_periodic.sh ${taskId}`;
        const schedulerArgs = [
            "/mnt/c/Windows/System32/schtasks.exe",
            "/Create", "/TN", taskId, "/TR", command,
            "/SC", frecuencia, "/F"
        ];

        if (frecuencia === "ONCE" && hora) schedulerArgs.push("/ST", hora);
        else if (["MINUTE", "HOURLY"].includes(frecuencia)) {
            schedulerArgs.push("/MO", intervalo);
            if (hora) schedulerArgs.push("/ST", hora);
        }

        const result = spawnSync(schedulerArgs[0], schedulerArgs.slice(1), { encoding: "utf-8" });

        if (result.status === 0) {
            logCustom(`NASA task scheduled: ${taskId}`, 'INFO');
            return { message: "Task scheduled successfully" };
        } else {
            logCustom('NASA Task Error', `Error creating task: ${result.stderr}`, 'ERROR');
            throw new Error(result.stderr || "Could not create task");
        }
    });

    ipcMain.handle("crearTareaNOAA", async (_, args) => {
        const { taskId, hora, frecuencia, intervalo } = args;

        logCustom('NOAA Task Creation', `Creating NOAA task: ${taskId} - ${frecuencia} at ${hora}`, 'INFO');

        const command = `cmd.exe /c start /min "" wsl -d Ubuntu-24.04 -- bash /home/jose/API-NASA/map/scripts/launch_noaa.sh ${taskId}`;
        const schedulerArgs = [
            "/mnt/c/Windows/System32/schtasks.exe",
            "/Create", "/TN", taskId, "/TR", command,
            "/SC", frecuencia, "/F"
        ];

        if (frecuencia === "ONCE" && hora) schedulerArgs.push("/ST", hora);
        else if (["MINUTE", "HOURLY"].includes(frecuencia)) {
            schedulerArgs.push("/MO", intervalo);
            if (hora) schedulerArgs.push("/ST", hora);
        }

        const result = spawnSync(schedulerArgs[0], schedulerArgs.slice(1), { encoding: "utf-8" });

        if (result.status === 0) {
            logCustom(`NOAA task scheduled: ${taskId}`, 'INFO');
            return { message: "NOAA task scheduled successfully" };
        } else {
            logCustom('NOAA Task Error', `Error creating NOAA task: ${result.stderr}`, 'ERROR');
            throw new Error(result.stderr || "Unable to create NOAA task");
        }
    });

    // Handler: direct download from main.js
    ipcMain.handle('descargarDirecto', async () => {
        return new Promise((resolve, reject) => {
            logCustom('Download Start', 'Starting direct download from Electron', 'INFO');

            const scriptPath = path.join(__dirname, 'scripts', 'backend', 'run_batch_processor.py');
            const jsonFile = path.join(__dirname, 'scripts', 'periodic_metadata.json');
            const process = spawn('python3', [scriptPath, jsonFile]);
            const mainWindow = BrowserWindow.getAllWindows()[0];

            let stderrData = "";
            let lastProgress = 0;
            let processStarted = false;

            // Safety timeout to avoid hanging processes
            const timeoutId = setTimeout(() => {
                logCustom('Download Timeout', 'Download process exceeded time limit', 'WARNING');
                process.kill('SIGTERM');
                reject(new Error('Download process exceeded time limit (timeout)'));
            }, 3 * 60 * 60 * 1000);
            process.stdout.on('data', (data) => {
                const lines = data.toString().split('\n');
                lines.forEach(line => {
                    line = line.trim();

                    // Detect different progress types
                    if (line.startsWith('PROGRESS:')) {
                        const progressValue = parseInt(line.replace('PROGRESS:', '').trim(), 10);

                        if (mainWindow && !isNaN(progressValue) && progressValue !== lastProgress) {
                            // Validate progress range
                            if (progressValue >= 0 && progressValue <= 100) {
                                processStarted = true;

                                // Log only on meaningful milestones
                                if (progressValue % 10 === 0 || progressValue === 1 || progressValue === 99) {
                                    logCustom(`Download progress: ${progressValue}%`, 'INFO');
                                }

                                // Send progress to the UI
                                mainWindow.webContents.send('progreso-descarga', progressValue);
                                lastProgress = progressValue;
                            }
                        }
                    }

                    // Detect errors in stdout
                    else if (line.includes('[ERROR]')) {
                        console.error(line);
                        stderrData += line + '\n';
                    }
                    // Other informational messages already formatted in Python
                    else if (line.trim()) {
                        console.log(line);
                    }
                });
            });

            process.stderr.on('data', (data) => {
                const error = data.toString();
                
                // Only messages with [ERROR] are real errors
                if (error.includes('[ERROR]')) {
                    stderrData += error;
                    console.error(error.trim());
                } else if (error.trim()) {
                    // Other stderr messages are warnings or info
                    console.log(error.trim());
                }
            });

            process.on('close', (code) => {
                clearTimeout(timeoutId);

                if (code === 0) {
                    logCustom('Download Complete', 'Direct download finished successfully', 'INFO');

                    // Send completion signal only when the process was successful
                    if (mainWindow) {
                        mainWindow.webContents.send('descarga-completa');
                    }

                    resolve({
                        message: 'Direct download completed successfully.',
                        processStarted: processStarted,
                        lastProgress: lastProgress
                    });
                } else {
                    logCustom('Download Error', `Download failed with code: ${code}`, 'ERROR');

                    // Determine error type
                    let errorMessage = `Script execution failed. Code: ${code}`;

                    if (stderrData.includes('Permission denied')) {
                        errorMessage = 'Permission error. Verify you have access to the required folders.';
                    } else if (stderrData.includes('No module named')) {
                        errorMessage = 'Python dependency error. Ensure all libraries are installed.';
                    } else if (stderrData.includes('Connection')) {
                        errorMessage = 'Connection error. Check your internet connection.';
                    } else if (stderrData.trim()) {
                        errorMessage += `\n\nDetails: ${stderrData.slice(-300)}`; // last 300 chars only
                    }

                    reject(new Error(errorMessage));
                }
            });

            process.on('error', (error) => {
                clearTimeout(timeoutId);
                logCustom('Process Error', `Error in download process: ${error.message}`, 'ERROR');

                let userMessage = `Error running process: ${error.message}`;

                if (error.code === 'ENOENT') {
                    userMessage = 'Python3 not found. Verify it is installed and available in PATH.';
                } else if (error.code === 'EACCES') {
                    userMessage = 'Permission error running Python3.';
                }

                reject(new Error(userMessage));
            });
        });
    });

    // NOAA handlers
    ipcMain.handle('generate-tiles', () => {
        return new Promise((resolve, reject) => {
            logCustom('Tile Generation', 'Generating NOAA tiles', 'INFO');

            exec('python3 scripts/noaa/noaa_commands.py generate_tiles', (error, stdout, stderr) => {
                if (error) {
                    logCustom('Tile Error', `Error generating tiles: ${stderr}`, 'ERROR');
                    reject(stderr);
                } else {
                    logCustom('Tiles generated successfully', 'INFO');
                    resolve(stdout);
                }
            });
        });
    });

    ipcMain.handle("listar-candidatos-export", async () => {
        return new Promise((resolve, reject) => {
            logCustom('List Candidates', 'Listing candidates for export', 'INFO');

            const scriptPath = path.join(__dirname, "scripts/noaa/noaa_commands.py");
            const py = spawn("python3", [scriptPath, "listar-candidatos-export"]);
            let out = "", err = "";

            py.stdout.on("data", data => out += data.toString());

            py.stderr.on("data", data => {
                const message = data.toString();
                
                // Capture only real errors
                if (message.includes('[ERROR]')) {
                    err += message;
                }
                // Other messages are informational; ignore
            });

            py.on("close", code => {
                if (code === 0) {
                    try {
                        const parsed = JSON.parse(out);
                        logCustom(`Candidates listed: ${parsed.length || 0} items`, 'INFO');
                        resolve(parsed);
                    } catch (e) {
                        logCustom('JSON Error', `Error parsing JSON: ${e.message}`, 'ERROR');
                        reject("Error parsing Python output.");
                    }
                } else {
                    logCustom('Python Error', `Error running Python: ${err}`, 'ERROR');
                    reject("Python failed to list candidates.");
                }
            });
        });
    });

    // ipcMain.handle("export-all", async () => {
    //     return new Promise((resolve, reject) => {
    //         logCustom('NOAA Export', 'Starting full NOAA export', 'INFO');

    //         const python = spawn("python3", ["scripts/noaa/noaa_commands.py", "export_all"]);

    //         python.stdout.on("data", (data) => {
    //             const message = data.toString().trim();
    //             if (message && noaaWindow) {
    //                 noaaWindow.webContents.send("export-progress", message);
    //             }
    //         });

    //         python.stderr.on("data", (data) => {
    //             const error = data.toString().trim();
    //             if (error) {
    //                 logCustom('Export Error', `NOAA export error: ${error}`, 'ERROR');
    //             }
    //         });

    //         python.on("close", (code) => {
    //             if (code === 0) {
    //                 logCustom('NOAA export completed successfully', 'INFO');
    //                 resolve("Export completed");
    //             } else {
    //                 logCustom('Export Error', `NOAA export failed with code: ${code}`, 'ERROR');
    //                 reject(new Error(`Python ended with code ${code}`));
    //             }
    //         });
    //     });
    // });
    ipcMain.handle("export-all", async () => {
        return new Promise((resolve, reject) => {
            logCustom('NOAA Export', 'Starting full NOAA export', 'INFO');

            const python = spawn("python3", ["scripts/noaa/noaa_commands.py", "export_all"]);
            let hasError = false;
            let errorBuffer = "";

            python.stdout.on("data", (data) => {
                const lines = data.toString().split('\n');

                lines.forEach(line => {
                    line = line.trim();
                    if (!line) return;

                    // Capture GEE progress
                    if (line.includes("ProgresoLanzado:") || line.includes("ProgresoReal:")) {
                        if (noaaWindow) {
                            noaaWindow.webContents.send("export-progress", line);
                        }
                    }

                    // Capture RCLONE progress
                    else if (line.startsWith("PROGRESS:")) {
                        const progressValue = parseInt(line.replace("PROGRESS:", "").trim(), 10);
                        if (!isNaN(progressValue) && noaaWindow) {
                            noaaWindow.webContents.send("download-progress", progressValue);
                        }
                    }
                });
            });

            python.stderr.on("data", (data) => {
                const message = data.toString().trim();
                
                // Only [ERROR] messages are real errors
                if (message.includes('[ERROR]')) {
                    hasError = true;
                    errorBuffer += message + "\n";
                    console.error(message);
                }
                // Progress messages
                else if (message.includes("ProgresoLanzado:") || message.includes("ProgresoReal:")) {
                    if (noaaWindow) {
                        noaaWindow.webContents.send("export-progress", message);
                    }
                }
                // Other informational messages already formatted
                else if (message) {
                    console.log(message);
                }
            });

            python.on("close", (code) => {
                if (code === 0 && !hasError) {
                    logCustom('NOAA export completed successfully', 'INFO');
                    resolve("Export completed");
                } else if (hasError) {
                    logCustom('NOAA Export Error', `Failed: ${errorBuffer}`, 'ERROR');
                    reject(new Error(`Export error: ${errorBuffer}`));
                } else {
                    logCustom('NOAA Export Error', `Failed with code: ${code}`, 'ERROR');
                    reject(new Error(`Python ended with code ${code}`));
                }
            });
        });
    });
    ipcMain.handle('get-metadata', (_, year) => {
        return new Promise((resolve, reject) => {
            logCustom('NOAA Metadata', `Fetching metadata for year: ${year}`, 'INFO');

            exec(`python3 scripts/noaa/noaa_commands.py get_metadata ${year}`, (error, stdout, stderr) => {
                if (error) {
                    logCustom('Metadata Error', `Error fetching metadata for ${year}: ${stderr}`, 'ERROR');
                    reject(stderr);
                } else {
                    logCustom(`Metadata fetched for ${year}`, 'INFO');
                    resolve(stdout);
                }
            });
        });
    });

    ipcMain.handle('listar-imagenes-drive', async () => {
        logCustom('Google Drive', 'Listing images from Google Drive', 'INFO');

        const { google } = require('googleapis');
        const { execSync } = require('child_process');

        const auth = new google.auth.GoogleAuth({
            keyFile: 'scripts/noaa/credentials.json',
            scopes: ['https://www.googleapis.com/auth/drive.readonly'],
        });

        const drive = google.drive({ version: 'v3', auth: await auth.getClient() });
        const folderId = '1jrc17OB2Yy3PjFgU8j54Kbh6-WTec5h8';

        try {
            const res = await drive.files.list({
                q: `'${folderId}' in parents and mimeType contains 'image/'`,
                fields: "files(id, name, createdTime, mimeType, thumbnailLink, webContentLink, iconLink, hasThumbnail)",
                orderBy: "createdTime desc"
            });

            const archivos = res.data.files;
            logCustom(`Found ${archivos.length} files in Google Drive`, 'INFO');

            for (const file of archivos) {
                if (!file.thumbnailLink && file.hasThumbnail) {
                    try {
                        const fileMetadata = await drive.files.get({
                            fileId: file.id,
                            fields: 'thumbnailLink',
                            supportsAllDrives: true
                        });
                        file.thumbnailLink = fileMetadata.data.thumbnailLink || file.iconLink || null;
                    } catch (err) {
                        logCustom(`Error fetching thumbnail for ${file.name}: ${err.message}`, 'WARNING');
                    }
                }

                const match = file.name.match(/\d{4}/);
                if (match) {
                    const year = match[0];
                    try {
                        const output = execSync(`python3 scripts/noaa/noaa_commands.py get_metadata ${year}`);
                        const lines = output.toString().split("\n");
                        const jsonStart = lines.findIndex(line => line.trim().startsWith("{"));
                        const jsonText = lines.slice(jsonStart).join("\n");
                        file.metadata = JSON.parse(jsonText);
                        file.year = year;
                    } catch (err) {
                        logCustom(`Error fetching metadata for ${year}: ${err.message}`, 'WARNING');
                        file.metadata = null;
                        file.year = year;
                    }
                } else {
                    file.metadata = null;
                }
            }

            logCustom('Google Drive images listed successfully', 'INFO');
            return archivos;

        } catch (err) {
            logCustom('Drive Error', `Error accessing Google Drive: ${err.message}`, 'ERROR');
            if (err.code === 401 || err.code === 403) {
                return { error: 'NO_AUTH', message: 'You need to re-authenticate or check permissions.' };
            }
            return { error: 'UNKNOWN', message: err.message };
        }
    });
}

// ─────────────────────────────────────────────────────────────
// APP STARTUP
// ─────────────────────────────────────────────────────────────

app.whenReady().then(() => {
    logCustom('App Start', 'Electron application started');

    // Initialize database and handlers
    initializeDatabase();
    setupIpcHandlers();

    // Create window based on args
    if (process.argv.includes("--nasa")) {
        logCustom('Creating NASA periodic window');
        createPeriodicWindow();
    } else if (process.argv.includes("--noaa")) {
        logCustom('Creating NOAA window');
        createNOAA();
    } else if (process.argv.includes("--nocturno")) {
        logCustom('Creating GIRS window');
        createNocturno();
    } else {
        logCustom('Creating main window');
        createMainWindow();
    }
});


ipcMain.on('pid-message', function(event, arg) {
  console.log('Main:', arg);
  pids.push(arg);
});

// app.on('before-quit', () => {
//     pids.forEach(function(pid){
//         ps.kill(pid, function(err){
//             if(err){
//                 throw new Error(err)
//             }else {
//             console.log( 'Process %s has been killed!', pid );
//             }
//          });
//   });
// });

app.on('window-all-closed', () => {
    logCustom('App Closed', 'All windows closed', 'INFO');
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createMainWindow();
    }
});