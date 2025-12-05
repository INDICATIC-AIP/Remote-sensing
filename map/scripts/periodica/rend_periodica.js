// Versión corregida del renderer con logging optimizado y función tiempoDescargaFormato arreglada

const axios = require('axios');
const cheerio = require('cheerio');
const config = require('../../config.js');

const { cameraMap, filmMap } = require('./utils/data.js');
const LOG_PATH = path.join("..", "..", "logs", "iss", "general.log");
const validInputRegex = /^[a-zA-Z0-9 *\-.,±]+$/;

fetch("template.html")
  .then(res => res.text())
  .then(template => {
    const app = Vue.createApp({
      template: template,
      data() {
        return {
          limiteDescarga: 15,
          filters: [],
          returnFieldsSelected: {},
          accordionOpen: null,
          results: [],
          searchPerformed: false,
          isLoading: false,
          isPanelOpen: true,
          showResultsPanel: true,
          selectedImageUrl: null,
          map: null,
          clusterGroup: null,
          markers: [],
          selectedPhotoIndex: null,
          selectedCoordSource: "frames",
          tables: {
            frames: ["mission", "roll", "frame", "tilt", "pdate", "ptime", "cldp", "azi", "elev", "fclt", "lat", "lon", "nlat", "nlon", "camera", "film", "geon", "feat"],
            images: ["mission", "roll", "frame", "directory", "filename", "width", "height", "annotated", "cropped", "filesize"],
            nadir: ["mission", "roll", "frame", "pdate", "ptime", "lat", "lon", "azi", "elev", "cldp"],
            camera: ["mission", "roll", "frame", "fclt", "camera"],
            captions: ["mission", "roll", "frame", "caption"],
            mlfeat: ["mission", "roll", "frame", "feat"],
            mlcoord: [
              "mission", "roll", "frame", "lat", "lon", "orientation", "resolution_long", "resolution_short",
              "ul_lat", "ul_lon", "ur_lat", "ur_lon", "ll_lat", "ll_lon", "lr_lat", "lr_lon"
            ],
            publicfeatures: ["mission", "roll", "frame", "features"],
          },
          frames_values: {
            camera_codes: ["AA", "C1", "DV", "E2", "E3", "E4", "HB", "LH", "MA", "MS", "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8", "N9", "NK", "RX", "SA", "SB"],
            film_codes: [
              "1035I", "2000E", "2041", "2106", "2402", "2415", "2443", "2447", "2448", "3060E", "3072E", "3101", "4256E", "4288E", "4928E",
              "5012", "5017", "5025", "5026", "5028", "5030", "5036", "5046", "5048", "5069", "5074", "5080", "5095", "5096", "5245", "5250",
              "5327", "5568E", "5755", "5775", "5776", "6017", "6048E", "6118", "6144E", "7360E", "8256E", "8443", "ANSCO", "E2424", "E2424C",
              "E2424D", "E2443", "E3414", "E3443", "EKTAR", "FJ400", "FJ800", "QX", "QX807", "QX824", "QX868", "RS200", "RS50", "RUSSI", "SG800",
              "SN-10", "SO022", "SO022A", "SO022B", "SO117", "SO121", "SO131", "SO180", "SO217", "SO242", "SO356", "SO368", "SO489", "UNKN", "VELVI"
            ]
          },
          currentPage: 1,
          pageSize: 20,
          mostrarModalCron: false,
          cronHora: "",
          cronFrecuencia: "ONCE",
          cronIntervalo: 1,
          tareasPeriodicas: [],
          boundingBox: {
            latMin: 6.1,
            latMax: 10.8,
            lonMin: -82.9,
            lonMax: -77.3
          },
          modoNocturno: true,
          descargandoDirecto: false,
          progresoDescarga: 0,
          totalImagenes: 0,
          imagenesDescargadas: 0,
          tiempoDescarga: 0,
          intervaloTiempo: null,
          mostrarModalAcciones: false,
          estadoDescarga: 'idle', // 'idle', 'processing', 'downloading', 'completed'
          mensajeEstado: '', // Mensaje descriptivo del estado actual
          verificandoNasaIds: false,
          resultadosNuevos: [], // Solo imágenes que NO están en BD
          todasEnBD: false, // True si todas las imágenes ya están descargada
          vistaFiltro: 'todas', // 'todas', 'nuevas', 'descargadas'
        };
      },
      computed: {
        resultadosFiltrados() {
          switch (this.vistaFiltro) {
            case 'nuevas':
              return this.resultadosNuevos;
            case 'descargadas':
              return this.results.filter(photo => !this.esImagenNueva(photo));
            case 'todas':
            default:
              return this.results;
          }
        },
        //  ÚNICO paginatedResults basado en resultados filtrados
        paginatedResults() {
          const start = (this.currentPage - 1) * this.pageSize;
          return this.resultadosFiltrados.slice(start, start + this.pageSize);
        },
        //  PÁGINAS basadas en resultados filtrados
        totalPages() {
          return Math.ceil(this.resultadosFiltrados.length / this.pageSize);
        },
        //  CORREGIDO: Función computed para formatear tiempo de descarga
        tiempoDescargaFormato() {
          const horas = Math.floor(this.tiempoDescarga / 3600).toString().padStart(2, '0');
          const minutos = Math.floor((this.tiempoDescarga % 3600) / 60).toString().padStart(2, '0');
          const segundos = (this.tiempoDescarga % 60).toString().padStart(2, '0');
          return `${horas}:${minutos}:${segundos}`;
        },
        allFiltersValid() {
          return this.filters.every(f =>
            f.table &&
            f.field &&
            f.operator &&
            f.value.trim() !== "" &&
            this.isValidInput(f.value)
          );
        },
        allowedReturnTables() {
          const mapping = {
            frames: ["frames", "images", "camera", "captions", "mlfeat"],
            nadir: ["nadir", "images", "camera", "captions"],
            mlcoord: ["mlcoord", "images", "mlfeat", "camera"]
          };
          return mapping[this.selectedCoordSource] || [];
        },
        filteredTables() {
          const result = {};
          for (const [table, fields] of Object.entries(this.tables)) {
            if (this.allowedReturnTables.includes(table)) {
              result[table] = fields;
            }
          }
          return result;
        },
        puedeDescargar() {
          return !this.verificandoNasaIds &&
            !this.todasEnBD &&
            !this.descargandoDirecto &&
            this.resultadosNuevos.length > 0;
        }
      },
      watch: {
        // Resetear paginación cuando cambia el filtro de vista
        //  ACTUALIZAR MAPA Y PAGINACIÓN al cambiar filtro
        vistaFiltro() {
          this.currentPage = 1;

          // Actualizar mapa con nuevo filtro
          if (this.searchPerformed && this.map) {
            this.actualizarMapaConFiltros();
          }
        },


        selectedCoordSource() {
          this.aplicarCamposDefault(this.returnFieldsSelected);
        }
      },
      mounted() {
        // alert(" Actualizacion.");
        window.mapHelpers.initBoundingBoxMap("bounding-box-map", this.boundingBox, this.actualizarBoundingBox);
        this.aplicarCamposDefault(this.returnFieldsSelected, this.tables, this.allowedReturnTables, this.selectedCoordSource, this.getAll);
        this.map = window.mapHelpers.initMap("map");
        window.addEventListener("resize", this.handleWindowResize);

        // Cargar tareas con logging
        fetch("tasks.json")
          .then(res => {
            if (!res.ok) {
              ipcRenderer.send("log_custom", {
                section: "Carga de Tareas",
                message: "Archivo tasks.json no encontrado o inaccesible",
                level: "WARNING",
                file: LOG_PATH
              });
              return [];
            }
            return res.json();
          })
          .then(data => {
            this.tareasPeriodicas = data;
            ipcRenderer.send("log_custom", {
              message: `Tareas cargadas exitosamente: ${data.length} tareas encontradas`,
              level: "INFO",
              file: LOG_PATH
            });
          })
          .catch(err => {
            ipcRenderer.send("log_custom", {
              section: "Error Carga de Tareas",
              message: `No se pudo cargar tasks.json: ${err.message}`,
              level: "ERROR",
              file: LOG_PATH
            });
            this.tareasPeriodicas = [];
          });
      },
      beforeUnmount() {
        window.removeEventListener("resize", this.handleWindowResize);
        ipcRenderer.removeAllListeners('progreso-descarga');
        ipcRenderer.removeAllListeners('descarga-completa');
      },
      methods: {
        //  FUNCIÓN CORREGIDA: obtenerNadirAltitudCamaraOptimized con fecha y verificación GeoTIFF
        async obtenerNadirAltitudCamaraOptimized(nasaId) {
          const MAX_RETRIES = 2;
          const TIMEOUT = 8000;

          for (let intento = 0; intento <= MAX_RETRIES; intento++) {
            try {
              const [mission, roll, frame] = nasaId.split('-');
              if (!mission || !roll || !frame) {
                console.warn(` NASA_ID mal formateado: ${nasaId}`);
                return {
                  NADIR_CENTER: null,
                  ALTITUD: null,
                  CAMARA: null,
                  FECHA_CAPTURA: null,
                  GEOTIFF_URL: null,
                  HAS_GEOTIFF: false
                };
              }

              const url = `https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?mission=${mission}&roll=${roll}&frame=${frame}`;

              const timeoutPromise = new Promise((_, reject) =>
                setTimeout(() => reject(new Error('Timeout')), TIMEOUT)
              );

              const fetchPromise = axios.get(url, {
                timeout: TIMEOUT,
                headers: {
                  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
              });

              const res = await Promise.race([fetchPromise, timeoutPromise]);
              const $ = cheerio.load(res.data);

              //  EXTRAER FECHA DE CAPTURA MEJORADA
              let fechaCaptura = null;

              // Método 1: Buscar en tabla con "Date taken"
              const fechaMatch = res.data.match(/Date taken[^<]*<\/td>\s*<td[^>]*>([^<]+)<\/td>/i);
              if (fechaMatch) {
                fechaCaptura = fechaMatch[1].trim().replace(/\./g, '-');
              }

              // Método 2: Si no se encuentra, buscar en otros formatos
              if (!fechaCaptura) {
                const alternativeFechaMatch = res.data.match(/(\d{4})\.(\d{2})\.(\d{2})/);
                if (alternativeFechaMatch) {
                  fechaCaptura = `${alternativeFechaMatch[1]}-${alternativeFechaMatch[2]}-${alternativeFechaMatch[3]}`;
                }
              }

              // Buscar información de cámara
              const cameraEl = $("em:contains('Camera:')");
              const cameraText = cameraEl && cameraEl[0] && cameraEl[0].nextSibling
                ? $(cameraEl[0].nextSibling).text().trim().replace(/["']/g, "")
                : null;

              // Buscar información de Nadir
              const nadirEl = $("em:contains('Nadir to Photo Center:')");
              const nadirText = nadirEl && nadirEl[0] && nadirEl[0].nextSibling
                ? $(nadirEl[0].nextSibling).text().trim().replace(/["']/g, "")
                : null;

              // Buscar información de altitud
              const altEl = $("em:contains('Spacecraft Altitude')");
              const altText = altEl.parent().text().replace(/[\r\n\t"]/g, "").trim();
              const altMatch = altText.match(/\(([\d.,]+)km\)/);
              const altValue = altMatch ? parseFloat(altMatch[1].replace(",", "")) : null;

              //  VERIFICAR SI HAY GEOTIFF DISPONIBLE
              const hasGeotiff = !res.data.includes("No GeoTIFF is available for this photo");
              const geotiffUrl = hasGeotiff ? `https://eol.jsc.nasa.gov/SearchPhotos/GetGeotiff.pl?photo=${nasaId}` : null;

              console.log(` Datos obtenidos para ${nasaId}: Camera=${cameraText}, Nadir=${nadirText}, Alt=${altValue}, Fecha=${fechaCaptura}, GeoTIFF=${hasGeotiff ? 'SÍ' : 'NO'}`);

              return {
                NADIR_CENTER: nadirText || null,
                ALTITUD: altValue,
                CAMARA: cameraText,
                FECHA_CAPTURA: fechaCaptura,
                GEOTIFF_URL: geotiffUrl,
                HAS_GEOTIFF: hasGeotiff
              };

            } catch (err) {
              console.warn(` Intento ${intento + 1} fallido para ${nasaId}: ${err.message}`);

              if (intento === MAX_RETRIES) {
                ipcRenderer.send("log_custom", {
                  message: `Error obteniendo NADIR/ALTITUD/FECHA para ${nasaId} después de ${MAX_RETRIES + 1} intentos: ${err.message}`,
                  level: "ERROR",
                  file: LOG_PATH
                });
                return {
                  NADIR_CENTER: null,
                  ALTITUD: null,
                  CAMARA: null,
                  FECHA_CAPTURA: null,
                  GEOTIFF_URL: null,
                  IMAGE_URL: null,
                  HAS_GEOTIFF: false
                };
              }

              // Esperar antes del siguiente intento
              await new Promise(resolve => setTimeout(resolve, 1000 * (intento + 1)));
            }
          }
        },
        // Versión corregida y unificada:
        async obtenerCamaraMetadataOptimized(nasaId) {
          const MAX_RETRIES = 2;
          const TIMEOUT = 10000;

          for (let intento = 0; intento <= MAX_RETRIES; intento++) {
            try {
              const [mission, roll, frame] = nasaId.split('-');
              if (!mission || !roll || !frame) {
                console.warn(` NASA_ID mal formateado: ${nasaId}`);
                return null;
              }

              const url = `https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?mission=${mission}&roll=${roll}&frame=${frame}`;

              const timeoutPromise = new Promise((_, reject) =>
                setTimeout(() => reject(new Error('Timeout')), TIMEOUT)
              );

              const fetchPromise = axios.get(url, {
                timeout: TIMEOUT,
                headers: {
                  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
              });

              const res = await Promise.race([fetchPromise, timeoutPromise]);
              const $ = cheerio.load(res.data);

              const button = $("input[type='button'][value='View camera metadata']");
              if (button.length && button.attr("onclick")) {
                const onclickValue = button.attr("onclick");
                const start = onclickValue.indexOf("('") + 2;
                const end = onclickValue.indexOf("')", start);
                const fileUrl = onclickValue.substring(start, end);

                if (fileUrl && fileUrl.startsWith("/")) {
                  const outputFolder = this.getOutputFolder(); // Sin parámetros
                  const fullUrl = `https://eol.jsc.nasa.gov${fileUrl}`;
                  const finalPath = path.join(outputFolder, path.basename(fileUrl));

                  // Verificar si ya existe y es válido
                  if (fs.existsSync(finalPath)) {
                    const stats = fs.statSync(finalPath);
                    if (stats.size > 0) {
                      console.log(` Camera metadata ya existe: ${finalPath}`);
                      return finalPath;
                    }
                  }

                  const downloadTimeoutPromise = new Promise((_, reject) =>
                    setTimeout(() => reject(new Error('Download timeout')), TIMEOUT)
                  );

                  const downloadPromise = axios.get(fullUrl, {
                    timeout: TIMEOUT,
                    headers: {
                      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                  });

                  const response = await Promise.race([downloadPromise, downloadTimeoutPromise]);

                  if (response.status === 200 && response.data) {
                    fs.writeFileSync(finalPath, response.data, 'utf-8');
                    console.log(` Camera metadata descargado: ${finalPath}`);
                    return finalPath;
                  }
                }
              }

              console.log(` No se encontró botón de camera metadata para ${nasaId}`);
              return null;

            } catch (err) {
              console.warn(` Error en camera metadata (intento ${intento + 1}) para ${nasaId}: ${err.message}`);

              if (intento === MAX_RETRIES) {
                ipcRenderer.send("log_custom", {
                  message: `Error en CAMARA_METADATA para ${nasaId} después de ${MAX_RETRIES + 1} intentos: ${err.message}`,
                  level: "ERROR",
                  file: LOG_PATH
                });
                return null;
              }

              await new Promise(resolve => setTimeout(resolve, 1000 * (intento + 1)));
            }
          }
        },
        //  NUEVA FUNCIÓN: Deduplicar metadatos por NASA_ID
        // deduplicarMetadatos(metadatos) {
        //   const vistos = new Map();
        //   const unicos = [];
        //   let duplicados = 0;

        //   for (const metadata of metadatos) {
        //     const nasaId = metadata.NASA_ID;

        //     if (!nasaId || nasaId === "Sin_ID") {
        //       // Mantener metadatos sin NASA_ID válido (pueden ser únicos por otras razones)
        //       unicos.push(metadata);
        //       continue;
        //     }

        //     if (!vistos.has(nasaId)) {
        //       // Primera vez que vemos este NASA_ID
        //       vistos.set(nasaId, true);
        //       unicos.push(metadata);
        //     } else {
        //       // Duplicado encontrado
        //       duplicados++;
        //       console.warn(`🔄 Duplicado detectado y eliminado: ${nasaId}`);
        //     }
        //   }

        //   ipcRenderer.send("log_custom", {
        //     section: "Deduplicación",
        //     message: `Metadatos únicos: ${unicos.length}, Duplicados eliminados: ${duplicados}`,
        //     level: "INFO",
        //     file: LOG_PATH
        //   });

        //   console.log(` Deduplicación completada: ${unicos.length} únicos, ${duplicados} duplicados eliminados`);

        //   return unicos;
        // },
        // Reemplaza la función deduplicarMetadatos existente con esta versión:
        deduplicarMetadatos(datos) {
          const vistos = new Map();
          const unicos = [];
          let duplicados = 0;

          for (const item of datos) {
            //  DETECTAR AUTOMÁTICAMENTE EL FORMATO
            let nasaId = null;

            // Formato 1: Metadatos procesados (tienen NASA_ID directamente)
            if (item.NASA_ID) {
              nasaId = item.NASA_ID;
            }
            // Formato 2: Resultados de API (tienen images.filename)
            else if (item["images.filename"]) {
              nasaId = item["images.filename"].split(".")[0];
            }
            // Formato 3: Resultados normalizados (sin prefijo)
            else if (item.filename) {
              nasaId = item.filename.split(".")[0];
            }

            if (!nasaId || nasaId === "Sin_ID") {
              // Mantener elementos sin NASA_ID válido
              unicos.push(item);
              continue;
            }

            if (!vistos.has(nasaId)) {
              // Primera vez que vemos este NASA_ID
              vistos.set(nasaId, true);
              unicos.push(item);
            } else {
              // Duplicado encontrado
              duplicados++;
              console.warn(`🔄 Duplicado detectado y eliminado: ${nasaId}`);
            }
          }

          //  LOGGING INTELIGENTE según el contexto
          const contexto = datos.length > 0 && datos[0].NASA_ID ? "Metadatos" : "Resultados API";

          ipcRenderer.send("log_custom", {
            section: `Deduplicación ${contexto}`,
            message: `Elementos únicos: ${unicos.length}, Duplicados eliminados: ${duplicados}`,
            level: "INFO",
            file: LOG_PATH
          });

          console.log(` Deduplicación de ${contexto} completada: ${unicos.length} únicos, ${duplicados} duplicados eliminados`);

          return unicos;
        },
        //  MÉTODO CORREGIDO: descargarAhora con deduplicación
        //  MÉTODO descargarAhora COMPLETAMENTE CORREGIDO
        async descargarAhora() {
          //  VERIFICAR SI HAY IMÁGENES NUEVAS
          if (this.todasEnBD || this.resultadosNuevos.length === 0) {
            alert(" No hay imágenes nuevas para descargar. Todas ya están en la base de datos.");
            return;
          }

          //  USAR SOLO IMÁGENES NUEVAS (aplicar límite si está configurado)
          let imagenesToProcess;
          if (this.limiteDescarga > 0 && this.limiteDescarga < this.resultadosNuevos.length) {
            imagenesToProcess = this.resultadosNuevos.slice(0, this.limiteDescarga);
            console.log(`🔍 DESCARGA: Aplicando límite - Procesando ${imagenesToProcess.length} de ${this.resultadosNuevos.length} imágenes nuevas`);
          } else {
            imagenesToProcess = [...this.resultadosNuevos]; // Todas las nuevas
            console.log(`🔍 DESCARGA: Sin límite - Procesando todas las ${imagenesToProcess.length} imágenes nuevas`);
          }

          const outputPath = path.join(__dirname, "..", "metadatos_periodicos.json");

          //  INICIALIZAR VARIABLES DE PROGRESO
          this.descargandoDirecto = true;
          this.progresoDescarga = 0;
          this.totalImagenes = imagenesToProcess.length;
          this.imagenesDescargadas = 0;
          this.tiempoDescarga = 0;
          this.estadoDescarga = 'processing';
          this.mensajeEstado = `Procesando ${imagenesToProcess.length} imágenes nuevas...`;

          this.cerrarModalAcciones();

          //  LIMPIAR TIMER ANTERIOR
          if (this.intervaloTiempo) {
            clearInterval(this.intervaloTiempo);
          }

          //  INICIAR CRONÓMETRO
          this.intervaloTiempo = setInterval(() => {
            this.tiempoDescarga++;
          }, 1000);

          //  INICIALIZAR NPROGRESS
          NProgress.start();

          ipcRenderer.send("log_custom", {
            section: "Inicio Descarga Manual",
            message: `Iniciando descarga manual de ${imagenesToProcess.length} imágenes nuevas`,
            level: "INFO",
            file: LOG_PATH
          });

          const findBySuffix = (obj, suffix, fallback = null) => {
            for (const key in obj) {
              if (key.endsWith(suffix) && obj[key] != null && obj[key] !== "") {
                return obj[key];
              }
            }
            return fallback;
          };

          // Cache para evitar llamadas duplicadas
          const metadataCache = new Map();
          const nadirAltCache = new Map();
          const self = this;

          //  FUNCIÓN PROCESAMIENTO OPTIMIZADA
          const processPhotoOptimized = async (photo) => {
            try {
              const filename = findBySuffix(photo, ".filename");
              const directory = findBySuffix(photo, ".directory");

              if (!filename) {
                console.warn(" Sin filename:", photo);
                return null;
              }

              const rawDate = findBySuffix(photo, ".pdate", "");
              const rawTime = findBySuffix(photo, ".ptime", "");
              const formattedDate = rawDate.length === 8 ? `${rawDate.slice(0, 4)}.${rawDate.slice(4, 6)}.${rawDate.slice(6, 8)}` : "";
              const formattedHour = rawTime.length === 6 ? `${rawTime.slice(0, 2)}:${rawTime.slice(2, 4)}:${rawTime.slice(4, 6)}` : "";

              const width = findBySuffix(photo, ".width", "");
              const height = findBySuffix(photo, ".height", "");
              const resolucionTexto = (width && height) ? `${width} x ${height} pixels` : "";

              const cameraCode = findBySuffix(photo, ".camera", "Desconocida");
              const cameraDesc = cameraMap[cameraCode] || "Desconocida";

              const filmCode = findBySuffix(photo, ".film", "UNKN");
              const filmData = filmMap[filmCode] || { type: "Desconocido", description: "Desconocido" };

              const nasaId = filename?.split(".")[0] || "Sin_ID";

              if (!nasaId || nasaId === "Sin_ID") {
                console.warn(" NASA_ID inválido:", nasaId, "filename:", filename);
                return null;
              }

              //  USAR CACHE PARA OPTIMIZAR
              let extraData = nadirAltCache.get(nasaId);
              let camaraMetadataPath = metadataCache.get(nasaId);

              if (!extraData || !camaraMetadataPath) {
                const promises = [];

                if (!extraData) {
                  promises.push(self.obtenerNadirAltitudCamaraOptimized(nasaId));
                } else {
                  promises.push(Promise.resolve(extraData));
                }

                if (!camaraMetadataPath) {
                  promises.push(self.obtenerCamaraMetadataOptimized(nasaId));
                } else {
                  promises.push(Promise.resolve(camaraMetadataPath));
                }

                try {
                  const [newExtraData, newCamaraMetadataPath] = await Promise.all(promises);

                  if (!extraData) {
                    extraData = newExtraData || {
                      NADIR_CENTER: null,
                      ALTITUD: null,
                      CAMARA: null,
                      FECHA_CAPTURA: null,
                      GEOTIFF_URL: null,
                      HAS_GEOTIFF: false
                    };
                    nadirAltCache.set(nasaId, extraData);
                  }

                  if (!camaraMetadataPath) {
                    camaraMetadataPath = newCamaraMetadataPath;
                    metadataCache.set(nasaId, camaraMetadataPath);
                  }
                } catch (promiseError) {
                  console.warn(` Error en promises para ${nasaId}:`, promiseError.message);
                  extraData = {
                    NADIR_CENTER: null,
                    ALTITUD: null,
                    CAMARA: null,
                    FECHA_CAPTURA: null,
                    GEOTIFF_URL: null,
                    HAS_GEOTIFF: false
                  };
                  camaraMetadataPath = null;
                }
              }

              //  DETERMINAR CÁMARA
              let camera = null;
              if (cameraDesc.includes("Desconocida") || cameraDesc.includes("Desconocido") || cameraDesc.includes("Unspecified : ")) {
                camera = extraData?.CAMARA || "Desconocida";
              } else {
                camera = cameraDesc;
              }

              //  URL INTELIGENTE: GeoTIFF si disponible, sino JPG
              let finalImageUrl;
              if (extraData?.HAS_GEOTIFF && extraData?.GEOTIFF_URL) {
                finalImageUrl = extraData.GEOTIFF_URL;
                console.log(`🗺️ Usando GeoTIFF para ${nasaId}`);
              } else {
                finalImageUrl = filename && directory ? `https://eol.jsc.nasa.gov/DatabaseImages/${directory}/${filename}` : null;
                console.log(`📷 Usando JPG para ${nasaId}`);
              }

              const fechaFinal = extraData?.FECHA_CAPTURA || formattedDate;

              const resultado = {
                NASA_ID: nasaId,
                FECHA: fechaFinal,
                HORA: formattedHour,
                RESOLUCION: resolucionTexto,
                URL: finalImageUrl,
                NADIR_LAT: findBySuffix(photo, ".nlat"),
                NADIR_LON: findBySuffix(photo, ".nlon"),
                CENTER_LAT: findBySuffix(photo, ".lat"),
                CENTER_LON: findBySuffix(photo, ".lon"),
                NADIR_CENTER: extraData?.NADIR_CENTER || null,
                ALTITUD: extraData?.ALTITUD || null,
                LUGAR: findBySuffix(photo, ".geon", ""),
                ELEVACION_SOL: findBySuffix(photo, ".elev", ""),
                AZIMUT_SOL: findBySuffix(photo, ".azi", ""),
                COBERTURA_NUBOSA: findBySuffix(photo, ".cldp", ""),
                CAMARA: camera,
                LONGITUD_FOCAL: findBySuffix(photo, ".fclt"),
                INCLINACION: findBySuffix(photo, ".tilt"),
                FORMATO: `${filmData.type}: ${filmData.description}`,
                CAMARA_METADATA: camaraMetadataPath
              };

              console.log(` Procesado: ${nasaId} - URL: ${finalImageUrl ? 'SI' : 'NO'} - Fecha: ${fechaFinal}`);
              return resultado;

            } catch (error) {
              console.error(` Error procesando foto:`, error);
              return null;
            }
          };

          try {
            //  FASE 1: PROCESAR METADATOS CON PROGRESO REAL
            this.estadoDescarga = 'processing';
            this.mensajeEstado = 'Procesando metadatos de imágenes...';

            ipcRenderer.send("log_custom", {
              section: "Fase 1 - Procesamiento",
              message: `FASE 1: Procesando ${imagenesToProcess.length} metadatos con paralelización optimizada`,
              level: "INFO",
              file: LOG_PATH
            });

            const CONCURRENT_LIMIT = 10;
            const metadatos = [];
            let procesados = 0;

            //  FUNCIÓN DE PROCESAMIENTO CON LÍMITE DE CONCURRENCIA Y PROGRESO
            const processWithConcurrencyLimit = async (items, processor, limit) => {
              const results = [];

              for (let i = 0; i < items.length; i += limit) {
                const batch = items.slice(i, i + limit);
                const batchNum = Math.floor(i / limit) + 1;
                const totalBatches = Math.ceil(items.length / limit);

                console.log(`📦 Procesando lote ${batchNum}/${totalBatches}: elementos ${i} a ${Math.min(i + limit - 1, items.length - 1)}`);

                //  ACTUALIZAR MENSAJE DE ESTADO CON PROGRESO DETALLADO
                this.mensajeEstado = `Procesando metadatos... Lote ${batchNum} de ${totalBatches} (${Math.floor((procesados / items.length) * 100)}%)`;

                const batchResults = await Promise.allSettled(batch.map(processor));

                batchResults.forEach((result, index) => {
                  if (result.status === 'fulfilled') {
                    const data = result.value;
                    if (data && data.NASA_ID) {
                      results.push(data);
                      console.log(` Procesado exitosamente: ${data.NASA_ID}`);
                    } else {
                      console.log(` Resultado sin NASA_ID válido:`, data);
                    }
                  } else {
                    const item = batch[index];
                    const nasaId = item?.["images.filename"]?.split(".")[0] || `item_${i + index}`;

                    ipcRenderer.send("log_custom", {
                      message: `Error procesando ${nasaId}: ${result.reason?.message || 'Error desconocido'}`,
                      level: "ERROR",
                      file: LOG_PATH
                    });
                  }
                });

                procesados = Math.min(i + limit, items.length);

                //  PROGRESO REAL DE FASE 1: 30% del total
                const progresoFase1 = procesados / items.length;
                const progresoTotal = progresoFase1 * 0.3; // FASE 1 = 30% del progreso total

                //  ACTUALIZAR VARIABLES DE UI EN TIEMPO REAL
                this.progresoDescarga = Math.floor(progresoTotal * 100);
                this.imagenesDescargadas = Math.floor(progresoTotal * this.totalImagenes);

                NProgress.set(progresoTotal);

                // Log cada 5 lotes o al final
                if (batchNum % 5 === 0 || procesados >= items.length) {
                  ipcRenderer.send("log_custom", {
                    message: `Procesados ${procesados} de ${items.length} metadatos (${Math.floor(progresoFase1 * 100)}%) - Lote ${batchNum}/${totalBatches}`,
                    level: "INFO",
                    file: LOG_PATH
                  });
                }

                // Pequeña pausa entre lotes para no saturar
                if (i + limit < items.length) {
                  await new Promise(resolve => setTimeout(resolve, 100));
                }
              }
              return results;
            };

            //  PROCESAR TODAS LAS IMÁGENES
            const metadatosCompletos = await processWithConcurrencyLimit(
              imagenesToProcess,
              processPhotoOptimized,
              CONCURRENT_LIMIT
            );

            metadatos.push(...metadatosCompletos);

            console.log(`📊 RESUMEN FASE 1 (ANTES de deduplicación): ${metadatos.length} metadatos procesados de ${imagenesToProcess.length} intentados`);

            //  APLICAR DEDUPLICACIÓN
            this.mensajeEstado = 'Eliminando duplicados...';
            const metadatosUnicos = this.deduplicarMetadatos(metadatos);

            console.log(`📊 RESUMEN FASE 1 (DESPUÉS de deduplicación): ${metadatosUnicos.length} metadatos únicos`);

            //  GUARDAR JSON CON METADATOS ÚNICOS
            if (metadatosUnicos.length > 0) {
              this.mensajeEstado = 'Guardando metadatos únicos...';

              fs.writeFileSync(outputPath, JSON.stringify(metadatosUnicos, null, 2), "utf-8");

              ipcRenderer.send("log_custom", {
                message: `FASE 1 COMPLETADA: JSON guardado con ${metadatosUnicos.length} entradas únicas (eliminados ${metadatos.length - metadatosUnicos.length} duplicados)`,
                level: "INFO",
                file: LOG_PATH
              });

              console.log(`💾 JSON guardado exitosamente con metadatos únicos: ${outputPath}`);
              console.log(`📝 Primeros 3 metadatos únicos:`, metadatosUnicos.slice(0, 3));
            } else {
              throw new Error("No se generaron metadatos únicos válidos para guardar");
            }

            //  FASE 2: DESCARGA REAL
            this.estadoDescarga = 'downloading';
            this.mensajeEstado = 'Iniciando descarga de imágenes...';

            ipcRenderer.send("log_custom", {
              message: `FASE 2: Iniciando descarga de ${metadatosUnicos.length} imágenes únicas`,
              level: "INFO",
              file: LOG_PATH
            });

            //  ACTUALIZAR VARIABLES PARA FASE 2
            this.totalImagenes = metadatosUnicos.length;
            this.imagenesDescargadas = 0;

            //  LISTENERS PARA PROGRESO DE PYTHON
            const progressListener = (event, progressData) => {
              console.log('📊 Progreso recibido:', progressData);

              if (typeof progressData === 'object' && progressData.porcentaje !== undefined) {
                const porcentaje = progressData.porcentaje;
                const descargadas = progressData.descargadas || 0;
                const total = progressData.total || this.totalImagenes;

                // Convertir progreso de Python (0-100%) a progreso total (30%-100%)
                const progresoFase2 = porcentaje / 100; // 0.0 a 1.0
                const progresoTotalReal = 0.3 + (progresoFase2 * 0.7); // De 30% a 100%

                //  ACTUALIZAR MENSAJE CON PROGRESO DETALLADO
                this.mensajeEstado = `Descargando imágenes... ${porcentaje}% (${descargadas}/${total})`;

                // Actualizar NProgress
                NProgress.set(progresoTotalReal);

                // Actualizar variables de interfaz
                this.progresoDescarga = Math.floor(progresoTotalReal * 100);
                this.imagenesDescargadas = descargadas;

                // Log cada 25%
                if (porcentaje % 25 === 0 || porcentaje === 100) {
                  ipcRenderer.send("log_custom", {
                    message: `Progreso descarga: ${porcentaje}% (${descargadas}/${total} imágenes)`,
                    level: "INFO",
                    file: LOG_PATH
                  });
                }
              } else if (typeof progressData === 'number') {
                // Fallback para formato anterior
                const porcentaje = progressData;
                const progresoFase2 = porcentaje / 100;
                const progresoTotalReal = 0.3 + (progresoFase2 * 0.7);

                this.mensajeEstado = `Descargando imágenes... ${porcentaje}%`;
                NProgress.set(progresoTotalReal);
                this.progresoDescarga = Math.floor(progresoTotalReal * 100);
                this.imagenesDescargadas = Math.floor((porcentaje / 100) * this.totalImagenes);
              }
            };

            const completeListener = async () => {
              //  COMPLETAR DESCARGA
              this.estadoDescarga = 'completed';
              this.mensajeEstado = 'Descarga completada exitosamente';

              NProgress.done();
              this.descargandoDirecto = false;
              this.progresoDescarga = 100;
              this.imagenesDescargadas = this.totalImagenes;

              // Limpiar cronómetro
              if (this.intervaloTiempo) {
                clearInterval(this.intervaloTiempo);
                this.intervaloTiempo = null;
              }

              // Remover listeners
              ipcRenderer.removeListener('progreso-descarga', progressListener);
              ipcRenderer.removeListener('descarga-completa', completeListener);

              ipcRenderer.send("log_custom", {
                section: "Descarga Completada",
                message: `PROCESO COMPLETADO: ${metadatos.length} metadatos procesados y descarga finalizada en ${this.tiempoDescargaFormato}`,
                level: "INFO",
                file: LOG_PATH
              });

              //  RESETEAR ESTADO DESPUÉS DE 3 SEGUNDOS
              setTimeout(() => {
                this.estadoDescarga = 'idle';
                this.mensajeEstado = '';
              }, 3000);

              //  RECARGAR LISTA AUTOMÁTICAMENTE
              try {
                ipcRenderer.send("log_custom", {
                  section: "Recarga Automática",
                  message: "Iniciando recarga automática de resultados",
                  level: "INFO",
                  file: LOG_PATH
                });

                await this.fetchData(true); // Recarga automática

                ipcRenderer.send("log_custom", {
                  section: "Recarga Completada",
                  message: "Lista de resultados actualizada exitosamente",
                  level: "INFO",
                  file: LOG_PATH
                });

                //  MOSTRAR NOTIFICACIÓN DE ÉXITO
                this.mostrarNotificacionExito(metadatos.length);

              } catch (error) {
                ipcRenderer.send("log_custom", {
                  section: "Error Recarga",
                  message: `Error recargando lista: ${error.message}`,
                  level: "ERROR",
                  file: LOG_PATH
                });

                console.error('Error recargando lista:', error);
                alert(` Descarga completada, pero hubo un error al recargar la lista: ${error.message}`);
              }
            };

            //  REGISTRAR LISTENERS
            ipcRenderer.on('progreso-descarga', progressListener);
            ipcRenderer.on('descarga-completa', completeListener);

            //  INVOCAR DESCARGA REAL DE PYTHON
            console.log(' Invocando descarga desde Python...');
            const response = await ipcRenderer.invoke("descargarDirecto");

            console.log(" Descarga invoke completado:", response);

          } catch (err) {
            //  LIMPIAR EN CASO DE ERROR
            NProgress.done();
            this.descargandoDirecto = false;
            this.progresoDescarga = 0;
            this.estadoDescarga = 'idle';
            this.mensajeEstado = '';

            if (this.intervaloTiempo) {
              clearInterval(this.intervaloTiempo);
              this.intervaloTiempo = null;
            }

            // Remover listeners en caso de error
            ipcRenderer.removeAllListeners('progreso-descarga');
            ipcRenderer.removeAllListeners('descarga-completa');

            console.error(" ERROR COMPLETO:", err);

            ipcRenderer.send("log_custom", {
              message: `Error durante descarga manual: ${err.message}`,
              level: "ERROR",
              file: LOG_PATH
            });

            alert(" Error al procesar: " + err.message);
          }
        }

        ,

        //  MÉTODO getOutputFolder ACTUALIZADO
        getOutputFolder() {
          //  USAR MISMA LÓGICA QUE PYTHON
          const nasPath = "/mnt/nas";  // Cambiar según rutas.py
          const localPath = path.join(__dirname, "..", "backend", "API-NASA", "camera_data");

          const canWriteTo = (dir) => {
            try {
              fs.accessSync(dir, fs.constants.W_OK);
              return true;
            } catch {
              return false;
            }
          };

          //  VERIFICAR NAS IGUAL QUE EN PYTHON
          const nasCameraPath = path.join(nasPath, "camera_data");
          const useNas = fs.existsSync(nasCameraPath) &&
            fs.lstatSync(nasCameraPath).isDirectory() &&
            canWriteTo(nasCameraPath);


          const finalPath = useNas ? path.join(nasPath, "camera_data") : localPath;
          const modo = useNas ? "PRODUCCIÓN (NAS)" : "DESARROLLO (Local - solo pruebas)";

          try {
            fs.mkdirSync(finalPath, { recursive: true });

            //  LOG COHERENTE CON PYTHON
            if (!this.carpetaSalidaLogged) {
              ipcRenderer.send("log_custom", {
                section: "Configuración",
                message: `Camera metadata - ${modo}: ${finalPath}`,
                level: useNas ? "INFO" : "WARNING",
                file: LOG_PATH
              });
              this.carpetaSalidaLogged = true;
            }
          } catch (err) {
            ipcRenderer.send("log_custom", {
              section: "Error Configuración",
              message: `No se pudo crear directorio en ${finalPath}: ${err.message}`,
              level: "ERROR",
              file: LOG_PATH
            });
          }

          return finalPath;
        },


        //  MÉTODO fetchData CORREGIDO - Sin logs duplicados
        // async fetchData(esRecargaAutomatica = false) {
        //   // if (esRecargaAutomatica) {
        //   //   this.mostrarIndicadorRecarga();
        //   // }

        //   this.aplicarCamposDefault();

        //   if (!this.allFiltersValid) {
        //     alert("Todos los filtros deben estar completos y tener caracteres válidos.");
        //     return;
        //   }

        //   const seccionLog = esRecargaAutomatica ? "Recarga Automática" : "Búsqueda Manual";
        //   const mensajeLog = esRecargaAutomatica
        //     ? "Recargando imágenes después de descarga"
        //     : "Iniciando búsqueda de imágenes";

        //   ipcRenderer.send("log_custom", {
        //     section: seccionLog,
        //     message: mensajeLog,
        //     level: "INFO",
        //     file: LOG_PATH
        //   });

        //   //  ACTIVAR LOADING CORRECTAMENTE
        //   this.isLoading = true;
        //   this.searchPerformed = false; // Ocultar panel mientras carga

        //   //  LIMPIAR MAPA Y RESULTADOS
        //   window.mapHelpers.clearMap(this.map, this.markers);
        //   this.results = [];
        //   this.resultadosNuevos = [];

        //   const coordSources = ["frames", "nadir", "mlcoord"];
        //   const allResults = [];

        //   for (const source of coordSources) {
        //     let consultas = [];

        //     if (this.modoNocturno) {
        //       if (source === "frames" || source === "nadir") {
        //         consultas = [
        //           { operator1: "ge", value1: "003000", operator2: "le", value2: "045959" },
        //           { operator1: "ge", value1: "050000", operator2: "le", value2: "103000" }
        //         ];
        //       } else {
        //         consultas = [{ operator1: null, value1: null, operator2: null, value2: null }];
        //       }
        //     } else {
        //       consultas = [{ operator1: null, value1: null, operator2: null, value2: null }];
        //     }

        //     for (const nocturna of consultas) {
        //       let filtrosActuales = [...this.filters];

        //       if (nocturna.operator1 && nocturna.operator2 && (source === "frames" || source === "nadir")) {
        //         filtrosActuales = filtrosActuales.filter(f => !(f.table === source && f.field === "ptime"));
        //         filtrosActuales.push(
        //           { table: source, field: "ptime", operator: nocturna.operator1, value: nocturna.value1 },
        //           { table: source, field: "ptime", operator: nocturna.operator2, value: nocturna.value2 }
        //         );
        //       }

        //       const queryString = window.queryBuilder.buildQuery(filtrosActuales, source, this.boundingBox);
        //       const returnParams = window.queryBuilder.buildReturn(this.returnFieldsSelected, source);
        //       const apiUrl = `https://eol.jsc.nasa.gov/SearchPhotos/PhotosDatabaseAPI/PhotosDatabaseAPI.pl?query=${queryString}&return=${returnParams}&key=${config.NASA_API_KEY}`;

        //       await this.procesarConsulta(apiUrl, source, allResults);
        //     }
        //   }

        //   try {
        //     //  DEDUPLICAR Y ASIGNAR RESULTADOS
        //     const allResultsUnicos = this.deduplicarMetadatos(allResults);
        //     this.results = allResultsUnicos;
        //     this.searchPerformed = true;
        //     this.showResultsPanel = true;

        //     //  UN SOLO LOG FINAL (eliminar duplicados)
        //     const mensajeResultado = esRecargaAutomatica
        //       ? `Recarga completada: ${allResultsUnicos.length} resultados únicos obtenidos`
        //       : `Búsqueda completada: ${allResultsUnicos.length} resultados únicos obtenidos`;

        //     ipcRenderer.send("log_custom", {
        //       section: seccionLog,
        //       message: mensajeResultado,
        //       level: "INFO",
        //       file: LOG_PATH
        //     });

        //     // Agregar marcadores al mapa
        //     if (this.results.length > 0 && this.map) {
        //       const { markers, clusterGroup } = window.mapHelpers.addMarkersToMap(this.map, this.results);
        //       this.markers = markers;
        //       this.clusterGroup = clusterGroup;
        //     }

        //     this.isLoading = false;

        //     if (esRecargaAutomatica) {
        //       this.ocultarIndicadorRecarga();
        //     }

        //   } catch (error) {
        //     this.isLoading = false;

        //     if (esRecargaAutomatica) {
        //       this.ocultarIndicadorRecarga();
        //     }

        //     ipcRenderer.send("log_custom", {
        //       section: seccionLog,
        //       message: `Error durante ${esRecargaAutomatica ? 'recarga' : 'búsqueda'}: ${error.message}`,
        //       level: "ERROR",
        //       file: LOG_PATH
        //     });

        //     throw error;
        //   }
        // },
        //  MODIFICAR fetchData para manejar loading correctamente
        async fetchData(esRecargaAutomatica = false) {
          this.aplicarCamposDefault();

          if (!this.allFiltersValid) {
            alert("Todos los filtros deben estar completos y tener caracteres válidos.");
            return;
          }

          const seccionLog = esRecargaAutomatica ? "Recarga Automática" : "Búsqueda Manual";
          const mensajeLog = esRecargaAutomatica
            ? "Recargando imágenes después de descarga"
            : "Iniciando búsqueda de imágenes";

          ipcRenderer.send("log_custom", {
            section: seccionLog,
            message: mensajeLog,
            level: "INFO",
            file: LOG_PATH
          });

          //  ACTIVAR LOADING CORRECTAMENTE
          this.isLoading = true;
          this.searchPerformed = false; // Ocultar panel mientras carga

          //  LIMPIAR MAPA Y RESULTADOS
          window.mapHelpers.clearMap(this.map, this.markers);
          this.results = [];
          this.resultadosNuevos = [];

          const coordSources = ["frames", "nadir", "mlcoord"];
          const allResults = [];

          try {
            // ... lógica de consultas existente sin cambios ...
            for (const source of coordSources) {
              let consultas = [];

              if (this.modoNocturno) {
                if (source === "frames" || source === "nadir") {
                  consultas = [
                    { operator1: "ge", value1: "003000", operator2: "le", value2: "045959" },
                    { operator1: "ge", value1: "050000", operator2: "le", value2: "103000" }
                  ];
                } else {
                  consultas = [{ operator1: null, value1: null, operator2: null, value2: null }];
                }
              } else {
                consultas = [{ operator1: null, value1: null, operator2: null, value2: null }];
              }

              for (const nocturna of consultas) {
                let filtrosActuales = [...this.filters];

                if (nocturna.operator1 && nocturna.operator2 && (source === "frames" || source === "nadir")) {
                  filtrosActuales = filtrosActuales.filter(f => !(f.table === source && f.field === "ptime"));
                  filtrosActuales.push(
                    { table: source, field: "ptime", operator: nocturna.operator1, value: nocturna.value1 },
                    { table: source, field: "ptime", operator: nocturna.operator2, value: nocturna.value2 }
                  );
                }

                const queryString = window.queryBuilder.buildQuery(filtrosActuales, source, this.boundingBox);
                const returnParams = window.queryBuilder.buildReturn(this.returnFieldsSelected, source);
                const apiUrl = `https://eol.jsc.nasa.gov/SearchPhotos/PhotosDatabaseAPI/PhotosDatabaseAPI.pl?query=${queryString}&return=${returnParams}&key=${config.NASA_API_KEY}`;

                await this.procesarConsulta(apiUrl, source, allResults);
              }
            }

            //  PROCESAR RESULTADOS
            const allResultsUnicos = this.deduplicarMetadatos(allResults);
            this.results = allResultsUnicos;

            //  VERIFICAR NASA_IDs AUTOMÁTICAMENTE
            if (this.results.length > 0) {
              await this.verificarNasaIdsEnBD();
            }

            //  RESETEAR VISTA A 'TODAS' EN NUEVA BÚSQUEDA
            this.vistaFiltro = 'todas';
            this.currentPage = 1;

            this.searchPerformed = true;
            this.showResultsPanel = true;

            const mensajeResultado = esRecargaAutomatica
              ? `Recarga completada: ${allResultsUnicos.length} resultados únicos obtenidos`
              : `Búsqueda completada: ${allResultsUnicos.length} resultados únicos obtenidos`;

            ipcRenderer.send("log_custom", {
              section: seccionLog,
              message: mensajeResultado,
              level: "INFO",
              file: LOG_PATH
            });

            //  AÑADIR MARCADORES AL MAPA (todos inicialmente)
            if (this.results.length > 0 && this.map) {
              const { markers, clusterGroup } = window.mapHelpers.addMarkersToMap(this.map, this.results);
              this.markers = markers;
              this.clusterGroup = clusterGroup;
            }

          } catch (error) {
            ipcRenderer.send("log_custom", {
              section: seccionLog,
              message: `Error durante ${esRecargaAutomatica ? 'recarga' : 'búsqueda'}: ${error.message}`,
              level: "ERROR",
              file: LOG_PATH
            });

            this.results = [];
            this.resultadosNuevos = [];
            throw error;
          } finally {
            //  DESACTIVAR LOADING SIEMPRE
            this.isLoading = false;
          }
        },

        async procesarConsulta(apiUrl, source, allResults) {
          try {
            const response = await fetch(apiUrl);
            if (!response.ok) throw new Error(`Error HTTP: ${response.status}`);

            const rawData = await response.json();
            if (!Array.isArray(rawData)) {
              ipcRenderer.send("log_custom", {
                message: `No se encontraron resultados para fuente: ${source}`,
                level: "WARNING",
                file: LOG_PATH
              });
              return;
            }

            //  PROCESAR TODOS LOS RESULTADOS SIN VERIFICAR NASA_ID
            const processedResults = rawData.map((photo) => {
              const normalized = {};
              for (const key in photo) {
                normalized[key.replace('|', '.')] = photo[key];
              }
              normalized.previewUrl = window.photoUtils.getImageUrl(normalized);
              normalized.coordSource = source;
              return normalized;
            });

            allResults.push(...processedResults);

          } catch (err) {
            ipcRenderer.send("log_custom", {
              message: `Error en la consulta ${source}: ${err.message}`,
              level: "ERROR",
              file: LOG_PATH
            });
          }
        },

        aplicarCamposDefault() {
          window.generalUtils.aplicarCamposDefault(this.returnFieldsSelected, this.tables);
        },

        formatFieldName: window.photoUtils.formatFieldName,
        getPhotoDetails: window.photoUtils.getPhotoDetails,

        async confirmarCrearCron() {
          await window.taskManager.confirmarCrearCron({
            filters: this.filters,
            selectedCoordSource: this.selectedCoordSource,
            returnFieldsSelected: this.returnFieldsSelected,
            allowedReturnTables: this.allowedReturnTables,
            cronHora: this.cronHora,
            cronFrecuencia: this.cronFrecuencia,
            cronIntervalo: this.cronIntervalo,
            resultados: this.results,
            boundingBox: this.boundingBox
          });
        },

        async eliminarTarea(index) {
          await window.taskManager.eliminarTarea(index, this.tareasPeriodicas);
        },

        handleWindowResize() {
          this.isPanelOpen = window.innerWidth > 992;
        },

        nextPage() {
          if (this.currentPage < this.totalPages) this.currentPage++;
        },

        prevPage() {
          if (this.currentPage > 1) this.currentPage--;
        },

        togglePanel() {
          this.isPanelOpen = !this.isPanelOpen;
        },

        abrirVentanaElectron() {
          window.open('https://eol.jsc.nasa.gov/SearchPhotos/PhotosDatabaseAPI/', '_blank');
        },

        getTotalSelectedFields() {
          let total = 0;
          for (const table in this.returnFieldsSelected) {
            total += this.returnFieldsSelected[table].length;
          }
          return total;
        },

        isAccordionOpen(table) {
          return this.accordionOpen === table;
        },

        isSelectedReturnField(table, field) {
          return this.returnFieldsSelected[table]?.includes(field);
        },

        addFilter() {
          this.filters.push({ table: "frames", field: "mission", operator: "like", value: "" });
        },

        removeFilter(index) {
          this.filters.splice(index, 1);
        },

        getAll(table) {
          return this.tables[table] || [];
        },

        tableParams(table) {
          return this.tables[table] || [];
        },

        isValidInput(value) {
          return validInputRegex.test(value);
        },

        abrirModalCron() {
          this.mostrarModalCron = true;
          this.cerrarModalAcciones();
        },

        cerrarModalCron() {
          this.mostrarModalCron = false;
        },

        selectImage(photo) {
          if (!this.map || !this.clusterGroup) {
            ipcRenderer.send("log_custom", {
              message: "Mapa o clusterGroup no inicializados",
              level: "WARNING",
              file: LOG_PATH
            });
            return;
          }

          const lat = parseFloat(photo[`${this.selectedCoordSource}.lat`]);
          const lon = parseFloat(photo[`${this.selectedCoordSource}.lon`]);

          if (!isNaN(lat) && !isNaN(lon)) {
            const markerEntry = this.markers.find(m =>
              Math.abs(m.lat - lat) < 0.0001 &&
              Math.abs(m.lon - lon) < 0.0001
            );

            if (markerEntry) {
              const marker = markerEntry.marker;
              const handleAdd = () => {
                marker.openPopup();
                marker.off("add", handleAdd);
              };
              marker.on("add", handleAdd);
              this.clusterGroup.zoomToShowLayer(marker);
            } else {
              ipcRenderer.send("log_custom", {
                message: "No se encontró el marcador para abrir",
                level: "WARNING",
                file: LOG_PATH
              });
            }
          }
        },

        actualizarBoundingBox(nuevoBox) {
          this.boundingBox = nuevoBox;

          const otrosFiltros = this.filters.filter(f =>
            !(f.field === "lat" || f.field === "lon")
          );

          const nuevosFiltrosLatLon = [
            { table: this.selectedCoordSource, field: "lat", operator: "ge", value: this.boundingBox.latMin.toString() },
            { table: this.selectedCoordSource, field: "lat", operator: "le", value: this.boundingBox.latMax.toString() },
            { table: this.selectedCoordSource, field: "lon", operator: "ge", value: this.boundingBox.lonMin.toString() },
            { table: this.selectedCoordSource, field: "lon", operator: "le", value: this.boundingBox.lonMax.toString() }
          ];

          this.filters = [...otrosFiltros, ...nuevosFiltrosLatLon];
          this.aplicarCamposDefault();

          ipcRenderer.send("log_custom", {
            message: `Bounding Box actualizado y filtros aplicados. Lat: ${this.boundingBox.latMin}-${this.boundingBox.latMax}, Lon: ${this.boundingBox.lonMin}-${this.boundingBox.lonMax}`,
            level: "INFO",
            file: LOG_PATH
          });
        },

        guardarBoundingBox() {
          alert(`Bounding Box actual:\nLat: ${this.boundingBox.latMin} - ${this.boundingBox.latMax}\nLon: ${this.boundingBox.lonMin} - ${this.boundingBox.lonMax}`);
        },

        convertirUTCaLocal(ptimeUTC) {
          if (!ptimeUTC || ptimeUTC.length !== 6) return "Hora inválida";

          const horasUTC = parseInt(ptimeUTC.substring(0, 2), 10);
          const minutosUTC = parseInt(ptimeUTC.substring(2, 4), 10);
          const segundosUTC = parseInt(ptimeUTC.substring(4, 6), 10);

          const fechaUTC = new Date(Date.UTC(1970, 0, 1, horasUTC, minutosUTC, segundosUTC));
          fechaUTC.setUTCHours(fechaUTC.getUTCHours() - 5);

          let horasLocal = fechaUTC.getUTCHours();
          const minutosLocal = fechaUTC.getUTCMinutes().toString().padStart(2, '0');
          const segundosLocal = fechaUTC.getUTCSeconds().toString().padStart(2, '0');

          let periodoTexto = "";
          if (horasLocal >= 6 && horasLocal < 12) {
            periodoTexto = "de la mañana";
          } else if (horasLocal >= 12 && horasLocal < 19) {
            periodoTexto = "de la tarde";
          } else {
            periodoTexto = "de la noche";
          }

          let horas12 = horasLocal % 12;
          if (horas12 === 0) horas12 = 12;

          const horasStr = horas12.toString().padStart(2, '0');
          return `Hora Local: ${horasStr}:${minutosLocal}:${segundosLocal} ${periodoTexto}`;
        },

        // 4. MODIFICAR abrirModalAcciones para incluir verificación:
        async abrirModalAcciones() {
          this.mostrarModalAcciones = true;

          //  VERIFICAR NASA_IDs automáticamente al abrir acciones
          if (this.results.length > 0) {
            await this.verificarNasaIdsEnBD();
          }
        },

        cerrarModalAcciones() {
          this.mostrarModalAcciones = false;
        },

        actualizarTareasDesdeArchivo() {
          const fs = require("fs");
          const path = require("path");
          const ruta = path.join(__dirname, "tasks.json");

          try {
            const contenido = fs.readFileSync(ruta, "utf-8").trim();
            this.tareasPeriodicas = contenido ? JSON.parse(contenido) : [];
          } catch (err) {
            ipcRenderer.send("log_custom", {
              message: `Error al leer tareas: ${err.message}`,
              level: "ERROR",
              file: LOG_PATH
            });
            this.tareasPeriodicas = [];
          }
        },

        validarYCrearTarea() {
          if (this.validarCron()) {
            this.confirmarCrearCron();
          }
        },

        validarCron() {
          if (!this.cronHora || this.cronHora.trim() === "") {
            alert("Debes especificar la hora de inicio.");
            return false;
          }

          if (!this.cronFrecuencia || this.cronFrecuencia.trim() === "") {
            alert("Debes seleccionar una frecuencia.");
            return false;
          }

          if (
            (this.cronFrecuencia === "MINUTE" || this.cronFrecuencia === "HOURLY") &&
            (!this.cronIntervalo || isNaN(this.cronIntervalo) || this.cronIntervalo < 1)
          ) {
            alert("Debes ingresar un intervalo válido (mayor que 0).");
            return false;
          }

          return true;
        },
        //  MODIFICAR EL MÉTODO DE CANCELAR DESCARGA PARA LIMPIAR ESTADO
        cancelarDescarga() {
          if (confirm('¿Estás seguro de que quieres cancelar la descarga?')) {
            // Limpiar variables de progreso
            this.descargandoDirecto = false;
            this.progresoDescarga = 0;
            this.imagenesDescargadas = 0;
            this.estadoDescarga = 'idle';
            this.mensajeEstado = '';

            // Limpiar cronómetro
            if (this.intervaloTiempo) {
              clearInterval(this.intervaloTiempo);
              this.intervaloTiempo = null;
            }

            // Remover listeners
            ipcRenderer.removeAllListeners('progreso-descarga');
            ipcRenderer.removeAllListeners('descarga-completa');

            // Completar NProgress
            NProgress.done();

            // Log de cancelación
            ipcRenderer.send("log_custom", {
              section: "Descarga Cancelada",
              message: "Usuario canceló la descarga manualmente",
              level: "WARNING",
              file: LOG_PATH
            });

            //  RECARGAR LISTA PARA MOSTRAR ESTADO ACTUAL
            setTimeout(async () => {
              try {
                await this.fetchData(true); // Recarga automática
                alert(' Descarga cancelada. Lista actualizada para mostrar estado actual.');
              } catch (error) {
                alert(' Descarga cancelada por el usuario');
              }
            }, 500);
          }
        },
        //  NUEVO MÉTODO: Mostrar notificación de éxito
        mostrarNotificacionExito(cantidadProcesada) {
          // Crear notificación visual atractiva
          const notification = document.createElement('div');
          notification.className = 'success-notification';
          notification.innerHTML = `
        <div class="notification-content">
            <div class="notification-icon"></div>
            <div class="notification-text">
                <h3>¡Descarga Completada!</h3>
                <p>${cantidadProcesada} imágenes procesadas exitosamente</p>
                <p>Lista actualizada automáticamente</p>
            </div>
            <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;

          // Añadir estilos CSS dinámicamente
          if (!document.getElementById('notification-styles')) {
            const styles = document.createElement('style');
            styles.id = 'notification-styles';
            styles.textContent = `
            .success-notification {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                background: linear-gradient(135deg, #4CAF50, #45a049);
                color: white;
                border-radius: 12px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);
                min-width: 350px;
                animation: slideInRight 0.5s ease-out, fadeOut 0.5s ease-in 4.5s forwards;
            }

            .notification-content {
                padding: 20px;
                display: flex;
                align-items: center;
                gap: 15px;
            }

            .notification-icon {
                font-size: 2rem;
                animation: bounce 1s ease-in-out infinite alternate;
            }

            .notification-text h3 {
                margin: 0 0 5px 0;
                font-size: 1.1rem;
                font-weight: bold;
            }

            .notification-text p {
                margin: 2px 0;
                font-size: 0.9rem;
                opacity: 0.9;
            }

            .notification-close {
                position: absolute;
                top: 10px;
                right: 15px;
                background: none;
                border: none;
                color: white;
                font-size: 1.5rem;
                cursor: pointer;
                opacity: 0.7;
                transition: opacity 0.3s;
            }

            .notification-close:hover {
                opacity: 1;
            }

            @keyframes slideInRight {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }

            @keyframes fadeOut {
                from { opacity: 1; }
                to { opacity: 0; }
            }

            @keyframes bounce {
                from { transform: scale(1); }
                to { transform: scale(1.1); }
            }
        `;
            document.head.appendChild(styles);
          }

          // Añadir al DOM
          document.body.appendChild(notification);

          // Auto-remover después de 5 segundos
          setTimeout(() => {
            if (notification.parentElement) {
              notification.remove();
            }
          }, 5000);

          // También mostrar alert tradicional como respaldo
          setTimeout(() => {
            alert(`Proceso completado exitosamente!\n\nMetadatos: ${cantidadProcesada} procesados\n Tiempo total: ${this.tiempoDescargaFormato}\n Descarga finalizada\n Lista actualizada automáticamente`);
          }, 1000);
        },
        //  NUEVO MÉTODO: Mostrar indicador sutil de recarga
        mostrarIndicadorRecarga() {
          // Crear indicador discreto
          const indicator = document.createElement('div');
          indicator.id = 'reload-indicator';
          indicator.innerHTML = `
        <div class="reload-content">
            <div class="reload-spinner"></div>
            <span>Actualizando lista...</span>
        </div>
    `;

          // Estilos para el indicador
          const styles = `
        #reload-indicator {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(33, 150, 243, 0.95);
            color: white;
            padding: 12px 20px;
            border-radius: 25px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 9999;
            font-size: 0.9rem;
            animation: fadeInUp 0.3s ease-out;
        }

        .reload-content {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .reload-spinner {
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255,255,255,0.3);
            border-top: 2px solid white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes fadeInUp {
            from { transform: translateX(-50%) translateY(20px); opacity: 0; }
            to { transform: translateX(-50%) translateY(0); opacity: 1; }
        }

        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
    `;

          // Añadir estilos si no existen
          if (!document.getElementById('reload-styles')) {
            const styleSheet = document.createElement('style');
            styleSheet.id = 'reload-styles';
            styleSheet.textContent = styles;
            document.head.appendChild(styleSheet);
          }

          document.body.appendChild(indicator);
        },

        //  NUEVO MÉTODO: Ocultar indicador de recarga
        ocultarIndicadorRecarga() {
          const indicator = document.getElementById('reload-indicator');
          if (indicator) {
            indicator.style.animation = 'fadeOutDown 0.3s ease-in forwards';
            setTimeout(() => {
              if (indicator.parentElement) {
                indicator.remove();
              }
            }, 300);
          }
        },

        //  MEJORAR: beforeUnmount para limpiar listeners
        beforeUnmount() {
          window.removeEventListener("resize", this.handleWindowResize);

          // Limpiar listeners de descarga
          ipcRenderer.removeAllListeners('progreso-descarga');
          ipcRenderer.removeAllListeners('descarga-completa');

          // Limpiar cronómetro si existe
          if (this.intervaloTiempo) {
            clearInterval(this.intervaloTiempo);
            this.intervaloTiempo = null;
          }
        },
        //  NUEVA FUNCIÓN: Verificar NASA_IDs contra BD
        async verificarNasaIdsEnBD() {
          this.verificandoNasaIds = true;
          this.resultadosNuevos = [];
          this.todasEnBD = false;

          ipcRenderer.send("log_custom", {
            section: "Verificación NASA_IDs",
            message: `Verificando ${this.results.length} NASA_IDs contra base de datos`,
            level: "INFO",
            file: LOG_PATH
          });

          try {
            const verificacionPromises = this.results.map(async (photo) => {
              const filename = photo["images.filename"];
              const nasaId = filename ? filename.replace(/\.[^/.]+$/, '') : null;

              if (!nasaId) {
                console.warn(` Resultado sin filename válido:`, photo);
                return null;
              }

              try {
                const existe = await ipcRenderer.invoke('verificar-nasa-id', nasaId);

                if (!existe) {
                  //  FILTRO ADICIONAL: Solo imágenes de alta resolución
                  const dir = (photo["images.directory"] || "").toLowerCase();
                  if (dir.includes("large") || dir.includes("highres")) {
                    return photo; // Imagen nueva y de alta resolución
                  }
                }
                return null; // Ya existe en BD o no es alta resolución
              } catch (err) {
                ipcRenderer.send("log_custom", {
                  message: `Error verificando NASA_ID ${nasaId}: ${err.message}`,
                  level: "ERROR",
                  file: LOG_PATH
                });
                return null;
              }
            });

            const resultados = await Promise.all(verificacionPromises);
            this.resultadosNuevos = resultados.filter(photo => photo !== null);

            //  DETERMINAR ESTADO
            if (this.resultadosNuevos.length === 0) {
              this.todasEnBD = true;
              ipcRenderer.send("log_custom", {
                section: "Verificación Completada",
                message: "Todas las imágenes ya están en la base de datos",
                level: "INFO",
                file: LOG_PATH
              });
            } else {
              this.todasEnBD = false;
              ipcRenderer.send("log_custom", {
                section: "Verificación Completada",
                message: `${this.resultadosNuevos.length} imágenes nuevas encontradas de ${this.results.length} totales`,
                level: "INFO",
                file: LOG_PATH
              });
            }

          } catch (error) {
            ipcRenderer.send("log_custom", {
              section: "Error Verificación",
              message: `Error durante verificación de NASA_IDs: ${error.message}`,
              level: "ERROR",
              file: LOG_PATH
            });
            this.resultadosNuevos = [];
            this.todasEnBD = false;
          }

          this.verificandoNasaIds = false;
        },
        // Verificar si una imagen es nueva (no está en BD)
        esImagenNueva(photo) {
          const filename = photo["images.filename"];
          const nasaId = filename ? filename.replace(/\.[^/.]+$/, '') : null;

          if (!nasaId) return false;

          return this.resultadosNuevos.some(nueva => {
            const nuevaFilename = nueva["images.filename"];
            const nuevaNasaId = nuevaFilename ? nuevaFilename.replace(/\.[^/.]+$/, '') : null;
            return nuevaNasaId === nasaId;
          });
        },
        getResultadosFiltrados() {
          switch (this.vistaFiltro) {
            case 'nuevas':
              return this.resultadosNuevos;
            case 'descargadas':
              return this.results.filter(photo => !this.esImagenNueva(photo));
            case 'todas':
            default:
              return this.results;
          }
        },
        //  RESETEAR PAGINACIÓN AL CAMBIAR FILTRO
        // cambiarVistaFiltro() {
        //   console.log('🔄 Cambiando filtro a:', this.vistaFiltro);
        //   console.log('📊 Total results:', this.results.length);
        //   console.log('🆕 Nuevos results:', this.resultadosNuevos.length);
        //   console.log(' Filtrados results:', this.resultadosFiltrados.length);
        //   this.currentPage = 1;

        //   //  ACTUALIZAR MAPA CON RESULTADOS FILTRADOS
        //   if (this.map && this.resultadosFiltrados.length > 0) {
        //     this.actualizarMapaConFiltros();
        //   } else if (this.map) {
        //     // Limpiar mapa si no hay resultados filtrados
        //     window.mapHelpers.clearMap(this.map, this.markers);
        //   }
        // },
        cambiarVistaFiltro() {
          this.currentPage = 1;
          this.$forceUpdate(); // Forzar actualización

          this.$nextTick(() => {
            if (this.map) {
              this.actualizarMapaConFiltros();
            }
          });
        },
        //  NUEVO MÉTODO: Actualizar mapa según filtro
        actualizarMapaConFiltros() {
          // Limpiar marcadores existentes
          window.mapHelpers.clearMap(this.map, this.markers);

          // Añadir solo marcadores de resultados filtrados
          if (this.resultadosFiltrados.length > 0) {
            const { markers, clusterGroup } = window.mapHelpers.addMarkersToMap(this.map, this.resultadosFiltrados);
            this.markers = markers;
            this.clusterGroup = clusterGroup;

            ipcRenderer.send("log_custom", {
              message: `Mapa actualizado con ${this.resultadosFiltrados.length} marcadores (filtro: ${this.vistaFiltro})`,
              level: "INFO",
              file: LOG_PATH
            });
          }
        },
      }
    });

    const vm = app.mount("#app");
    window.vueApp = vm;
  });
