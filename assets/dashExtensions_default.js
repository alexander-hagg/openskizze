window.dashExtensions = Object.assign({}, window.dashExtensions, {
    default: {
        function0: function(feature, context) {
                const {
                    selected
                } = context.hideout;
                if (selected.includes(feature.properties.id)) {
                    return {
                        color: '#ff7800',
                        weight: 3,
                        opacity: 1,
                        fillOpacity: 0.5
                    }; // Orange for selected
                } else {
                    return {
                        color: '#3388ff',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.1
                    }; // Blue for available
                }
            }

            ,
        function1: function(feature, context) {
            const {
                z_length
            } = context.hideout;
            const height = feature.properties.height;
            const colorscale = chroma.scale('viridis').domain([0, z_length]);
            return {
                fillColor: colorscale(height),
                color: '#333',
                weight: 1,
                opacity: 1,
                fillOpacity: 0.8
            };
        }

    }
});