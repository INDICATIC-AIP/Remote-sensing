// ─────────────────────────────────────────────────────────────
//  DEPENDENCIAS PRINCIPALES
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
//  FUNCIÓN DE LOGGING OPTIMIZADA
// ─────────────────────────────────────────────────────────────

/**
 * Función única para logging - inteligente según parámetros
 * @param {string} messageOrSection - Mensaje o sección
 * @param {string} [messageOrLevel] - Si hay sección: mensaje. Si no hay sección: level
 * @param {string} [levelOrFile] - Si hay sección: level. Si no hay sección: file
 * @param {string} [file] - Archivo (solo si hay sección)
 */
function logCustom(messageOrSection, messageOrLevel, levelOrFile, file) {
    const logScript = path.join(__dirname, 'scripts', 'utils', 'log.py');

    let section = null;
    let finalMessage = null;
    let level = 'INFO';
    let logFile = 'logs/iss/general.log';

    // Detectar si es sección + mensaje o solo mensaje
    if (messageOrLevel && !['INFO', 'WARNING', 'ERROR'].includes(messageOrLevel) && !messageOrLevel.includes('.log')) {
        // Caso: logCustom('Sección', 'Mensaje', 'INFO', 'file.log')
        section = messageOrSection;
        finalMessage = messageOrLevel;
        level = levelOrFile || 'INFO';
        logFile = file || 'logs/iss/general.log';
    } else {
        // Caso: logCustom('Mensaje', 'INFO', 'file.log') o logCustom('Mensaje')
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
            console.error(`[ERROR] Log falló - código: ${code}`);
            if (errorOutput) {
                console.error(`   Error: ${errorOutput.trim()}`);
            }
        }
    });

    child.on('error', (error) => {
        console.error(`[ERROR] Error ejecutando log_custom: ${error.message}`);
    });
}

// ─────────────────────────────────────────────────────────────
//  FUNCIONES DE VENTANAS
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

    nasaWindow.loadFile(path.join(__dirname, 'scripts', 'periodica', 'periodica.html'));
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
//  INICIALIZACIÓN DE BASE DE DATOS
// ─────────────────────────────────────────────────────────────

function initializeDatabase() {
    db = new sqlite3.Database(dbPath, sqlite3.OPEN_READWRITE, (err) => {
        if (err) {
            logCustom('Error Base de Datos', `Error conectando: ${err.message}`, 'ERROR');
        } else {
            logCustom('Conexión a base de datos establecida', 'INFO');
        }
    });
}

// ─────────────────────────────────────────────────────────────
// HANDLERS IPC
// ─────────────────────────────────────────────────────────────

function setupIpcHandlers() {
    // Handler para log_custom desde renderer
    ipcMain.on('log_custom', (event, args) => {
        const { section, message, level, file } = args;
        logCustom(section, message, level, file);
    });

    // Verificación de NASA ID en base de datos
    ipcMain.handle('verificar-nasa-id', async (_, nasaId) => {
        return new Promise((resolve) => {
            db.get("SELECT COUNT(*) AS count FROM Image WHERE nasa_id = ?", [String(nasaId)], (err, row) => {
                if (err) {
                    logCustom('Error Base de Datos', `Error consultando NASA_ID ${nasaId}: ${err.message}`, 'ERROR');
                    resolve(false);
                } else {
                    const exists = row && row.count > 0;
                    resolve(exists);
                }
            });
        });
    });

    // Gestión de tareas programadas
    ipcMain.handle("eliminarTareaWindows", async (_, taskName) => {
        logCustom('Gestión de Tareas', `Eliminando tarea: ${taskName}`);

        const result = spawnSync("/mnt/c/Windows/System32/schtasks.exe", [
            "/Delete", "/TN", taskName, "/F"
        ], { encoding: "utf-8" });

        if (result.status === 0 || result.status === 1) {
            logCustom(`Tarea eliminada correctamente: ${taskName}`);
            return { message: "Tarea eliminada correctamente." };
        } else {
            logCustom('Error Eliminación', `Error eliminando ${taskName}: ${result.stderr}`, 'ERROR');
            throw new Error(result.stderr || "Error al eliminar tarea");
        }
    });

    ipcMain.handle("crearTareaPeriodica", async (_, args) => {
        const { taskId, jsonPath, hora, frecuencia, intervalo } = args;

        logCustom('Creación Tarea NASA', `Creando tarea: ${taskId} - ${frecuencia} a las ${hora}`, 'INFO');

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
            logCustom(`Tarea NASA programada: ${taskId}`, 'INFO');
            return { message: "Tarea programada con éxito" };
        } else {
            logCustom('Error Tarea NASA', `Error creando tarea: ${result.stderr}`, 'ERROR');
            throw new Error(result.stderr || "No se pudo crear la tarea");
        }
    });

    ipcMain.handle("crearTareaNOAA", async (_, args) => {
        const { taskId, hora, frecuencia, intervalo } = args;

        logCustom('Creación Tarea NOAA', `Creando tarea NOAA: ${taskId} - ${frecuencia} a las ${hora}`, 'INFO');

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
            logCustom(`Tarea NOAA programada: ${taskId}`, 'INFO');
            return { message: "Tarea NOAA programada con éxito" };
        } else {
            logCustom('Error Tarea NOAA', `Error creando tarea NOAA: ${result.stderr}`, 'ERROR');
            throw new Error(result.stderr || "No se pudo crear la tarea NOAA");
        }
    });

    //  HANDLER CORREGIDO: descargarDirecto en main.js
    ipcMain.handle('descargarDirecto', async () => {
        return new Promise((resolve, reject) => {
            logCustom('Inicio Descarga', 'Iniciando descarga directa desde Electron', 'INFO');

            const scriptPath = path.join(__dirname, 'scripts', 'backend', 'run_batch_processor.py');
            const jsonFile = path.join(__dirname, 'scripts', 'metadatos_periodicos.json');
            const process = spawn('python3', [scriptPath, jsonFile]);
            const mainWindow = BrowserWindow.getAllWindows()[0];

            let stderrData = "";
            let lastProgress = 0;
            let processStarted = false;

            //  TIMEOUT DE SEGURIDAD PARA EVITAR PROCESOS COLGADOS
            const timeoutId = setTimeout(() => {
                logCustom('Timeout Descarga', 'Proceso de descarga excedió tiempo límite', 'WARNING');
                process.kill('SIGTERM');
                reject(new Error('Proceso de descarga excedió tiempo límite (timeout)'));
            }, 3 * 60 * 60 * 1000);
            process.stdout.on('data', (data) => {
                const lines = data.toString().split('\n');
                lines.forEach(line => {
                    line = line.trim();

                    //  DETECTAR DIFERENTES TIPOS DE PROGRESO
                    if (line.startsWith('PROGRESS:')) {
                        const progressValue = parseInt(line.replace('PROGRESS:', '').trim(), 10);

                        if (mainWindow && !isNaN(progressValue) && progressValue !== lastProgress) {
                            // Validar rango de progreso
                            if (progressValue >= 0 && progressValue <= 100) {
                                processStarted = true;

                                // Log solo en hitos importantes
                                if (progressValue % 10 === 0 || progressValue === 1 || progressValue === 99) {
                                    logCustom(`Progreso descarga: ${progressValue}%`, 'INFO');
                                }

                                // Enviar progreso a la UI
                                mainWindow.webContents.send('progreso-descarga', progressValue);
                                lastProgress = progressValue;
                            }
                        }
                    }

                    // Detectar errores en stdout
                    else if (line.includes('[ERROR]')) {
                        console.error(line);
                        stderrData += line + '\n';
                    }
                    // Otros mensajes informativos - ya vienen formateados desde Python
                    else if (line.trim()) {
                        console.log(line);
                    }
                });
            });

            process.stderr.on('data', (data) => {
                const error = data.toString();
                
                // Solo los mensajes con [ERROR] son errores reales
                if (error.includes('[ERROR]')) {
                    stderrData += error;
                    console.error(error.trim());
                } else if (error.trim()) {
                    // Otros mensajes en stderr son warnings o info
                    console.log(error.trim());
                }
            });

            process.on('close', (code) => {
                clearTimeout(timeoutId);

                if (code === 0) {
                    logCustom('Descarga Completada', 'Descarga directa completada exitosamente', 'INFO');

                    // ENVIAR SEÑAL DE COMPLETADO SOLO SI EL PROCESO FUE EXITOSO
                    if (mainWindow) {
                        mainWindow.webContents.send('descarga-completa');
                    }

                    resolve({
                        message: 'Descarga directa finalizada correctamente.',
                        processStarted: processStarted,
                        lastProgress: lastProgress
                    });
                } else {
                    logCustom('Error Descarga', `Descarga falló con código: ${code}`, 'ERROR');

                    // DETERMINAR TIPO DE ERROR
                    let errorMessage = `Fallo en ejecución del script. Código: ${code}`;

                    if (stderrData.includes('Permission denied')) {
                        errorMessage = 'Error de permisos. Verifica que tienes acceso a las carpetas necesarias.';
                    } else if (stderrData.includes('No module named')) {
                        errorMessage = 'Error de dependencias Python. Verifica que estén instaladas todas las librerías.';
                    } else if (stderrData.includes('Connection')) {
                        errorMessage = 'Error de conexión. Verifica tu conexión a internet.';
                    } else if (stderrData.trim()) {
                        errorMessage += `\n\nDetalles: ${stderrData.slice(-300)}`; // Solo últimos 300 chars
                    }

                    reject(new Error(errorMessage));
                }
            });

            process.on('error', (error) => {
                clearTimeout(timeoutId);
                logCustom('Error Proceso', `Error en proceso de descarga: ${error.message}`, 'ERROR');

                let userMessage = `Error ejecutando el proceso: ${error.message}`;

                if (error.code === 'ENOENT') {
                    userMessage = 'No se encontró Python3. Verifica que esté instalado y en el PATH.';
                } else if (error.code === 'EACCES') {
                    userMessage = 'Error de permisos ejecutando Python3.';
                }

                reject(new Error(userMessage));
            });
        });
    });

    // Handlers NOAA
    ipcMain.handle('generate-tiles', () => {
        return new Promise((resolve, reject) => {
            logCustom('Generación Mosaicos', 'Generando mosaicos NOAA', 'INFO');

            exec('python3 scripts/noaa/noaa_commands.py generate_tiles', (error, stdout, stderr) => {
                if (error) {
                    logCustom('Error Mosaicos', `Error generando mosaicos: ${stderr}`, 'ERROR');
                    reject(stderr);
                } else {
                    logCustom(`Mosaicos generados exitosamente`, 'INFO');
                    resolve(stdout);
                }
            });
        });
    });

    ipcMain.handle("listar-candidatos-export", async () => {
        return new Promise((resolve, reject) => {
            logCustom('Listar Candidatos', 'Listando candidatos para exportación', 'INFO');

            const scriptPath = path.join(__dirname, "scripts/noaa/noaa_commands.py");
            const py = spawn("python3", [scriptPath, "listar-candidatos-export"]);
            let out = "", err = "";

            py.stdout.on("data", data => out += data.toString());

            py.stderr.on("data", data => {
                const message = data.toString();
                
                // Solo capturar errores reales
                if (message.includes('[ERROR]')) {
                    err += message;
                }
                // Otros mensajes son informativos, ignorar
            });

            py.on("close", code => {
                if (code === 0) {
                    try {
                        const parsed = JSON.parse(out);
                        logCustom(`Candidatos listados: ${parsed.length || 0} elementos`, 'INFO');
                        resolve(parsed);
                    } catch (e) {
                        logCustom('Error JSON', `Error parseando JSON: ${e.message}`, 'ERROR');
                        reject("Error parseando salida de Python.");
                    }
                } else {
                    logCustom('Error Python', `Error ejecutando Python: ${err}`, 'ERROR');
                    reject("Python falló al listar candidatos.");
                }
            });
        });
    });

    // ipcMain.handle("export-all", async () => {
    //     return new Promise((resolve, reject) => {
    //         logCustom('Exportación NOAA', 'Iniciando exportación completa NOAA', 'INFO');

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
    //                 logCustom('Error Exportación', `Error exportación NOAA: ${error}`, 'ERROR');
    //             }
    //         });

    //         python.on("close", (code) => {
    //             if (code === 0) {
    //                 logCustom(`Exportación NOAA completada exitosamente`, 'INFO');
    //                 resolve("Exportación completada");
    //             } else {
    //                 logCustom('Error Exportación', `Exportación NOAA falló con código: ${code}`, 'ERROR');
    //                 reject(new Error(`Python terminó con código ${code}`));
    //             }
    //         });
    //     });
    // });
    ipcMain.handle("export-all", async () => {
        return new Promise((resolve, reject) => {
            logCustom('Exportación NOAA', 'Iniciando exportación completa NOAA', 'INFO');

            const python = spawn("python3", ["scripts/noaa/noaa_commands.py", "export_all"]);
            let hasError = false;
            let errorBuffer = "";

            python.stdout.on("data", (data) => {
                const lines = data.toString().split('\n');

                lines.forEach(line => {
                    line = line.trim();
                    if (!line) return;

                    // CAPTURAR PROGRESO DE GEE
                    if (line.includes("ProgresoLanzado:") || line.includes("ProgresoReal:")) {
                        if (noaaWindow) {
                            noaaWindow.webContents.send("export-progress", line);
                        }
                    }

                    // CAPTURAR PROGRESO DE RCLONE
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
                
                // Solo los [ERROR] son errores reales
                if (message.includes('[ERROR]')) {
                    hasError = true;
                    errorBuffer += message + "\n";
                    console.error(message);
                }
                // Mensajes de progreso
                else if (message.includes("ProgresoLanzado:") || message.includes("ProgresoReal:")) {
                    if (noaaWindow) {
                        noaaWindow.webContents.send("export-progress", message);
                    }
                }
                // Otros mensajes informativos - ya vienen formateados
                else if (message) {
                    console.log(message);
                }
            });

            python.on("close", (code) => {
                if (code === 0 && !hasError) {
                    logCustom(`Exportación NOAA completada exitosamente`, 'INFO');
                    resolve("Exportación completada");
                } else if (hasError) {
                    logCustom('Error Exportación NOAA', `Falló: ${errorBuffer}`, 'ERROR');
                    reject(new Error(`Error en exportación: ${errorBuffer}`));
                } else {
                    logCustom('Error Exportación NOAA', `Falló con código: ${code}`, 'ERROR');
                    reject(new Error(`Python terminó con código ${code}`));
                }
            });
        });
    });
    ipcMain.handle('get-metadata', (_, year) => {
        return new Promise((resolve, reject) => {
            logCustom('Metadatos NOAA', `Obteniendo metadatos para año: ${year}`, 'INFO');

            exec(`python3 scripts/noaa/noaa_commands.py get_metadata ${year}`, (error, stdout, stderr) => {
                if (error) {
                    logCustom('Error Metadatos', `Error obteniendo metadatos para ${year}: ${stderr}`, 'ERROR');
                    reject(stderr);
                } else {
                    logCustom(`Metadatos obtenidos para ${year}`, 'INFO');
                    resolve(stdout);
                }
            });
        });
    });

    ipcMain.handle('listar-imagenes-drive', async () => {
        logCustom('Google Drive', 'Listando imágenes desde Google Drive', 'INFO');

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
            logCustom(`Encontrados ${archivos.length} archivos en Google Drive`, 'INFO');

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
                        logCustom(`Error obteniendo thumbnail para ${file.name}: ${err.message}`, 'WARNING');
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
                        logCustom(`Error obteniendo metadatos para ${year}: ${err.message}`, 'WARNING');
                        file.metadata = null;
                        file.year = year;
                    }
                } else {
                    file.metadata = null;
                }
            }

            logCustom(`Imágenes de Google Drive listadas exitosamente`, 'INFO');
            return archivos;

        } catch (err) {
            logCustom('Error Drive', `Error accediendo a Google Drive: ${err.message}`, 'ERROR');
            if (err.code === 401 || err.code === 403) {
                return { error: 'NO_AUTH', message: 'Necesitas volver a autenticarte o revisar permisos.' };
            }
            return { error: 'UNKNOWN', message: err.message };
        }
    });
}

// ─────────────────────────────────────────────────────────────
// INICIO DE LA APP
// ─────────────────────────────────────────────────────────────

app.whenReady().then(() => {
    logCustom('Inicio de Aplicación', 'Aplicación Electron iniciada');

    // Inicializar base de datos y handlers
    initializeDatabase();
    setupIpcHandlers();

    // Crear ventana según argumentos
    if (process.argv.includes("--nasa")) {
        logCustom('Creando ventana periódica NASA');
        createPeriodicWindow();
    } else if (process.argv.includes("--noaa")) {
        logCustom('Creando ventana NOAA');
        createNOAA();
    } else if (process.argv.includes("--nocturno")) {
        logCustom('Creando ventana GIRS');
        createNocturno();
    } else {
        logCustom('Creando ventana principal');
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
    logCustom('App Cerrada', 'Todas las ventanas cerradas', 'INFO');
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createMainWindow();
    }
});