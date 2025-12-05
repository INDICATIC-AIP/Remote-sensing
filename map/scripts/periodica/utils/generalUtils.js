window.generalUtils = {
  aplicarCamposDefault(returnFieldsSelected) {
    // Aquí defines lo que quieres que siempre se incluya
    const combinedDefaults = {
      frames: ["mission","tilt","pdate","ptime","cldp","azi","elev","fclt","lat", "lon","nlat", "nlon","camera","film","geon","feat"],
      nadir: ["mission","pdate","ptime","lat", "lon","azi","elev","cldp"],
      mlcoord: ["mission","lat", "lon", "orientation"],
      images: ["directory", "filename", "width","height"],
    };

    for (const table in combinedDefaults) {
      returnFieldsSelected[table] = [...combinedDefaults[table]];
    }
    console.log("🎯 Defaults aplicados:", JSON.stringify(returnFieldsSelected, null, 2));
  }
};
