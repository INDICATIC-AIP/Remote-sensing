const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');


function saveSelectedImageUrls(selectedImageUrls) {
    if (selectedImageUrls.length === 0) {
        alert("No se han seleccionado imágenes. Dibuja un área sobre los marcadores antes de enviar.");
        return;
    }

    const automaticaDir = path.join(__dirname, '../', '..');
    const filePath = path.join(automaticaDir, 'enlaces_photo_id.txt');


    if (!fs.existsSync(automaticaDir)) {
        fs.mkdirSync(automaticaDir, { recursive: true });
    }

    fs.writeFile(filePath, selectedImageUrls.join('\n') + '\n', (err) => {
        if (err) {
            console.error('Error al guardar las URLs:', err);
        } else {
            console.log(`${selectedImageUrls.length} imágenes guardadas en ${filePath}`);
            alert(`Selección guardada exitosamente.`);
        }
    });
}


function runPythonScript(command) {
    return new Promise((resolve, reject) => {
        exec(command, (error, stdout, stderr) => {
            if (error) {
                reject(new Error(`❌ Error ejecutando Python: ${error.message}`));
                return;
            }

            // ✅ Buscar mensaje especial
            const abortMatch = stdout.match(/^QueryAborted::(.*)$/m);
            if (abortMatch) {
                reject(new Error(`❌ Consulta abortada:\n${abortMatch[1].trim()}`));
                return;
            }

            if (stderr) {
                console.warn(`⚠️ Python stderr: ${stderr}`);
            }

            console.log(`✅ Salida de Python: ${stdout}`);
            resolve(stdout);
        });
    });
}

module.exports = { saveSelectedImageUrls, runPythonScript };
