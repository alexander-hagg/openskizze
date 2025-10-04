// Client-side camera synchronization for 3D plots
// This runs in the browser for instant synchronization without server roundtrips

window.dash_clientside = Object.assign({}, window.dash_clientside, {
    clientside: {
        syncCameras: function(relayoutDataList, figureList) {
            // Find which plot was updated
            const triggered = window.dash_clientside.callback_context.triggered;
            if (!triggered || triggered.length === 0) {
                return window.dash_clientside.no_update;
            }
            
            // Get the triggered input info
            const triggeredProp = triggered[0].prop_id;
            
            // Extract the index from the triggered prop_id
            // Format: {"index":0,"type":"3d-plot"}.relayoutData
            let triggerIndex = -1;
            try {
                const match = triggeredProp.match(/"index":(\d+)/);
                if (match) {
                    triggerIndex = parseInt(match[1]);
                }
            } catch (e) {
                return window.dash_clientside.no_update;
            }
            
            if (triggerIndex < 0 || triggerIndex >= relayoutDataList.length) {
                return window.dash_clientside.no_update;
            }
            
            // Get the relayout data from the triggered plot
            const relayoutData = relayoutDataList[triggerIndex];
            
            // Check if camera was updated (and not just dragmode or other properties)
            if (!relayoutData || !relayoutData['scene.camera']) {
                return window.dash_clientside.no_update;
            }
            
            // Get the new camera state
            const newCamera = relayoutData['scene.camera'];
            
            // Update all other plots with the new camera position
            const updatedFigures = figureList.map((fig, index) => {
                if (index === triggerIndex) {
                    // Don't update the plot that triggered the change
                    return window.dash_clientside.no_update;
                }
                
                // Create a shallow copy of the figure
                const updatedFig = {...fig};
                
                // Update the camera in the scene
                if (updatedFig.layout && updatedFig.layout.scene) {
                    updatedFig.layout = {
                        ...updatedFig.layout,
                        scene: {
                            ...updatedFig.layout.scene,
                            camera: newCamera
                        }
                    };
                }
                
                return updatedFig;
            });
            
            return updatedFigures;
        }
    }
});
