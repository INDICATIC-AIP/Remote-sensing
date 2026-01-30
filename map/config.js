// Configuration for Electron application
// This file reads environment variables from the .env file

const path = require('path');
const fs = require('fs');

// Function to load environment variables from .env
function loadEnv() {
  const envPath = path.join(__dirname, '..', '.env');
  
  if (!fs.existsSync(envPath)) {
    console.error('[WARNING] .env file not found. Copy .env.example to .env and configure your credentials.');
    return {};
  }

  const envContent = fs.readFileSync(envPath, 'utf-8');
  const envVars = {};

  envContent.split('\n').forEach(line => {
    line = line.trim();
    // Ignore comments and empty lines
    if (line && !line.startsWith('#')) {
      const [key, ...valueParts] = line.split('=');
      if (key && valueParts.length > 0) {
        let value = valueParts.join('=').trim();
        // Remove quotes if present
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

// Load environment variables
const env = loadEnv();

// Export configuration
module.exports = {
  NASA_API_KEY: env.NASA_API_KEY || '',
  NAS_IP: env.NAS_IP || '',
  NAS_SHARE: env.NAS_SHARE || '',
  NAS_USERNAME: env.NAS_USERNAME || '',
  NAS_PASSWORD: env.NAS_PASSWORD || '',
  
  // Validate that required variables exist
  validate() {
    const required = ['NASA_API_KEY'];
    const missing = required.filter(key => !this[key]);
    
    if (missing.length > 0) {
      console.error(`[ERROR] Missing environment variables: ${missing.join(', ')}`);
      console.error('Please configure the .env file');
      return false;
    }
    return true;
  }
};
