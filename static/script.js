document.addEventListener('DOMContentLoaded', function() {
    const inputSection = document.getElementById('inputSection');
    const mainContent = document.getElementById('mainContent');
    const outputSection = document.getElementById('outputSection');
    const outputMap = document.getElementById('outputMap');

    // Add event listeners to input elements
    inputSection.addEventListener('change', function(event) {
        updateDesigns();
    });

    // Add event listener for output section changes
    outputSection.addEventListener('change', function(event) {
        if (event.target.type === 'checkbox') {
            updateOutputMap();
        }
    });    

    function updateDesigns() {
        fetch('/update_designs', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(getInputValues())
        })
        .then(response => response.json())
        .then(data => {
            displayDesign(data.design);
        });
    }

    function getInputValues() {
        let inputValues = {};
        document.querySelectorAll('#inputSection input[type="checkbox"], #inputSection input[type="radio"]').forEach(input => {
            // Check if nextElementSibling exists to avoid the error
            if (input.nextElementSibling) {
                let key = input.nextElementSibling.textContent.trim().replace(/\s+/g, '_');
                if(input.type === 'checkbox' && input.checked) {
                    inputValues[key] = 'on';
                } else if(input.type === 'radio' && input.checked) {
                    inputValues[input.name] = key;
                }
            }
        });
        return inputValues;
    }

    function displayDesign(designSrc) {
        mainContent.innerHTML = ''; // Clear current content
        let img = document.createElement('img');
        img.src = designSrc;
        img.alt = 'Design Mockup';
        mainContent.appendChild(img);
    }

    function updateOutputMap() {
        // Fetch the updated output map based on output selections
        fetch('/update_output_map', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(getOutputSelections())
        })
        .then(response => response.json())
        .then(data => {
            displayOutputMap(data.mapSrc);
        });
    }

    function getOutputSelections() {
        let outputSelections = {};
        document.querySelectorAll('#outputSection input[type="checkbox"]').forEach(input => {
            outputSelections[input.id] = input.checked;
        });
        return outputSelections;
    }

    function displayOutputMap(mapSrc) {
        outputMap.style.backgroundImage = `url(${mapSrc})`;
        outputMap.style.backgroundSize = 'cover';
        outputMap.style.backgroundPosition = 'center';
    }


    document.getElementById('formalizeButton').addEventListener('click', function() {
        const currentData = {
            inputs: getInputValues(),
            // designs: getDesigns(), // You will need to implement this function
            // maps: getMaps() // You will need to implement this function
        };

        fetch('/formalize_criteria', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(currentData)
        })
        .then(response => response.json())
        .then(data => {
            displayFormalCriteria(data.criteria);
        });
    });

    function displayFormalCriteria(criteria) {
        const formalCriteriaElement = document.getElementById('formalCriteria');
        formalCriteriaElement.innerHTML = criteria; // Assuming 'criteria' is already in HTML format
    }
});
