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
                };
            } else {
                return {
                    color: '#3388ff',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.1
                };
            }
        }

    }
});