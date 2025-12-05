window.photoUtils = {
 getImageUrl(photo) { 
    const originalDir = photo["images.directory"];
      const filename = photo["images.filename"];

      // console.log("📦 Directorio original:", originalDir);
      // console.log("🖼️ Nombre de archivo:", filename);

      if (originalDir && filename) {
        const parts = originalDir.split('/');
        // console.log("🔍 Partes del directorio:", parts);

        if (parts.length >= 3) {
          const type = parts[1].toLowerCase();
          // console.log("🧪 Tipo de carpeta detectada:", type);

          if (type.includes("highres")) {
            parts[1] = "lowres";
            // console.log("🔄 Transformado a carpeta 'lowres'");
          } else if (type.includes("large")) {
            parts[1] = "small";
            // console.log("🔄 Transformado a carpeta 'small'");
          } else {
            console.warn("⚠️ Tipo de carpeta no reconocido. Se usará como está.");
          }

          const previewDir = parts.join('/');
          const fullUrl = `https://eol.jsc.nasa.gov/DatabaseImages/${previewDir}/${filename}`;
          // console.log("✅ URL final construida:", fullUrl);

          return fullUrl;
        } else {
          console.warn("⚠️ Directorio no tiene suficientes partes.");
        }
      } else {
        console.warn("⚠️ Faltan datos de directorio o nombre de archivo.");
      }

      // Imagen por defecto
      return "https://eol.jsc.nasa.gov/assets/images/nasapic.jpg";
 },
 getPhotoDetails(photo) { 
    // Filtrar solo los campos que tienen valores
    const details = {};
    for (const key in photo) {
      if (photo[key] && key !== 'images.filename') {
        details[key] = photo[key];
      }
    }
    return details;
 },
 formatFieldName(key) { 
     // Mejora la presentación de los nombres de campo
     const parts = key.split('|');
     if (parts.length === 2) {
       return parts[1].charAt(0).toUpperCase() + parts[1].slice(1);
     }
     return key;
 }
}