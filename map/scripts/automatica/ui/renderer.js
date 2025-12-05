const { initializeMap, agregarMarcador, updateImageCount } = require('./utils/map');
const { saveSelectedImageUrls } = require('./utils/utils');
const { initializeControls } = require('./utils/controls');
const path = require('path');
const fs = require('fs');
const { ipcRenderer } = require('electron');

const jsonFilePath = path.join(__dirname, '../', 'map_filters', 'combined_output.json');
const markerMap = new Map();
document.addEventListener('DOMContentLoaded', () => {
    initializeControls();

    const { map, drawnItems, markerCluster } = initializeMap();
    let selectedImageUrls = [];
    let currentRectangle = null;


    fetch(jsonFilePath)
        .then(response => response.json())
        .then(async data => {
            if (!Array.isArray(data)) {
                console.error("❌ El JSON no es un array. Recibido:", data);
                return;
            }

            const idsVistos = new Set();

            for (const row of data) {
                if (idsVistos.has(row.id)) {
                    console.warn(`⚠️ Dato duplicado en JSON: ${row.id}`);
                    continue;
                }
                idsVistos.add(row.id);
            
                const existe = await verificarNasaId(row.id);
                if (!existe) {
                    agregarMarcador(row, markerCluster);
                }
            }            

            updateImageCount();

        })
        .catch(error => console.error("❌ Error al cargar el JSON:", error));


    map.on('draw:created', function (event) {
        const layer = event.layer;
        drawnItems.addLayer(layer);

        if (currentRectangle) drawnItems.removeLayer(currentRectangle);
        currentRectangle = layer;

        if (layer instanceof L.Rectangle) {
            const bounds = layer.getBounds();
            selectedImageUrls = [];

            markerCluster.eachLayer(marker => {
                if (bounds.contains(marker.getLatLng()) && marker.options.imageUrl) {
                    selectedImageUrls.push(marker.options.imageUrl);
                }
            });

            console.log(`🖼️ Imágenes seleccionadas: ${selectedImageUrls.length}`);
            if (selectedImageUrls.length === 0) {
                alert("No hay imágenes dentro del área seleccionada.");
            }
        }
    });

    // Watcher para actualizar marcadores
    if (fs.existsSync(jsonFilePath)) {
        fs.watchFile(jsonFilePath, { interval: 1000 }, async (curr, prev) => {
            if (curr.mtime !== prev.mtime) {
                console.log("🔁 Archivo JSON modificado. Actualizando marcadores...");
                await actualizarMarcadores();
            }
        });
    } else {
        console.warn(`⚠️ File ${jsonFilePath} does not exist. Watcher not started.`);
    }


    async function actualizarMarcadores() {
        try {
            const response = await fetch(`${jsonFilePath}?t=${Date.now()}`);
            if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);

            const data = await response.json();
            markerCluster.clearLayers();
            markerMap.clear();

            for (const row of data) {
                const existe = await verificarNasaId(row.id);
                if (!existe) {
                    agregarMarcador(row, markerCluster);
                }
            }

            console.log(`${data.length} marcadores actualizados.`);
            updateImageCount();
        } catch (error) {
            console.error('Error al actualizar marcadores:', error);
        }
    }

    async function verificarNasaId(nasaId) {
        try {
            return await ipcRenderer.invoke('verificar-nasa-id', nasaId);
        } catch {
            console.error("No se pudo verificar el NASA_ID.");
            return false;
        }
    }

    const sendButton = document.getElementById('sendButton');
    sendButton.addEventListener('click', (e) => {
        e.preventDefault();
        if (!selectedImageUrls || selectedImageUrls.length === 0) {
            alert('Por favor, selecciona al menos una imagen antes de continuar.');
            return;
        }
        saveSelectedImageUrls(selectedImageUrls);
        ipcRenderer.send('close');
    });
});
