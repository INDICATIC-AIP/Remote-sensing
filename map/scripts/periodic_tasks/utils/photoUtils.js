window.photoUtils = {
 getImageUrl(photo) { 
    const originalDir = photo["images.directory"];
      const filename = photo["images.filename"];

      if (originalDir && filename) {
        const parts = originalDir.split('/');
        if (parts.length >= 3) {
          const type = parts[1].toLowerCase();
          if (type.includes("highres")) {
            parts[1] = "lowres";
          } else if (type.includes("large")) {
            parts[1] = "small";
          } else {
            console.warn("Folder type not recognized. Using as is.");
          }

          const previewDir = parts.join('/');
          const fullUrl = `https://eol.jsc.nasa.gov/DatabaseImages/${previewDir}/${filename}`;

          return fullUrl;
        } else {
          console.warn("Directory does not have enough parts.");
        }
      } else {
        console.warn("Missing directory or filename data.");
      }

      // Imagen por defecto
      return "https://eol.jsc.nasa.gov/assets/images/nasapic.jpg";
 },
 getPhotoDetails(photo) { 
    // Keep only fields with values
    const details = {};
    for (const key in photo) {
      if (photo[key] && key !== 'images.filename') {
        details[key] = photo[key];
      }
    }
    return details;
 },
 formatFieldName(key) { 
     // Improve display formatting for field names
     const parts = key.split('|');
     if (parts.length === 2) {
       return parts[1].charAt(0).toUpperCase() + parts[1].slice(1);
     }
     return key;
 }
}