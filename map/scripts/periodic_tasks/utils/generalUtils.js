window.generalUtils = {
  aplicarCamposDefault(returnFieldsSelected) {
    // Default return fields per table
    const combinedDefaults = {
      frames: ["mission","tilt","pdate","ptime","cldp","azi","elev","fclt","lat", "lon","nlat", "nlon","camera","film","geon","feat"],
      nadir: ["mission","pdate","ptime","lat", "lon","azi","elev","cldp"],
      mlcoord: ["mission","lat", "lon", "orientation"],
      images: ["directory", "filename", "width","height"],
    };

    for (const table in combinedDefaults) {
      returnFieldsSelected[table] = [...combinedDefaults[table]];
    }
    console.log("Default return fields applied:", JSON.stringify(returnFieldsSelected, null, 2));
  }
};
