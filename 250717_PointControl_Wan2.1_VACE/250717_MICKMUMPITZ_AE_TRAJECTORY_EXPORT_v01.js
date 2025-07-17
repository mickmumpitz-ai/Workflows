// After Effects Screen Space Position Export Script
// Exports selected layers' position data in screen space coordinates

(function() {
    
    // Check if After Effects is available
    if (typeof app === "undefined") {
        alert("This script must be run in After Effects");
        return;
    }
    
    // Check if a project is open
    if (!app.project) {
        alert("Please open a project first");
        return;
    }
    
    // Check if a composition is active
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
        alert("Please select an active composition");
        return;
    }
    
    // Check if layers are selected
    var selectedLayers = comp.selectedLayers;
    if (selectedLayers.length === 0) {
        alert("Please select one or more layers");
        return;
    }
    
    // Get composition settings
    var frameRate = comp.frameRate;
    var duration = comp.duration;
    var startTime = 0;
    var endTime = duration;
    var timeStep = 1 / frameRate;
    var totalFrames = Math.ceil((endTime - startTime) * frameRate);
    
    // Function to convert position to screen space
    function positionToScreenSpace(layer, time, comp) {
        try {
            var pos3D = layer.position.valueAtTime(time, false);
            
            if (layer.threeDLayer) {
                var camera = comp.activeCamera;
                if (!camera) {
                    var compWidth = comp.width;
                    var compHeight = comp.height;
                    
                    return [
                        pos3D[0] + compWidth / 2,
                        pos3D[1] + compHeight / 2
                    ];
                } else {
                    var cameraPos = camera.position.valueAtTime(time, false);
                    var cameraPoint = camera.pointOfInterest.valueAtTime(time, false);
                    var zoom = camera.zoom ? camera.zoom.valueAtTime(time, false) : 2000;
                    
                    var relX = pos3D[0] - cameraPos[0];
                    var relY = pos3D[1] - cameraPos[1];
                    var relZ = pos3D[2] - cameraPos[2];
                    
                    var camToPOI = Math.sqrt(
                        Math.pow(cameraPoint[0] - cameraPos[0], 2) +
                        Math.pow(cameraPoint[1] - cameraPos[1], 2) +
                        Math.pow(cameraPoint[2] - cameraPos[2], 2)
                    );
                    
                    var distance = camToPOI + relZ;
                    var scale = distance !== 0 ? zoom / distance : 1;
                    
                    var screenX = (relX * scale) + comp.width / 2;
                    var screenY = (relY * scale) + comp.height / 2;
                    
                    return [screenX, screenY];
                }
            } else {
                return [pos3D[0], pos3D[1]];
            }
        } catch (e) {
            var pos = layer.position.valueAtTime(time, false);
            return [pos[0], pos[1]];
        }
    }
    
    // Collect position data for all selected layers
    var exportData = "";
    
    // If only one layer is selected, export as simple array
    if (selectedLayers.length === 1) {
        var layer = selectedLayers[0];
        var positionData = [];
        
        for (var frameIndex = 0; frameIndex < totalFrames; frameIndex++) {
            var time = startTime + (frameIndex * timeStep);
            
            if (time > endTime) {
                time = endTime;
            }
            
            var screenPos = positionToScreenSpace(layer, time, comp);
            
            positionData.push({
                x: Math.round(screenPos[0]),
                y: Math.round(screenPos[1])
            });
            
            if (time >= endTime) {
                break;
            }
        }
        
        // Build simple array format
        exportData = "[";
        for (var j = 0; j < positionData.length; j++) {
            if (j > 0) exportData += ", ";
            exportData += '{"x": ' + positionData[j].x + ', "y": ' + positionData[j].y + '}';
        }
        exportData += "]";
        
    } else {
        // Multiple layers - export as object with layer names
        var allLayersData = {};
        
        for (var n = 0; n < selectedLayers.length; n++) {
            var layer = selectedLayers[n];
            var positionData = [];
            
            for (var frameIndex = 0; frameIndex < totalFrames; frameIndex++) {
                var time = startTime + (frameIndex * timeStep);
                
                if (time > endTime) {
                    time = endTime;
                }
                
                var screenPos = positionToScreenSpace(layer, time, comp);
                
                positionData.push({
                    x: Math.round(screenPos[0]),
                    y: Math.round(screenPos[1])
                });
                
                if (time >= endTime) {
                    break;
                }
            }
            
            allLayersData[layer.name] = positionData;
        }
        
        // Build JSON object format
        exportData = "{\n";
        var layerNames = [];
        
        for (var name in allLayersData) {
            if (allLayersData.hasOwnProperty(name)) {
                layerNames.push(name);
            }
        }
        
        for (var i = 0; i < layerNames.length; i++) {
            var layerName = layerNames[i];
            var layerData = allLayersData[layerName];
            
            if (i > 0) exportData += ",\n";
            exportData += '  "' + layerName + '": [';
            
            for (var j = 0; j < layerData.length; j++) {
                if (j > 0) exportData += ", ";
                exportData += '{"x": ' + layerData[j].x + ', "y": ' + layerData[j].y + '}';
            }
            
            exportData += ']';
        }
        
        exportData += "\n}";
    }
    
    // Show dialog with coordinates
    var dialog = new Window("dialog", "Screen Position Export");
    dialog.orientation = "column";
    dialog.alignChildren = "fill";
    
    // Add info text
    var infoGroup = dialog.add("group");
    infoGroup.orientation = "column";
    infoGroup.alignChildren = "left";
    
    if (selectedLayers.length === 1) {
        infoGroup.add("statictext", undefined, "Layer: " + selectedLayers[0].name);
    } else {
        infoGroup.add("statictext", undefined, "Selected layers: " + selectedLayers.length);
    }
    
    // Add text area with coordinates
    var textArea = dialog.add("edittext", undefined, exportData, {multiline: true, scrolling: true});
    textArea.preferredSize.width = 600;
    textArea.preferredSize.height = 400;
    textArea.active = true;
    
    // Add buttons
    var buttonGroup = dialog.add("group");
    buttonGroup.orientation = "row";
    buttonGroup.alignment = "center";
    
    var copyButton = buttonGroup.add("button", undefined, "Copy");
    var saveButton = buttonGroup.add("button", undefined, "Save as .txt");
    var closeButton = buttonGroup.add("button", undefined, "Close");
    
    // Copy function
    copyButton.onClick = function() {
        textArea.active = true;
        textArea.selection = [0, textArea.text.length];
    };
    
    // Save function
    saveButton.onClick = function() {
        var file = File.saveDialog("Save position data", "*.txt");
        if (file) {
            try {
                var filePath = file.fsName;
                if (filePath.indexOf(".txt") === -1) {
                    file = new File(filePath + ".txt");
                }
                
                if (file.open("w")) {
                    file.write(exportData);
                    file.close();
                    dialog.close();
                } else {
                    alert("Could not open file for writing");
                }
            } catch (e) {
                alert("Error saving file: " + e.toString());
            }
        }
    };
    
    // Close function
    closeButton.onClick = function() {
        dialog.close();
    };
    
    // Show dialog
    dialog.show();
    
})();