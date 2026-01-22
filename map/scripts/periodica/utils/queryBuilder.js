window.queryBuilder = {

  buildQuery(filters, selectedCoordSource, boundingBox) {
    // Incluir filtros de la tabla seleccionada y siempre incluir cualquier filtro 'pdate'
    const candidate = filters.filter(f => f.table === selectedCoordSource || f.field === 'pdate');
    // Normalizar y eliminar duplicados
    const userFilters = Array.from(new Set(candidate.map(filter => `${filter.table}|${filter.field}|${filter.operator}|${filter.value}`)));

    const boundingFilters = [
      `${selectedCoordSource}|lat|ge|${boundingBox.latMin}`,
      `${selectedCoordSource}|lat|le|${boundingBox.latMax}`,
      `${selectedCoordSource}|lon|ge|${boundingBox.lonMin}`,
      `${selectedCoordSource}|lon|le|${boundingBox.lonMax}`
    ];

    return [...userFilters, ...boundingFilters].join("|");
  },

  buildReturn(returnFieldsSelected, source) {
    const returnList = [];
  
    for (const [table, fields] of Object.entries(returnFieldsSelected)) {
      // ✅ Solo campos de la tabla actual o images
      if (table === source || table === "images") {
        for (const field of fields) {
          returnList.push(`${table}|${field}`);
        }
      }
    }
  
    // if (source === "nadir" || source === "mlcoord") {
    //    returnList.push("camera|camera");
    // }

    // 🔄 Fallback mínimo
    if (returnList.length === 0) {
      returnList.push("images|directory", "images|filename");
      returnList.push(`${source}|lat`, `${source}|lon`);
    }
  
    return returnList.join("|");
  }
  
};
