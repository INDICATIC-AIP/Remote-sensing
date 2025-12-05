const { focal_length, cameras, filmClassifications, films } = require('./data');
let uncatalogedContainer;
function initializeControls() {
    const rightPanel = document.getElementById('rightPanel');
    if (document.getElementById('basicConfigContainer')) return;

const formContainer = document.createElement('div');
formContainer.id = 'basicConfigContainer';
    // Contenedor de configuración básica
    formContainer.style.background = 'white';
    formContainer.style.padding = '20px';
    formContainer.style.borderRadius = '10px';
    formContainer.style.boxShadow = '0 2px 5px rgba(0, 0, 0, 0.1)';
    formContainer.style.marginBottom = '20px';
    rightPanel.appendChild(formContainer);

    formContainer.appendChild(createTitle("Configuración Básica"));

    // Create coordinate inputs
    const inputs = {
        upperLat: createInputField('Latitud Superior:', 'upperLat', '9.5'),
        lowerLat: createInputField('Latitud Inferior:', 'lowerLat', '8.6'),
        leftLon: createInputField('Longitud Izquierda:', 'leftLon', '-80.3'),
        rightLon: createInputField('Longitud Derecha:', 'rightLon', '-79.1')
    };

    Object.values(inputs).forEach(input => {
        input.input.addEventListener('input', updateRectangleFromInputs);
        formContainer.appendChild(input.container);
    });

    // Create send button
    const sendButton = document.createElement('button');
    sendButton.innerText = 'Enviar URL y Cerrar';
    sendButton.style.width = '100%';
    sendButton.style.padding = '12px';
    sendButton.id = 'sendButton'; 
    sendButton.style.backgroundColor = '#007BFF';
    sendButton.style.color = 'white';
    sendButton.style.border = 'none';
    sendButton.style.borderRadius = '5px';
    sendButton.style.cursor = 'pointer';
    sendButton.style.marginTop = '20px';
    sendButton.style.fontSize = '16px';
    sendButton.style.transition = 'background 0.3s';
    sendButton.addEventListener('mouseover', () => sendButton.style.backgroundColor = '#0056b3');
    sendButton.addEventListener('mouseout', () => sendButton.style.backgroundColor = '#007BFF');
    formContainer.appendChild(sendButton);

    uncatalogedContainer = document.createElement('div');
    uncatalogedContainer.style.display = 'block';
    uncatalogedContainer.style.background = 'white';
    uncatalogedContainer.style.padding = '20px';
    uncatalogedContainer.style.borderRadius = '10px';
    uncatalogedContainer.style.marginBottom = '20px'; 
    uncatalogedContainer.style.boxShadow = '0 2px 5px rgba(0, 0, 0, 0.1)';
    

    // Advanced configuration container
    const advancedContainer = document.createElement('div');
    advancedContainer.style.display = 'none';
    advancedContainer.style.background = 'white';
    advancedContainer.id = "advancedContainer";
    advancedContainer.style.padding = '20px';
    advancedContainer.style.borderRadius = '10px';
    advancedContainer.style.marginBottom = '20px'; // Añadido margin bottom
    advancedContainer.style.boxShadow = '0 2px 5px rgba(0, 0, 0, 0.1)';
    rightPanel.appendChild(advancedContainer);

    // Toggle button for advanced settings
    const toggleAdvanced = document.createElement('button');
    toggleAdvanced.innerText = 'Mostrar Configuración Avanzada ⬇';
    toggleAdvanced.style.width = '100%';
    toggleAdvanced.style.padding = '10px';
    toggleAdvanced.style.backgroundColor = '#f8f9fa';
    toggleAdvanced.style.border = '1px solid #dee2e6';
    toggleAdvanced.style.borderRadius = '5px';
    toggleAdvanced.style.cursor = 'pointer';
    toggleAdvanced.style.marginTop = '10px';
    toggleAdvanced.style.marginBottom = '10px';
    formContainer.appendChild(toggleAdvanced);

    let isAdvancedVisible = false;
    toggleAdvanced.addEventListener('click', () => {
        isAdvancedVisible = !isAdvancedVisible;
        advancedContainer.style.display = isAdvancedVisible ? 'block' : 'none';
        toggleAdvanced.innerText = isAdvancedVisible ? 'Ocultar Configuración Avanzada ⬆' : 'Mostrar Configuración Avanzada ⬇';

        // Hacer scroll automático al panel avanzado cuando se muestra
        if (isAdvancedVisible) {
            advancedContainer.scrollIntoView({ behavior: 'smooth' });
        }
    });


    
   

        // Crear contenedor para el select y configurar estilos
const catalogedSelectContainer = document.createElement('div');
catalogedSelectContainer.style.textAlign = 'center'; // Centrar contenido
catalogedSelectContainer.style.marginBottom = '20px';
catalogedSelectContainer.style.borderBottom = '2px solid #007BFF';

// Crear el elemento select
const catalogedSelect = document.createElement('select');
catalogedSelect.id = 'catalogedSelect';
catalogedSelect.style.marginRight = '8px';

// Crear opciones para el 
const optionAll = document.createElement('option');
optionAll.value = 'all';
optionAll.textContent = 'All';

const optionCataloged = document.createElement('option');
optionCataloged.value = 'cataloged';
optionCataloged.textContent = 'Cataloged';

const optionNotCataloged = document.createElement('option');
optionNotCataloged.value = 'not-cataloged';
optionNotCataloged.textContent = 'Not Cataloged';


// Agregar las opciones al select
catalogedSelect.appendChild(optionAll);
catalogedSelect.appendChild(optionCataloged);
catalogedSelect.appendChild(optionNotCataloged);



// Agregar el select al contenedor
catalogedSelectContainer.appendChild(catalogedSelect);

// Si también debe aparecer en 'advancedContainer'
if (advancedContainer) {
    advancedContainer.appendChild(catalogedSelectContainer);
} else {
    console.warn("El contenedor 'advancedContainer' no está definido.");
}




catalogedSelect.addEventListener('change', () => {
    const inputsAdvanced = advancedContainer.querySelectorAll('input, select');
    const inputsUncataloged = uncatalogedContainer.querySelectorAll('input, select');

    // Asegurar que catalogedSelect nunca sea deshabilitado

    // Ocultar o mostrar el contenedor de "Not Cataloged"
    uncatalogedContainer.style.display = catalogedSelect.value === 'not-cataloged' ? 'block' : 'none';

    switch (catalogedSelect.value) {
        case 'cataloged':
            // Habilitar controles avanzados, deshabilitar controles sin catalogar
            inputsAdvanced.forEach(el => el.disabled = false);
            inputsUncataloged.forEach(el => el.disabled = true);
            break;

        case 'not-cataloged':
            // Habilitar controles sin catalogar, deshabilitar controles avanzados
            inputsAdvanced.forEach(el => el.disabled = true);
            inputsUncataloged.forEach(el => el.disabled = false);
            break;

        case 'all':
        default:
            // Deshabilitar ambos grupos de controles si se selecciona 'all' o valor desconocido
            inputsAdvanced.forEach(el => el.disabled = true);
            inputsUncataloged.forEach(el => el.disabled = true);
            break;
    }
    catalogedSelect.disabled = false;

});


    // Definición de los controles (checkboxes)
const uncatalogedControls = [
    { type: 'checkbox', label: 'Incluir Imágenes Diurnas:', id: 'daytime' },
    { type: 'checkbox', label: 'Incluir Imágenes Nocturnas:', id: 'nighttime' },
    { type: 'checkbox', label: 'Incluir imágenes del amanecer y del anochecer:', id: 'dawndusk' },
    { type: 'checkbox', label: 'Incluir imágenes panorámicas y oblicuas altas:', id: 'HO' },
    { type: 'checkbox', label: 'Tiene máscara de nube:', id: 'hasCloudMask' }
];




const advancedControls = [
    { id: "camera-tilt", type: "checkbox-group", label: "Camera Tilt:", options: ["Near vertical", "Low Oblique", "High Oblique"] },
    { id: "cloud-cover", type: "checkbox-group", label: "Cloud Cover:", options: ["No clouds present", "1-10%", "11-25%", "26-50%", "51-75%", "76-100%"] },
    { id: "months", type: "select", multiple: true, size: 5, label: "Month(s):", options: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"] },
    { id: "min-focal-length", type: "select", label: "Minimum focal length:", options: focal_length },
    { id: "max-focal-length", type: "select", label: "Maximum focal length:", options: focal_length },
    { id: "min-sun-elevation", type: "number", label: "Minimum Sun Elevation:", placeholder: "Entre -90 y 90", min: -90, max: 90 },
    { id: "max-sun-elevation", type: "number", label: "Maximum Sun Elevation:", placeholder: "Entre -90 y 90", min: -90, max: 90 },
    { id: "cameras", type: "select", multiple: true, size: 5, label: "Camera(s):", options: cameras },
    { id: "film-classifications", type: "select", multiple: true, size: 6, label: "Film Classification(s):", options: filmClassifications },
    { id: "films", type: "select", multiple: true, size: 5, label: "Film(s):", options: films },
    { id: "has-cloud-mask", type: "checkbox", label: "Has Cloud Mask:" },
    { id: "min-megapixels", type: "number", label: "Minimum Megapixels:", placeholder: "Enter value", min: 0 }
];

        uncatalogedControls.forEach(control => {
            const element = createUncatalogedControl(control);
            uncatalogedContainer.appendChild(element);
        });
        // Solo agregar estilo una vez
        advancedContainer.appendChild(uncatalogedContainer);

        uncatalogedContainer.style.borderBottom = '2px solid #007BFF'; 
   

    advancedControls.forEach(control => {
        const element = createAdvancedControl(control);
        advancedContainer.appendChild(element);
    });




}




















function createTitle(title) {
    const container = document.createElement('div');
    container.style.display = 'flex';
    container.style.alignItems = 'center';
    container.style.justifyContent = 'space-between';
    container.style.padding = '10px';
    container.style.marginBottom = '20px';
    container.style.borderBottom = '2px solid #007BFF';
    container.style.fontSize = '1.2em';
    container.style.fontWeight = 'bold';
    container.style.color = '#007BFF';

    const titleElement = document.createElement('span');
    titleElement.innerText = title;

    const iconElement = document.createElement('span');
    iconElement.innerText = '⚙';
    iconElement.style.cursor = 'pointer';
    iconElement.style.fontSize = '20px';
    iconElement.style.marginLeft = '10px';

    container.appendChild(titleElement);
    container.appendChild(iconElement);

    return container;
}


function createInputField(labelText, id, defaultValue, type = 'text') {
    const container = document.createElement('div');
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.marginBottom = '15px';

    const label = document.createElement('label');
    label.innerText = labelText;
    label.style.marginBottom = '5px';
    label.style.fontWeight = 'bold';

    const input = document.createElement('input');
    input.type = type;
    input.id = id;
    input.value = defaultValue;
    input.style.width = '100%';
    input.style.padding = '8px';
    input.style.border = '1px solid #ccc';
    input.style.borderRadius = '5px';

    container.appendChild(label);
    container.appendChild(input);
    return { container, input };
}


function createUncatalogedControl(control) {
    const container = document.createElement('div');
    container.style.marginBottom = '10px';

    const label = document.createElement('label');
    label.innerText = control.label;
    label.style.marginLeft = '8px';

    if (control.type === 'checkbox') {
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.style.marginRight = '8px';

        container.appendChild(checkbox);
        container.appendChild(label);
    } else {
        console.error(`Tipo de control no soportado: ${control.type}`);
    }

    return container;
}


function createAdvancedControl(control) {
    const container = document.createElement('div');
    container.style.marginBottom = '15px';
    
    const label = document.createElement('label');
    label.innerText = control.label;
    label.style.display = 'block';
    label.style.fontWeight = 'bold';
    label.style.marginBottom = '8px';
    container.appendChild(label);
    
    if (control.type === 'checkbox-group') {
        control.options.forEach(option => {
            const wrapper = document.createElement('div');
            wrapper.style.marginBottom = '5px';
            wrapper.style.display = 'flex';
            wrapper.style.alignItems = 'center';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = option;
            // Añadir ID único para cada checkbox en el grupo
            checkbox.id = `${control.id}-${option.toLowerCase().replace(/\s+/g, '-')}`;
            checkbox.dataset.group = control.id;
            
            const optionLabel = document.createElement('label');
            optionLabel.innerText = option;
            optionLabel.style.marginLeft = '8px';
            optionLabel.htmlFor = checkbox.id; // Conectar label con el checkbox
            
            wrapper.appendChild(checkbox);
            wrapper.appendChild(optionLabel);
            container.appendChild(wrapper);
        });
    }
    
    if (control.type === 'select') {
        const select = document.createElement('select');
        select.id = control.id; // Añadir ID al select
        select.style.width = '100%';
        select.style.padding = '8px';
        select.style.borderRadius = '5px';
        select.style.border = '1px solid #ccc';
        
        if (control.multiple) {
            select.multiple = true;
            select.size = control.size || 5;
        }
        
        control.options.forEach(option => {
            const opt = document.createElement('option');
            opt.value = option;
            opt.innerText = option;
            select.appendChild(opt);
        });
        container.appendChild(select);
    }
    
    if (control.type === 'number' || control.type === 'text') {
        const input = document.createElement('input');
        input.type = control.type;
        input.id = control.id; // Añadir ID al input
        input.style.width = '100%';
        input.style.padding = '8px';
        input.style.borderRadius = '5px';
        input.style.border = '1px solid #ccc';
        
        if (control.placeholder) input.placeholder = control.placeholder;
        if (control.min !== undefined) input.min = control.min;
        if (control.max !== undefined) input.max = control.max;
        
        container.appendChild(input);
    }
    
    if (control.type === 'checkbox') {
        const wrapper = document.createElement('div');
        wrapper.style.display = 'flex';
        wrapper.style.alignItems = 'center';
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = control.id; // Usar el ID del control directamente
        checkbox.style.marginRight = '8px';
        
        const checkboxLabel = document.createElement('label');
        checkboxLabel.innerText = control.label.replace(':', ''); // Quitar los dos puntos si existen
        checkboxLabel.htmlFor = checkbox.id; // Conectar label con el checkbox
        
        wrapper.appendChild(checkbox);
        wrapper.appendChild(checkboxLabel);
        container.appendChild(wrapper);
    }
    
    return container;
}

function getSelectedUncatalogedParams() {
    const params = [];

    // Mapeo de checkboxes a argumentos de línea de comandos
    const checkboxMapping = {
        "Incluir Imágenes Diurnas:": "daytime",
        "Incluir Imágenes Nocturnas:": "nighttime",
        "Incluir imágenes del amanecer y del anochecer:": "dawndusk",
        "Incluir imágenes panorámicas y oblicuas altas:": "HO",
        "Incluir imágenes con máscara de nubes:": "hasCloudMask"
    };

    const checkboxes = uncatalogedContainer.querySelectorAll("input[type='checkbox']");
    
    checkboxes.forEach(checkbox => {
        const label = checkbox.nextSibling.textContent.trim();
        if (checkbox.checked && checkboxMapping[label]) {
            params.push(`--${checkboxMapping[label]}=on`);  // Solo enviar si está en "on"
        }
    });

    return params.join(" ");
}


function getSelectedCatalogedParams() {
    const params = [];
    const advancedContainer = document.getElementById('advancedContainer');

    if (!advancedContainer) {
        alert("No se encontró el contenedor con ID 'advancedContainer'");
        return "";
    }

    const inputs = advancedContainer.querySelectorAll('input, select');

    inputs.forEach(input => {
        try {
            const paramId = input.id;
            if (!paramId || paramId === "catalogedSelect") return;

            if (input.type === "checkbox") {
                if (input.checked) {
                    if (input.dataset && input.dataset.group) {
                        const groupName = input.dataset.group;
                        const groupElements = document.querySelectorAll(`input[data-group="${groupName}"]:checked`);
                        const values = Array.from(groupElements)
                            .map(el => `"${el.value}"`) // Envolver con comillas
                            .join(" ");

                        if (values && !params.some(param => param.startsWith(`--${groupName}=`))) {
                            params.push(`--${groupName} ${values}`);
                        }
                    } else {
                        params.push(`--${paramId}`);
                    }
                }
            } else if (input.type === "number" || input.type === "text") {
                if (input.value.trim() !== "" && input.value !== "No preference") { 
                    params.push(`--${paramId} "${encodeURIComponent(input.value)}"`);
                }
            } else if (input.tagName === "SELECT") {
                const selectedOptions = Array.from(input.selectedOptions)
                    .map(opt => `"${opt.value}"`) // Envolver con comillas
                    .filter(val => val !== `"No preference"`);

                if (selectedOptions.length > 0 && !params.some(param => param.startsWith(`--${paramId}=`))) {
                    const formattedValues = selectedOptions.join(" ");
                    params.push(`--${paramId} ${formattedValues}`);
                }
            }
        } catch (error) {
            alert(`Error al procesar elemento ${input.id}: ${error.message}`);
        }
    });

    return params.join(" ");
}

function updateRectangleFromInputs() {
    const upperLat = parseFloat(document.getElementById('upperLat').value);
    const lowerLat = parseFloat(document.getElementById('lowerLat').value);
    const leftLon = parseFloat(document.getElementById('leftLon').value);
    const rightLon = parseFloat(document.getElementById('rightLon').value);

    if (!isNaN(upperLat) && !isNaN(lowerLat) && !isNaN(leftLon) && !isNaN(rightLon)) {
        const bounds = [[lowerLat, leftLon], [upperLat, rightLon]];

        if (currentRectangle) {
            drawnItems.removeLayer(currentRectangle);
        }

        currentRectangle = L.rectangle(bounds, { color: '#ff7800', weight: 1 });
        drawnItems.addLayer(currentRectangle);
    }
}


module.exports = { initializeControls,
    getSelectedCatalogedParams, getSelectedUncatalogedParams };
