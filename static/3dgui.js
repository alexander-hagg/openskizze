let scene, camera, renderer, controls;

let margin = 20;
let solution_margin = 4;

init();
animate();

function init() {
    scene = new THREE.Scene();
    THREE.ColorManagement.legacyMode = false

    camera = new THREE.PerspectiveCamera(75, 1, 0.1, 1000);
    let spacing_scaling = 5; // TODO This magic number needs to be automatically calculated based on the incoming sat image and a fixed border. Change it from a scaling to an additivate factor.
    
    
    const container = document.getElementById("mainContent");
    renderer = new THREE.WebGLRenderer();
    renderer.setSize(container.offsetWidth-margin,container.offsetWidth-margin);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap; // PCF shadow mapping

    const dirLight = new THREE.DirectionalLight(0xffffff, 1); // white, intensity: 1
    dirLight.position.set(10, 10, 10); // adjust as needed
    //dirLight.target.position.set(-10,0,5);
    dirLight.castShadow = true;
    scene.add(dirLight);

    // Optional: Add an ambient light for softer lighting of shadows
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.4); // white, intensity: 0.4
    scene.add(ambientLight);

    container.appendChild(renderer.domElement);

    controls = new THREE.OrbitControls(camera, renderer.domElement);

    // Dynamic grid size calculation (assuming it's a square grid)
    fetch('/get-voxel-meshes')
        .then(response => response.json())
        .then(voxelMeshes => {
            const gridSize = Math.sqrt(voxelMeshes.length); 
            const gridCenter = solution_margin * (gridSize - 1) * (gridSize + 1) / 2;

            // Adjust camera position and FOV
            camera.position.set(gridCenter, gridCenter, gridSize*17); // Higher Z value
            controls.target.set(gridCenter, gridCenter, 0);
            controls.update();

            // Load voxel meshes
            voxelMeshes.forEach((voxelData, index) => {
                createVoxelMesh(voxelData, index, gridSize, solution_margin);
            });
        })
        .catch(error => console.error('Error fetching voxel data:', error));

}

function loadAndCreateBackgroundImage(imageUrl, positionX, positionY, width, height) {
    const textureLoader = new THREE.TextureLoader();
    texture = textureLoader.load(imageUrl, function(texture) {
        const planeGeometry = new THREE.PlaneGeometry(width, height);
        const planeMaterial = new THREE.MeshBasicMaterial({ map: texture, side: THREE.DoubleSide });
        const plane = new THREE.Mesh(planeGeometry, planeMaterial);
        
        // Adjust position as needed
        plane.position.set(positionX, positionY, 0); // Positioned slightly behind the voxel mesh
        plane.receiveShadow = true;
        plane.castShadow = false; // typically a plane doesn't need to cast shadows

        scene.add(plane);
    });
    texture.encoding = THREE.sRGBEncoding;
}

function createVoxelMesh(voxelData, index, gridSize, solution_margin) {
    const geometry = new THREE.BoxGeometry(1, 1, 1);
    const material = new THREE.MeshStandardMaterial();
    
    let xOffset = (index % gridSize) * gridSize * solution_margin; // Adjusted for spacing
    let yOffset = Math.floor(index / gridSize) * gridSize * solution_margin; // Adjusted for spacing
    
    for (let x = 0; x < voxelData.length; x++) {
        for (let y = 0; y < voxelData[x].length; y++) {
            const voxelHeight = voxelData[y][x];
            if (voxelHeight > 0) {
                const voxel = new THREE.Mesh(geometry, material.clone());
                voxel.position.set(x + xOffset, y + yOffset, voxelHeight / 2);
                voxel.scale.set(1, 1, voxelHeight);
                voxel.material.color.set(new THREE.Color(`hsl(${voxelHeight * 360 / 3}, 50%, 50%)`));
                voxel.castShadow = true;
                voxel.receiveShadow = true;

                scene.add(voxel);

            }
        }
    }

    // Create and add the border for this voxel mesh
    maxHeight = 3;
    const borderGeometry = new THREE.BoxGeometry(voxelData.length, voxelData.length, maxHeight);
    const borderMaterial = new THREE.LineBasicMaterial({ color: 0xffffff });
    const borderEdges = new THREE.EdgesGeometry(borderGeometry);
    const border = new THREE.LineSegments(borderEdges, borderMaterial);
    border.position.set(xOffset+0.5*voxelData.length, yOffset+0.5*voxelData.length, maxHeight / 2);
    scene.add(border);

    const imageUrl = 'static/img/mapsat.png'; // Replace with the actual path
    const imageWidth = voxelData.length; // Set the width of the image
    const imageHeight = voxelData.length; // Set the height of the image
    loadAndCreateBackgroundImage(imageUrl, xOffset + 0.5 * voxelData.length, yOffset + 0.5 * voxelData.length, imageWidth*1.3, imageHeight*1.3);

}

function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
}

window.addEventListener('resize', onWindowResize, false);

function onWindowResize() {
    camera.updateProjectionMatrix();
    renderer.setSize(document.getElementById("mainContent").offsetWidth-margin,document.getElementById("mainContent").offsetWidth-margin);
    controls.update();
    renderer.render(scene, camera);
}
