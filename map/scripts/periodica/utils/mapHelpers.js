window.mapHelpers = {

initMap(mapId) {
  const container = document.getElementById(mapId);
  if (!container) {
    console.error(`❌ Contenedor #${mapId} no encontrado.`);
    return null;
  }

  const map = L.map(mapId).setView([8.5, -80], 6);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);
  return map;
},

  


   clearMap(map, markers) {
    markers.forEach(entry => map.removeLayer(entry.marker));
    markers = [];
  },


  addMarkersToMap(map, results) {
    const clusterGroup = L.markerClusterGroup();
    const markers = [];
  
    let validMarkers = 0;
  
    results.forEach(photo => {
      const lat = parseFloat(photo[`${photo.coordSource}.lat`]);
      const lon = parseFloat(photo[`${photo.coordSource}.lon`]);
  
      if (!isNaN(lat) && !isNaN(lon)) {
        const marker = L.marker([lat, lon]);
  
        const popupContent = `
          <div style="text-align: center;">
            <img src="${window.photoUtils.getImageUrl(photo)}" width="120"><br>
            <small>${photo["images.filename"]}</small><br>
            <strong>Fuente:</strong> ${photo.coordSource}
          </div>
        `;
  
        marker.bindPopup(popupContent);
        clusterGroup.addLayer(marker);
        markers.push({ marker, lat, lon });
        validMarkers++;
      }
    });
  
    if (validMarkers > 0) {
      map.addLayer(clusterGroup);
      map.fitBounds(clusterGroup.getBounds(), { padding: [30, 30] });
    } else {
      console.warn("⚠️ No se encontraron coordenadas válidas.");
    }
  
    return { markers, clusterGroup };
  }
  
  ,

  initBoundingBoxMap(mapId, boundingBox, onBoxChanged) {
    const map = L.map(mapId).setView([8.5, -79.5], 6);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);
  
    const bounds = [
      [boundingBox.latMin, boundingBox.lonMin],
      [boundingBox.latMax, boundingBox.lonMax]
    ];
  
    const rectangle = L.rectangle(bounds, { color: "#ff7800", weight: 2 });
    
    // 🟢 Instancia local del FeatureGroup
    const editableLayers = new L.FeatureGroup();
    editableLayers.addLayer(rectangle);
    map.addLayer(editableLayers);
  
    // 🟢 Instancia local del Control de Edición
    const drawControl = new L.Control.Draw({
      edit: {
        featureGroup: editableLayers,
        edit: true,
        remove: false
      },
      draw: false
    });
  
    map.addControl(drawControl);
  
    // 🟢 Evento local a este mapa
    map.on(L.Draw.Event.EDITED, (e) => {
      e.layers.eachLayer(layer => {
        const newBounds = layer.getBounds();
        boundingBox.latMin = newBounds.getSouthWest().lat.toFixed(4);
        boundingBox.lonMin = newBounds.getSouthWest().lng.toFixed(4);
        boundingBox.latMax = newBounds.getNorthEast().lat.toFixed(4);
        boundingBox.lonMax = newBounds.getNorthEast().lng.toFixed(4);
  
        if (onBoxChanged && typeof onBoxChanged === 'function') {
          onBoxChanged({ ...boundingBox });
        }
      });
    });
  
    map.fitBounds(bounds);
    return { map, rectangle };
  }

  
}