// Configuración para aplicación Electron
// Este archivo lee las variables de entorno del archivo .env

const path = require('path');
const fs = require('fs');

// Función para cargar variables de entorno desde .env
function loadEnv() {
  const envPath = path.join(__dirname, '..', '..', '..', '.env');
  
  if (!fs.existsSync(envPath)) {
    console.error('⚠️ Archivo .env no encontrado. Copia .env.example a .env y configura tus credenciales.');
    return {};
  }

  const envContent = fs.readFileSync(envPath, 'utf-8');
  const envVars = {};

  envContent.split('\n').forEach(line => {
    line = line.trim();
    // Ignorar comentarios y líneas vacías
    if (line && !line.startsWith('#')) {
      const [key, ...valueParts] = line.split('=');
      if (key && valueParts.length > 0) {
        let value = valueParts.join('=').trim();
        // Remover comillas si existen
        if ((value.startsWith('"') && value.endsWith('"')) || 
            (value.startsWith("'") && value.endsWith("'"))) {
          value = value.slice(1, -1);
        }
        envVars[key.trim()] = value;
      }
    }
  });

  return envVars;
}

// Cargar variables de entorno
const env = loadEnv();

// Exportar configuración
module.exports = {
  NASA_API_KEY: env.NASA_API_KEY || '',
  NAS_IP: env.NAS_IP || '',
  NAS_SHARE: env.NAS_SHARE || '',
  NAS_USERNAME: env.NAS_USERNAME || '',
  NAS_PASSWORD: env.NAS_PASSWORD || '',
  
  // Validar que las variables necesarias existan
  validate() {
    const required = ['NASA_API_KEY'];
    const missing = required.filter(key => !this[key]);
    
    if (missing.length > 0) {
      console.error(`❌ Variables de entorno faltantes: ${missing.join(', ')}`);
      console.error('Por favor configura el archivo .env');
      return false;
    }
    return true;
  }
};
