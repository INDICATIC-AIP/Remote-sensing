const { ipcRenderer } = require("electron");
const fs = require("fs");
const path = require("path");

let pendientesExportar = [];
let filtradosDataset = [];
let pagina = 1;
const porPagina = 10;

const tileFilePath = path.join(__dirname, "tiles_panama.json");
let map;
let currentLayer = null;
let tileData = {};
let sidebarVisible = true;
let cachedDriveImages = null;
document.addEventListener("DOMContentLoaded", function () {
  try {
    // Inicializar mapa
    map = L.map('map', {
      zoomControl: false,
      attributionControl: false
    }).setView([8.5, -80.5], 7);

    L.control.zoom({ position: 'topright' }).addTo(map);
    L.control.attribution({ position: 'bottomright', prefix: false }).addTo(map);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap & CARTO',
      subdomains: 'abcd',
      maxZoom: 19
    }).addTo(map);

    loadTileData();

    // Event listeners con comprobaciones defensivas
    const fechaEl = document.getElementById("fecha");
    if (fechaEl) {
      fechaEl.addEventListener("change", cambiarCapa);
    }

    const opacidadEl = document.getElementById("opacidad");
    if (opacidadEl) {
      opacidadEl.addEventListener("input", cambiarCapa);
    }

    const toggleSidebarEl = document.getElementById("toggle-sidebar");
    if (toggleSidebarEl) {
      toggleSidebarEl.addEventListener("click", toggleSidebar);
    }

    const filtroAñoEl = document.getElementById("filtro-año");
    if (filtroAñoEl) {
      filtroAñoEl.addEventListener("input", filtrarImagenes);
    }

    const filtroTipoEl = document.getElementById("filtro-tipo");
    if (filtroTipoEl) {
      filtroTipoEl.addEventListener("change", filtrarImagenes);
    }

    const autoCheckEl = document.getElementById("auto-check");
    if (autoCheckEl) {
      autoCheckEl.addEventListener("change", function (e) {
        const scheduleControls = document.querySelector(".schedule-controls");
        if (scheduleControls) {
          scheduleControls.style.display = e.target.checked ? "flex" : "none";
        }
      });
    }

    const prevPagEl = document.getElementById("prev-pag");
    if (prevPagEl) {
      prevPagEl.addEventListener("click", () => {
        if (pagina > 1) {
          pagina--;
          renderizarPendientes();
        }
      });
    }

    const nextPagEl = document.getElementById("next-pag");
    if (nextPagEl) {
      nextPagEl.addEventListener("click", () => {
        if ((pagina * porPagina) < filtradosDataset.length) {
          pagina++;
          renderizarPendientes();
        }
      });
    }

    // Event listeners del mapa
    if (map) {
      map.on('mousemove', updateCoordinateInfo);
    }

    // Escuchar mensajes de verificación
    ipcRenderer.on("noaa-check-log", (event, message) => {
      showStatus(message);
    });

    console.log("✅ NOAA Renderer inicializado correctamente");

  } catch (error) {
    console.error("❌ Error inicializando NOAA Renderer:", error);
    showStatus("Error inicializando la aplicación: " + error.message, "error");
  }
});

function confirmarExportar() {
  cerrarModalExportar();
  exportarImagenes();
}


async function abrirModalTareas() {
  document.getElementById("modal-tareas").style.display = "flex";
  await cargarTareasNoaa(); // carga al abrir
}

function cerrarModalTareas() {
  document.getElementById("modal-tareas").style.display = "none";
}

async function cargarTareasNoaa() {
  try {
    const ruta = path.join(__dirname, "tasks_noaa.json");

    let tareas = [];
    if (fs.existsSync(ruta)) {
      const contenido = fs.readFileSync(ruta, "utf-8");
      tareas = contenido ? JSON.parse(contenido) : [];
    }

    const tbody = document.querySelector("#tabla-tareas tbody");
    tbody.innerHTML = "";

    tareas.forEach(t => {
      const fila = document.createElement("tr");
      fila.innerHTML = `
        <td>${t.id}</td>
        <td>${t.frecuencia}</td>
        <td>${t.hora || "—"}</td>
        <td>${t.intervalo || "1"}</td>
        <td>
          <button onclick="rellenarFormulario('${t.id}', '${t.frecuencia}', '${t.hora}', '${t.intervalo}')">✏️</button>
          <button onclick="eliminarTareaNoaa('${t.id}')">🗑</button>
        </td>
      `;
      tbody.appendChild(fila);
    });
  } catch (err) {
    console.error("Error cargando tareas NOAA:", err);
  }
}


function rellenarFormulario(taskId, frecuencia, hora, intervalo) {
  document.getElementById("modal-hora").value = hora || "";
  document.getElementById("modal-frecuencia").value = frecuencia;
  document.getElementById("modal-intervalo").value = intervalo;
}

async function guardarTareaNoaa() {

  const frecuencia = document.getElementById("modal-frecuencia").value;
  const intervalo = document.getElementById("modal-intervalo").value;
  const hora = document.getElementById("modal-hora").value;
  const taskId = `noaa_task_${Date.now().toString(36)}`;

  const tarea = {
    id: taskId,
    hora,
    frecuencia,
    intervalo,
    max_items: 5 // puedes modificar esto o hacerlo dinámico más adelante
  };

  const ruta = path.join(__dirname, "tasks_noaa.json");

  let tareas = [];
  if (fs.existsSync(ruta)) {
    const contenido = fs.readFileSync(ruta, "utf-8");
    tareas = contenido ? JSON.parse(contenido) : [];
  }

  tareas.push(tarea);
  fs.writeFileSync(ruta, JSON.stringify(tareas, null, 2), "utf-8");

  // Crear tarea en el programador de Windows
  try {
    const payload = {
      taskId: tarea.id,
      hora: tarea.hora,
      frecuencia: tarea.frecuencia,
      intervalo: tarea.intervalo
    };
    const result = await ipcRenderer.invoke("crearTareaNOAA", payload);
    showStatus(result.message, "success");
    cerrarModalTareas();
  } catch (err) {
    showStatus("Error creando tarea: " + err.message, "error");
  }
}

async function eliminarTareaNoaa(taskId) {
  try {
    await ipcRenderer.invoke("eliminarTareaWindows", taskId);

    const ruta = path.join(__dirname, "tasks_noaa.json");
    let tareas = [];

    if (fs.existsSync(ruta)) {
      const contenido = fs.readFileSync(ruta, "utf-8");
      tareas = contenido ? JSON.parse(contenido) : [];
    }

    const nuevas = tareas.filter(t => t.id !== taskId);
    fs.writeFileSync(ruta, JSON.stringify(nuevas, null, 2), "utf-8");

    showStatus("Tarea eliminada correctamente", "success");
    await cargarTareasNoaa();
  } catch (err) {
    showStatus("Error eliminando tarea: " + err.message, "error");
  }
}



async function generarTiles() {
  showStatus("Regenerando tiles... Esto puede tardar unos segundos.", "loading");

  ipcRenderer.invoke("generate-tiles").then(() => {
    showStatus("Tiles regenerados correctamente. Recargando...", "success");
    setTimeout(() => {
      location.reload();  // Fuerza recarga completa
    }, 2000);
  }).catch(err => {
    showStatus("Error al regenerar tiles: " + err.message, "error");
  });
}

// function exportarImagenes() {
//   showStatus("Exportando todas las imágenes...", "loading");

//   ipcRenderer.invoke("export-all")
//     .then(() => {
//       showStatus("Exportación iniciada para todas las imágenes.", "success");
//     })
//     .catch(err => {
//       showStatus("Error al exportar imágenes: " + err.message, "error");
//     });
// }

// function exportarImagenes() {
//   showStatus("Exportando todas las imágenes...", "loading");
//   NProgress.start();
//   NProgress.set(0);

//   ipcRenderer.invoke("export-all")
//     .then(() => {
//       NProgress.done();
//       ocultarProgresoAlerta();
//       showStatus("Exportación iniciada para todas las imágenes.", "success");

//     })
//     .catch(err => {
//       NProgress.done();
//       showStatus("Error al exportar imágenes: " + err.message, "error");
//     });
// }

ipcRenderer.on("export-progress", (event, message) => {
  console.log("📥 Mensaje recibido:", message);

  // Progreso de lanzamiento
  if (message.includes("ProgresoLanzado:")) {
    const match = message.match(/ProgresoLanzado:\s*(\d+)\/(\d+)/);
    if (match) {
      const actual = parseInt(match[1]);
      const total = parseInt(match[2]);
      const percent = Math.round((actual / total) * 100);
      NProgress.set(percent / 100);

      // mostrarProgresoAlerta(`🚀 Lanzadas: ${actual}/${total} (${percent}%)`);
      mostrarProgresoAlerta(`🚀 Lanzadas: ${actual}/${total} (${percent}%)`, percent);

    }
  }

  // Progreso real de completadas
  if (message.includes("ProgresoReal:")) {
    const match = message.match(/ProgresoReal:\s*(\d+)\/(\d+)/);
    if (match) {
      const actual = parseInt(match[1]);
      const total = parseInt(match[2]);
      const percent = Math.round((actual / total) * 100);
      NProgress.set(percent / 100);

      mostrarProgresoAlerta(`📥 Completadas: ${actual}/${total} (${percent}%)`);

      if (actual === total) {
        setTimeout(() => {
          NProgress.done();
          ocultarProgresoAlerta();
          showStatus("Todas las imágenes han sido exportadas correctamente.", "success");
        }, 1000);
      }
    }
  }
});


// Función mejorada para mostrar progreso con más detalles
function mostrarProgresoAlerta(texto, percent = null) {
  const alerta = document.getElementById("progreso-alerta");

  // Crear barra de progreso visual si se proporciona porcentaje
  let progressBar = '';
  if (percent !== null) {
    progressBar = `
      <div style="
        width: 100%; 
        background-color: rgba(255,255,255,0.3); 
        border-radius: 4px; 
        margin: 8px 0;
        height: 8px;
      ">
        <div style="
          width: ${percent}%; 
          background-color: #4CAF50; 
          height: 100%; 
          border-radius: 4px;
          transition: width 0.3s ease;
        "></div>
      </div>`;
  }

  alerta.innerHTML = `
    <div style="font-weight: bold; margin-bottom: 5px;">${texto}</div>
    ${progressBar}
    <button onclick="ocultarProgresoAlerta()" style="
      margin-top: 8px;
      color: #fff;
      background: rgba(255,255,255,0.2);
      border: 1px solid rgba(255,255,255,0.5);
      padding: 4px 8px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
      transition: background-color 0.3s;
    " onmouseover="this.style.backgroundColor='rgba(255,255,255,0.3)'" 
       onmouseout="this.style.backgroundColor='rgba(255,255,255,0.2)'">
      Ocultar
    </button>
  `;
  alerta.style.display = "block";
}

// Función mejorada para manejar progreso de exportación
ipcRenderer.on("export-progress", (event, message) => {
  console.log("📥 Mensaje recibido:", message);

  // Progreso de lanzamiento de tareas
  if (message.includes("ProgresoLanzado:")) {
    const match = message.match(/ProgresoLanzado:\s*(\d+)\/(\d+)/);
    if (match) {
      const actual = parseInt(match[1]);
      const total = parseInt(match[2]);
      const percent = Math.round((actual / total) * 100);

      // Actualizar barra de progreso principal
      NProgress.set(0.3); // Lanzamiento completo = 30%

      mostrarProgresoAlerta(
        `🚀 Tareas lanzadas: ${actual}/${total} (${percent}%)`,
        percent
      );
    }
  }

  // Progreso real de tareas completadas
  if (message.includes("ProgresoReal:")) {
    const match = message.match(/ProgresoReal:\s*(\d+)\/(\d+)/);
    if (match) {
      const actual = parseInt(match[1]);
      const total = parseInt(match[2]);
      const percent = Math.round((actual / total) * 100);

      // Progreso real va del 30% al 100%
      const nprogress_value = 0.3 + (percent / 100) * 0.7;
      NProgress.set(nprogress_value);

      mostrarProgresoAlerta(
        `📥 Tareas completadas: ${actual}/${total} (${percent}%)`,
        percent
      );

      // Si todas están completadas
      if (actual === total) {
        setTimeout(() => {
          NProgress.done();
          mostrarProgresoAlerta("¡Exportación completada exitosamente!", 100);

          // Auto-ocultar después de 3 segundos
          setTimeout(() => {
            ocultarProgresoAlerta();
            showStatus("Todas las imágenes han sido exportadas y organizadas.", "success");
          }, 3000);
        }, 1000);
      }
    }
  }

  // Manejar otros mensajes de estado
  if (message.includes("📊 Progreso:")) {
    // Extraer información detallada del progreso
    const progressMatch = message.match(/📊 Progreso: ([\d.]+)%/);
    const completedMatch = message.match(/(\d+)/);
    const runningMatch = message.match(/🔄 (\d+)/);
    const failedMatch = message.match(/(\d+)/);

    if (progressMatch && completedMatch) {
      const progressPct = parseFloat(progressMatch[1]);
      const completed = parseInt(completedMatch[1]);
      const running = runningMatch ? parseInt(runningMatch[1]) : 0;
      const failed = failedMatch ? parseInt(failedMatch[1]) : 0;

      mostrarProgresoAlerta(
        `📊 ${progressPct.toFixed(1)}% | ✅${completed} 🔄${running} ❌${failed}`,
        progressPct
      );
    }
  }
});

// Función mejorada para exportar con mejor feedback
function exportarImagenes() {
  showStatus("Preparando exportación de imágenes...", "loading");

  // Inicializar progreso
  NProgress.start();
  NProgress.set(0);

  // Mostrar alerta inicial
  mostrarProgresoAlerta("🔧 Preparando exportación...", 0);

  ipcRenderer.invoke("export-all")
    .then(() => {
      console.log("Exportación iniciada correctamente");
      // No ocultar progreso aquí - se maneja en los eventos
    })
    .catch(err => {
      NProgress.done();
      ocultarProgresoAlerta();
      showStatus("Error al exportar imágenes: " + err.message, "error");
      console.error("Error en exportación:", err);
    });
}

// Función mejorada para ocultar progreso
function ocultarProgresoAlerta() {
  const alerta = document.getElementById("progreso-alerta");
  alerta.style.opacity = "0";

  setTimeout(() => {
    alerta.style.display = "none";
    alerta.style.opacity = "1"; // Resetear para próxima vez
  }, 300);
}

// Añadir estilos CSS para mejores transiciones
const progressStyles = `
  #progreso-alerta {
    transition: opacity 0.3s ease-in-out;
    backdrop-filter: blur(5px);
    border: 1px solid rgba(255,255,255,0.2);
  }
  
  #progreso-alerta button:hover {
    transform: scale(1.05);
  }
`;

// Inyectar estilos
const styleSheet = document.createElement("style");
styleSheet.textContent = progressStyles;
document.head.appendChild(styleSheet);


function ocultarProgresoAlerta() {
  const alerta = document.getElementById("progreso-alerta");
  alerta.style.display = "none";
}

function debounce(func, timeout = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => { func.apply(this, args); }, timeout);
  };
}

function updateCoordinateInfo(e) {
  const info = document.getElementById("info");
  info.innerHTML = `Lat: ${e.latlng.lat.toFixed(4)}, Lng: ${e.latlng.lng.toFixed(4)} | Zoom: ${map.getZoom()}`;
}

function toggleSidebar() {
  const sidebar = document.getElementById("sidebar");
  const toggleBtn = document.getElementById("toggle-sidebar");

  if (!sidebar || !toggleBtn) {
    console.warn("Elementos de sidebar no encontrados");
    return;
  }

  sidebarVisible = !sidebarVisible;
  sidebar.style.transform = sidebarVisible ? "translateX(0)" : "translateX(100%)";
  toggleBtn.innerHTML = sidebarVisible ? "❯" : "❮";
  toggleBtn.style.right = sidebarVisible ? "350px" : "0";
}

// async function loadTileData() {
//   showStatus("Cargando datos de tiles...", "loading");

//   try {
//     const response = await fetch("tiles_panama.json");
//     if (!response.ok) throw new Error("Error cargando datos");

//     tileData = await response.json();
//     const fechas = Object.keys(tileData).sort((a, b) => parseInt(a) - parseInt(b));
//     const selector = document.getElementById("fecha");

//     selector.innerHTML = "";

//     fechas.forEach(fecha => {
//       const option = document.createElement("option");
//       option.value = fecha;
//       option.text = fecha;
//       selector.appendChild(option);
//     });

//     if (fechas.length > 0) {
//       selector.value = fechas[fechas.length - 1];
//       cambiarCapa();
//       hideStatus();
//     } else {
//       showStatus("No se encontraron datos de años", "error");
//     }
//   } catch (err) {
//     console.error("Error loading tile data:", err);
//     showStatus("Error cargando datos: " + err.message, "error");
//   }
// }
async function loadTileData() {
  showStatus("Cargando datos de tiles...", "loading");


  if (!fs.existsSync(tileFilePath)) {
    showStatus("No se encontró el archivo tiles_panama.json. Creando...", "loading");
    await ipcRenderer.invoke("generate-tiles"); // O pasa la ruta si lo necesitas
  }

  try {
    const fileContents = fs.readFileSync(tileFilePath, "utf-8");
    tileData = JSON.parse(fileContents);


    const selector = document.getElementById("fecha");
    selector.innerHTML = "";

    // Agrupar por tipo de dataset
    const dmspKeys = Object.keys(tileData).filter(k => tileData[k].dataset === "DMSP").sort();
    const viirsKeys = Object.keys(tileData).filter(k => tileData[k].dataset === "VIIRS").sort();

    const dmspGroup = document.createElement("optgroup");
    dmspGroup.label = "DMSP (1992–2013)";
    dmspKeys.forEach(k => {
      const option = document.createElement("option");
      option.value = k;
      option.text = k;
      dmspGroup.appendChild(option);
    });

    const viirsGroup = document.createElement("optgroup");
    viirsGroup.label = "VIIRS mensual (2014–2025)";
    viirsKeys.forEach(k => {
      const option = document.createElement("option");
      option.value = k;
      option.text = k;
      viirsGroup.appendChild(option);
    });

    selector.appendChild(dmspGroup);
    selector.appendChild(viirsGroup);

    if (dmspKeys.length + viirsKeys.length > 0) {
      selector.value = viirsKeys[viirsKeys.length - 1]; // Selecciona la más reciente
      cambiarCapa();
      hideStatus();
    } else {
      showStatus("No se encontraron datos en tiles_panama.json", "error");
    }

  } catch (err) {
    showStatus("Error leyendo tiles: " + err.message, "error");
  }
}


function cambiarCapa() {
  const fechaEl = document.getElementById("fecha");
  const opacidadEl = document.getElementById("opacidad");
  
  if (!fechaEl || !opacidadEl) {
    console.warn("Elementos de fecha u opacidad no encontrados");
    return;
  }

  const fecha = fechaEl.value;
  const opacity = parseFloat(opacidadEl.value);

  if (!fecha || !tileData[fecha]) {
    showStatus("No hay datos para el año " + fecha, "error");
    return;
  }

  const url = tileData[fecha]?.tile;
  updateInfoText(fecha);

  if (currentLayer) {
    map.removeLayer(currentLayer);
  }

  if (url) {
    showStatus("Cargando capa " + fecha + "...", "loading");

    currentLayer = L.tileLayer(url, {
      attribution: "NOAA / Earth Engine",
      opacity: opacity,
      minZoom: 5,
      maxZoom: 12
    }).addTo(map);

    // Detectar error 401
    currentLayer.on('tileerror', function (errorEvent) {
      const tile = errorEvent?.tile;

      if (tile?.src && tile.src.includes("401")) {
        document.getElementById("btn-regenerar-tiles").style.display = "inline-block";
        showStatus("⚠️ El token de los tiles ha expirado. Haz clic en 'Regenerar Tiles' para actualizar.", "error");
        return;
      }

      // Fallback: por si no está en el src
      try {
        const imgRequest = new XMLHttpRequest();
        imgRequest.open('GET', tile.src, true);
        imgRequest.onreadystatechange = function () {
          if (imgRequest.readyState === 4 && imgRequest.status === 401) {
            document.getElementById("btn-regenerar-tiles").style.display = "inline-block";
            showStatus("⚠️ El token ha expirado. Pulsa 'Regenerar Tiles'.", "error");
          }
        };
        imgRequest.send();
      } catch (e) {
        console.warn("Error verificando tile 401:", e);
      }
    });



    currentLayer.on('load', () => {
      hideStatus();
    });
  }
}

function updateInfoText(fecha) {
  const info = document.getElementById("info");
  const type = tileData[fecha]?.type || "Desconocido";
  const resolution = tileData[fecha]?.resolution || "N/A";

  info.innerHTML = `Año: ${fecha} | Tipo: ${type} | Resolución: ${resolution}`;
}

async function fetchDriveImages() {
  const container = document.getElementById("imagenes-drive");
  showStatusInElement(container, "Cargando imágenes desde Drive...");

  try {
    if (!cachedDriveImages) {
      const resultado = await ipcRenderer.invoke("listar-imagenes-drive");

      if (resultado.error) {
        showStatusInElement(container, "⚠️ Error al obtener imágenes: " + resultado.message, "error");
        return false;
      }

      if (!resultado || resultado.length === 0) {
        showStatusInElement(container, "No se encontraron imágenes en Drive", "info");
        return false;
      }

      cachedDriveImages = resultado;
    }

    return true;
  } catch (e) {
    console.error(e);
    showStatusInElement(container, "Error inesperado: " + e.message, "error");
    return false;
  }
}


// Nuevo: función unificada para cargar imágenes y luego filtrar
async function cargarYMostrarImagenes() {
  cachedDriveImages = null;
  const success = await fetchDriveImages();
  if (success) filtrarImagenes();
}

// Separado: solo aplica filtros si ya hay imágenes
function filtrarImagenes() {
  const container = document.getElementById("imagenes-drive");
  
  if (!container) {
    console.warn("Contenedor de imágenes no encontrado");
    return;
  }

  if (!cachedDriveImages) {
    container.innerHTML = `<div class="status-message info">Primero haz clic en 'Cargar imágenes locales'</div>`;
    return;
  }

  const añoFiltroEl = document.getElementById("filtro-año");
  const tipoFiltroEl = document.getElementById("filtro-tipo");
  
  const añoFiltro = añoFiltroEl ? añoFiltroEl.value.trim() : "";
  const tipoFiltro = tipoFiltroEl ? tipoFiltroEl.value : "";

  const filtrados = cachedDriveImages.filter(file => {
    let pasa = true;

    if (añoFiltro) {
      pasa = file.fecha.includes(añoFiltro);
    }

    if (tipoFiltro) {
      pasa = pasa && file.dataset === tipoFiltro;
    }

    return pasa;
  });

  if (filtrados.length === 0) {
    container.innerHTML = `<div class="status-message info">No hay resultados para los filtros aplicados</div>`;
    return;
  }
{/* <a href="${file.path}" target="_blank">📂 Ver imagen local</a> */}
  container.innerHTML = filtrados.map(file => `
    <div class="img-entry">
      <h4>${file.fecha} (${file.dataset})</h4>
      <p>
        
      </p>
      <div class="metadata-container">
        <details>
          <summary>Ver metadatos</summary>
          <ul class="metadata-list">
            ${Object.entries(file.metadata).map(([key, val]) => `<li><strong>${key}:</strong> <span>${val}</span></li>`).join("")}
          </ul>
        </details>
      </div>
    </div>
  `).join("");
}


function showStatus(message, type = "loading") {
  const statusEl = document.getElementById("estado");
  statusEl.className = "status-message " + type;

  if (type === "loading") {
    statusEl.innerHTML = `<div class="loader"></div>${message}`;
  } else {
    const icon = type === "success" ? "✅" : type === "error" ? "❌" : "ℹ️";
    statusEl.innerHTML = `${icon} ${message}`;
  }

  statusEl.style.display = "block";
}

function hideStatus() {
  const statusEl = document.getElementById("estado");
  statusEl.style.display = "none";
}

function showStatusInElement(element, message, type = "loading") {
  if (type === "loading") {
    element.innerHTML = `<div class="status-message ${type}"><div class="loader"></div>${message}</div>`;
  } else {
    const icon = type === "success" ? "✅" : type === "error" ? "❌" : "ℹ️";
    element.innerHTML = `<div class="status-message ${type}">${icon} ${message}</div>`;
  }
}


async function configurarVerificacionAutomatica() {
  const frequency = document.getElementById("check-frequency").value;
  const time = document.getElementById("check-time").value;
  const taskId = "NOAA_AUTO_CHECK";

  if (!time) {
    showStatus("Por favor selecciona una hora para la verificación", "error");
    return;
  }

  try {
    // Primero eliminar la tarea si existe
    try {
      await ipcRenderer.invoke("eliminarTareaWindows", taskId);
    } catch (e) {
      console.log("No había tarea previa que eliminar");
    }

    // Crear nueva tarea
    const args = {
      taskId,
      hora: time,
      frecuencia: frequency,
      intervalo: frequency === "HOURLY" ? "1" : "1"
    };

    await ipcRenderer.invoke("crearTareaNOAA", args);
    showStatus("Verificación automática configurada correctamente", "success");
  } catch (err) {
    showStatus("Error configurando verificación automática: " + err.message, "error");
  }
}

async function cargarImagenesLocales() {
  const container = document.getElementById("imagenes-drive");
  
  if (!container) {
    console.warn("Contenedor imagenes-drive no encontrado");
    return;
  }
  
  container.innerHTML = `<div class="status-message loading"><div class="loader"></div>Cargando imágenes locales...</div>`;

  try {
    // La ruta correcta al archivo de metadatos
    const response = await fetch("../../backend/API-NASA/metadatos_noaa.json");
    if (!response.ok) throw new Error(`Error cargando metadatos: ${response.status} ${response.statusText}`);

    const metadatos = await response.json();
    const imagenes = [];

    for (const id in metadatos) {
      const meta = metadatos[id];
      const dataset = meta.dataset;
      const fecha = id;  // Usa el ID como identificador
      const subfolder = dataset === "VIIRS" ? "VIIRS" : "DMSP-OLS";

      const localPath = `../../backend/API-NASA/${subfolder}/noaa_${fecha}.tif`;

      imagenes.push({
        id,
        fecha,
        dataset,
        path: localPath,
        metadata: meta
      });
    }

    cachedDriveImages = imagenes;
    
    console.log(`📊 Cargadas ${imagenes.length} imágenes desde backend/API-NASA/metadatos_noaa.json`);
    
    filtrarImagenes();

  } catch (err) {
    console.error("❌ Error cargando imágenes locales:", err);
    container.innerHTML = `<div class="status-message error">
      ❌ Error cargando imágenes locales: ${err.message}<br>
      <small>Archivo buscado en: backend/API-NASA/metadatos_noaa.json</small>
    </div>`;
  }
}

function abrirModalExportar() {
  document.getElementById("modal-exportar").style.display = "flex";
  cargarPendientesExport();
}

function cerrarModalExportar() {
  document.getElementById("modal-exportar").style.display = "none";
}

async function cargarPendientesExport() {
  const contenedor = document.getElementById("lista-pendientes");
  contenedor.innerHTML = `<p>Cargando imágenes...</p>`;
  try {
    pendientesExportar = await ipcRenderer.invoke("listar-candidatos-export");
    pagina = 1;
    filtrarPorDataset();
  } catch (err) {
    contenedor.innerHTML = `<p style='color:red;'>Error: ${err}</p>`;
  }
}

function filtrarPorDataset() {
  const filtroDatasetEl = document.getElementById("filtro-dataset");
  const tipo = filtroDatasetEl ? filtroDatasetEl.value : "";
  
  filtradosDataset = tipo ? pendientesExportar.filter(img => img.dataset === tipo) : pendientesExportar;
  pagina = 1;
  renderizarPendientes();
  actualizarResumen();
}

function actualizarResumen() {
  const totalTodos = pendientesExportar.length;
  const totalDMSP = pendientesExportar.filter(i => i.dataset === "DMSP").length;
  const totalVIIRS = pendientesExportar.filter(i => i.dataset === "VIIRS").length;
  
  const filtroDatasetEl = document.getElementById("filtro-dataset");
  const resumenTotalEl = document.getElementById("resumen-total");
  
  const seleccionado = filtroDatasetEl ? filtroDatasetEl.value : "";

  let texto = `Total: ${totalTodos} imágenes | DMSP: ${totalDMSP} | VIIRS: ${totalVIIRS}`;
  if (seleccionado) texto += ` | Mostrando: ${filtradosDataset.length}`;
  
  if (resumenTotalEl) {
    resumenTotalEl.innerText = texto;
  }
}

function renderizarPendientes() {
  const contenedor = document.getElementById("lista-pendientes");
  if (!filtradosDataset.length) {
    contenedor.innerHTML = `<p>No hay imágenes nuevas para exportar.</p>`;
    return;
  }

  const inicio = (pagina - 1) * porPagina;
  const fin = Math.min(inicio + porPagina, filtradosDataset.length);
  const items = filtradosDataset.slice(inicio, fin);

  contenedor.innerHTML = `
    <table style="width: 100%; border-collapse: collapse;">
      <thead>
        <tr style="background-color: #f0f0f0;">
          <th style="text-align:left; padding: 6px;">ID</th>
          <th style="text-align:left; padding: 6px;">Fecha</th>
          <th style="text-align:left; padding: 6px;">Dataset</th>
        </tr>
      </thead>
      <tbody>
        ${items.map(img => `
          <tr>
            <td style="padding: 6px;">${img.id}</td>
            <td style="padding: 6px;">${img.fecha}</td>
            <td style="padding: 6px;">${img.dataset}</td>
          </tr>`).join("")}
      </tbody>
    </table>
  `;

  const paginaActualEl = document.getElementById("pagina-actual");
  const prevPagEl = document.getElementById("prev-pag");
  const nextPagEl = document.getElementById("next-pag");
  
  if (paginaActualEl) {
    paginaActualEl.innerText = `Página ${pagina} de ${Math.ceil(filtradosDataset.length / porPagina)}`;
  }
  
  if (prevPagEl) {
    prevPagEl.disabled = pagina === 1;
  }
  
  if (nextPagEl) {
    nextPagEl.disabled = fin >= filtradosDataset.length;
  }
}

