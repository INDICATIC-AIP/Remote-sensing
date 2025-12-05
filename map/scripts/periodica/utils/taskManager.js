// const { ipcRenderer } = require('electron');
// const path = require('path');
// const fs = require('fs');

// window.taskManager = {
//   async confirmarCrearCron({
//     filters,
//     selectedCoordSource,
//     returnFieldsSelected,
//     allowedReturnTables,
//     cronHora,
//     cronFrecuencia,
//     cronIntervalo,
//     resultados,
//     boundingBox
//   }) {
//     if (!resultados || resultados.length === 0) {
//       alert("⚠️ No hay resultados para exportar.");
//       return;
//     }

//     const taskId = `task_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 5)}`;
//     const jsonPathHost = path.join(__dirname, "tasks.json");
//     const jsonPathWSL = "/home/jose/API-NASA/map/scripts/tasks.json";

//     const query = window.queryBuilder.buildQuery(filters, selectedCoordSource, boundingBox);
//     const retorno = window.queryBuilder.buildReturn(returnFieldsSelected, allowedReturnTables, selectedCoordSource);

//     const nuevaTarea = {
//       id: taskId,
//       query,
//       return: retorno,
//       hora: cronHora,
//       frecuencia: cronFrecuencia,
//       intervalo: cronIntervalo
//     };

//     try {
//       let tareas = [];

//       if (!fs.existsSync(jsonPathHost)) {
//         fs.writeFileSync(jsonPathHost, "[]", "utf-8");
//       }

//       const contenido = fs.readFileSync(jsonPathHost, "utf-8").trim();
//       tareas = contenido ? JSON.parse(contenido) : [];


//       const yaExiste = tareas.some(t =>
//         t.query === nuevaTarea.query &&
//         t.return === nuevaTarea.return &&
//         t.hora === nuevaTarea.hora &&
//         t.frecuencia === nuevaTarea.frecuencia &&
//         t.intervalo === nuevaTarea.intervalo
//       );
//       if (yaExiste) {
//         alert("⚠️ Ya existe una tarea idéntica.");
//         return;
//       }


//       tareas.push(nuevaTarea);
//       fs.writeFileSync(jsonPathHost, JSON.stringify(tareas, null, 2), "utf-8");

//       if (window.vueApp?.actualizarTareasDesdeArchivo) {
//         window.vueApp.actualizarTareasDesdeArchivo();
//       }

//       const payload = {
//         taskId,
//         jsonPath: jsonPathWSL,
//         hora: cronHora,
//         frecuencia: cronFrecuencia,
//         intervalo: cronIntervalo
//       };

//       const response = await ipcRenderer.invoke("crearTareaPeriodica", payload);
//       alert(response.message || "✅ Cron creado.");
//     } catch (err) {
//       console.error("❌ Error al guardar o programar tarea:", err);
//       alert("❌ Error creando tarea: " + err.message);
//     }
//   },

//   async eliminarTarea(index, tareasPeriodicas) {
//     const tarea = tareasPeriodicas[index];
//     if (!tarea || !tarea.id) {
//       alert("❌ Tarea inválida.");
//       return;
//     }

//     if (!confirm(`¿Eliminar tarea programada (${tarea.id})?`)) return;

//     try {
//       const response = await ipcRenderer.invoke("eliminarTareaWindows", tarea.id);
//       console.log(response.message);

//       const jsonPath = path.join(__dirname, "tasks.json");

//       let tareas = [];
//       if (fs.existsSync(jsonPath)) {
//         const contenido = fs.readFileSync(jsonPath, "utf-8").trim();
//         tareas = contenido ? JSON.parse(contenido) : [];
//       }

//       const nuevasTareas = tareas.filter(t => t.id !== tarea.id);
//       fs.writeFileSync(jsonPath, JSON.stringify(nuevasTareas, null, 2), "utf-8");

//       if (window.vueApp?.actualizarTareasDesdeArchivo) {
//         window.vueApp.actualizarTareasDesdeArchivo();
//       }
//     } catch (err) {
//       console.error("❌", err.message);
//       alert("❌ Error al eliminar tarea: " + err.message);
//     }
//   }
// };

const { ipcRenderer } = require('electron');
const path = require('path');
const fs = require('fs');

window.taskManager = {
  async confirmarCrearCron({
    filters,
    selectedCoordSource,
    returnFieldsSelected,
    allowedReturnTables,
    cronHora,
    cronFrecuencia,
    cronIntervalo,
    resultados,
    boundingBox
  }) {
    if (!resultados || resultados.length === 0) {
      alert("⚠️ No hay resultados para exportar.");
      return;
    }

    const taskId = `task_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 5)}`;
    const jsonPathHost = path.join(__dirname, "tasks.json");
    const jsonPathWSL = "/home/jose/API-NASA/map/scripts/tasks.json";

    // 🔥 CREAR MÚLTIPLES CONSULTAS - IGUAL QUE fetchData() con modo nocturno
    const coordSources = ["frames", "nadir", "mlcoord"];
    const consultas = [];

    for (const source of coordSources) {
      let consultasNocturnas = [];

      // 🔥 APLICAR MISMO FILTRO NOCTURNO QUE EN fetchData
      if (window.vueApp?.modoNocturno) {
        if (source === "frames" || source === "nadir") {
          consultasNocturnas = [
            { operator1: "ge", value1: "003000", operator2: "le", value2: "045959" },
            { operator1: "ge", value1: "050000", operator2: "le", value2: "103000" }
          ];
        } else {
          consultasNocturnas = [{ operator1: null, value1: null, operator2: null, value2: null }];
        }
      } else {
        consultasNocturnas = [{ operator1: null, value1: null, operator2: null, value2: null }];
      }

      // 🔥 GENERAR UNA CONSULTA POR CADA FILTRO NOCTURNO
      for (const nocturna of consultasNocturnas) {
        let filtrosActuales = [...filters];

        // Aplicar filtro de tiempo nocturno si corresponde
        if (nocturna.operator1 && nocturna.operator2 && (source === "frames" || source === "nadir")) {
          // Remover filtros existentes de ptime para esta fuente
          filtrosActuales = filtrosActuales.filter(f => !(f.table === source && f.field === "ptime"));

          // Agregar nuevos filtros de tiempo
          filtrosActuales.push(
            { table: source, field: "ptime", operator: nocturna.operator1, value: nocturna.value1 },
            { table: source, field: "ptime", operator: nocturna.operator2, value: nocturna.value2 }
          );
        }

        // Construir query y return para esta consulta específica
        const queryForSource = window.queryBuilder.buildQuery(filtrosActuales, source, boundingBox);
        const returnForSource = window.queryBuilder.buildReturn(returnFieldsSelected, source);

        consultas.push({
          source: source,
          query: queryForSource,
          return: returnForSource
          // modoNocturno: nocturna.operator1 ? `${nocturna.value1}-${nocturna.value2}` : "normal"
        });
      }
    }

    const nuevaTarea = {
      id: taskId,
      consultas: consultas,  // 🔥 Array de consultas (puede tener 2+ por fuente)
      hora: cronHora,
      frecuencia: cronFrecuencia,
      intervalo: cronIntervalo
    };

    try {
      let tareas = [];

      if (!fs.existsSync(jsonPathHost)) {
        fs.writeFileSync(jsonPathHost, "[]", "utf-8");
      }

      const contenido = fs.readFileSync(jsonPathHost, "utf-8").trim();
      tareas = contenido ? JSON.parse(contenido) : [];


      const yaExiste = tareas.some(t =>
        t.query === nuevaTarea.query &&
        t.return === nuevaTarea.return &&
        t.hora === nuevaTarea.hora &&
        t.frecuencia === nuevaTarea.frecuencia &&
        t.intervalo === nuevaTarea.intervalo
      );
      if (yaExiste) {
        alert("⚠️ Ya existe una tarea idéntica.");
        return;
      }


      tareas.push(nuevaTarea);
      fs.writeFileSync(jsonPathHost, JSON.stringify(tareas, null, 2), "utf-8");

      if (window.vueApp?.actualizarTareasDesdeArchivo) {
        window.vueApp.actualizarTareasDesdeArchivo();
      }

      const payload = {
        taskId,
        jsonPath: jsonPathWSL,
        hora: cronHora,
        frecuencia: cronFrecuencia,
        intervalo: cronIntervalo
      };

      const response = await ipcRenderer.invoke("crearTareaPeriodica", payload);
      alert(response.message || "✅ Cron creado.");
    } catch (err) {
      console.error("❌ Error al guardar o programar tarea:", err);
      alert("❌ Error creando tarea: " + err.message);
    }
  },

  async eliminarTarea(index, tareasPeriodicas) {
    const tarea = tareasPeriodicas[index];
    if (!tarea || !tarea.id) {
      alert("❌ Tarea inválida.");
      return;
    }

    if (!confirm(`¿Eliminar tarea programada (${tarea.id})?`)) return;

    try {
      const response = await ipcRenderer.invoke("eliminarTareaWindows", tarea.id);
      console.log(response.message);

      const jsonPath = path.join(__dirname, "tasks.json");

      let tareas = [];
      if (fs.existsSync(jsonPath)) {
        const contenido = fs.readFileSync(jsonPath, "utf-8").trim();
        tareas = contenido ? JSON.parse(contenido) : [];
      }

      const nuevasTareas = tareas.filter(t => t.id !== tarea.id);
      fs.writeFileSync(jsonPath, JSON.stringify(nuevasTareas, null, 2), "utf-8");

      if (window.vueApp?.actualizarTareasDesdeArchivo) {
        window.vueApp.actualizarTareasDesdeArchivo();
      }
    } catch (err) {
      console.error("❌", err.message);
      alert("❌ Error al eliminar tarea: " + err.message);
    }
  }
};