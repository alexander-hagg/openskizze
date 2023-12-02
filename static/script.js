document.addEventListener('DOMContentLoaded', function() {
    const inputSection = document.getElementById('inputSection');
    const mainContent = document.getElementById('mainContent');
    const outputSection = document.getElementById('outputSection');
    const outputMap = document.getElementById('outputMap');

    const checkboxes = document.querySelectorAll('.variation-properties input[type="checkbox"]');
    let checked = [];
    // Preselect the first two checkboxes
    checkboxes[0].checked = true;
    checkboxes[1].checked = true;
    checked.push(checkboxes[0], checkboxes[1]);
    updateAxisLabels();    
    checkboxes.forEach(function(checkbox) {
        checkbox.addEventListener('change', function() {
            if (checkbox.checked) {
                checked.push(checkbox);
                if (checked.length > 2) {
                    checked[0].checked = false;
                    checked.shift();
                }
            } else {
                // Prevent unchecking if it results in less than two checkboxes being checked
                if (checked.length <= 2) {
                    checkbox.checked = true;
                    return;
                }
                checked = checked.filter(item => item !== checkbox);
            }
            updateAxisLabels();
        });
    });

    updateOutputMaps();

    // Add event listeners to input elements
    inputSection.addEventListener('change', function(event) {
        //updateDesigns();
    });

    // Add event listener for output section changes
    // outputSection.addEventListener('change', function(event) {
    //     if (event.target.type === 'radio') {
    //         updateOutputMap();
    //     }
    // });    


    function updateAxisLabels() {
        const checkedCheckboxes = document.querySelectorAll('.variation-properties input[type="checkbox"]:checked');
        let labels = Array.from(checkedCheckboxes).map(cb => cb.nextSibling.textContent.trim());
        if (labels.length === 2) {
            document.getElementById('x-axis-label').textContent = labels[0].concat(" \u2192");
            document.getElementById('y-axis-label').textContent = "\u2190 ".concat(labels[1]);
        }
    }


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
            updateDesign(data.design);
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


    function updateOutputMaps() {
        // Fetch the updated output map based on output selections
        fetch('/update_output_map', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify('a')
        })
        .then(response => response.json())
        .then(data => {
            displayOutputMaps(data.mapSrc);
        });
    }

    // function getOutputSelections() {
    //     let outputSelections = {};
    //     document.querySelectorAll('#outputSection input[type="checkbox"]').forEach(input => {
    //         outputSelections[input.id] = input.checked;
    //     });
    //     return outputSelections;
    // }

    function displayOutputMaps(mapSrc) {
        mapSrc.forEach(function(map, index) {
            var outputMap = document.getElementById(`outputMap${index}`);
            if (outputMap) {
                outputMap.style.backgroundImage = `url(${map})`;
                outputMap.style.backgroundSize = 'cover';
                outputMap.style.backgroundPosition = 'center';
            }
        });
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
