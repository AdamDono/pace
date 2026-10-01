// Global 3D Viewer initialization
// This script handles all 3D model viewers on the page

(function() {
    'use strict';

    // Store active viewers to prevent duplicates
    var initializedViewers = new Set();

    function init3DViewer(container) {
        if (!container) return;

        var sectionId = container.getAttribute('data-section-id');
        if (initializedViewers.has(sectionId)) return;
        initializedViewers.add(sectionId);

        var mediaFile = container.getAttribute('data-media-file');
        var hotspotsData = container.getAttribute('data-hotspots');
        var labelsData = container.getAttribute('data-labels');
        var animationsData = container.getAttribute('data-animations');

        var canvas = document.getElementById('canvas-' + sectionId);
        var loading = document.getElementById('loading-' + sectionId);
        var resetBtn = document.getElementById('reset-view-' + sectionId);
        var toggleHotspotsBtn = document.getElementById('toggle-hotspots-' + sectionId);
        var toggleLabelsBtn = document.getElementById('toggle-labels-' + sectionId);

        var hotspotPopup = document.getElementById('hotspot-popup-' + sectionId);
        var hotspotTitle = document.getElementById('hotspot-title-' + sectionId);
        var hotspotContent = document.getElementById('hotspot-content-' + sectionId);
        var closePopupBtn = document.getElementById('close-popup-' + sectionId);

        var labelPanel = document.getElementById('label-panel-' + sectionId);
        var draggableLabelsContainer = document.getElementById('draggable-labels-' + sectionId);
        var labelProgress = document.getElementById('label-progress-' + sectionId);

        if (!canvas || !loading) return;

        // Parse JSON data
        var hotspots = hotspotsData ? JSON.parse(hotspotsData) : [];
        var labels = labelsData ? JSON.parse(labelsData) : [];
        var animations = animationsData ? JSON.parse(animationsData) : [];

        // Scene setup
        var scene = new THREE.Scene();
        scene.background = new THREE.Color(0x1a1a2e);

        // Camera
        var camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
        camera.position.set(0, 2, 5);

        // Renderer
        var renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setPixelRatio(window.devicePixelRatio);
        renderer.shadowMap.enabled = true;

        // Controls
        var controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.minDistance = 2;
        controls.maxDistance = 10;

        // Lighting
        var ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        scene.add(ambientLight);

        var directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(5, 10, 7);
        directionalLight.castShadow = true;
        scene.add(directionalLight);

        var pointLight = new THREE.PointLight(0xffffff, 0.5);
        pointLight.position.set(-5, 5, -5);
        scene.add(pointLight);

        // Grid helper
        var gridHelper = new THREE.GridHelper(10, 10, 0x444444, 0x222222);
        scene.add(gridHelper);

        // Raycaster for click detection
        var raycaster = new THREE.Raycaster();
        var mouse = new THREE.Vector2();

        // Store loaded model and hotspot meshes
        var loadedModel = null;
        var hotspotMeshes = [];
        var hotspotsVisible = true;
        var labelsVisible = false;
        var completedLabels = [];
        var activeAnimations = [];

        // Create hotspot markers
        function createHotspot(hotspot) {
            var geometry = new THREE.SphereGeometry(hotspot.size || 0.1, 16, 16);
            var material = new THREE.MeshBasicMaterial({ color: hotspot.color || '#ff6b6b' });
            var sphere = new THREE.Mesh(geometry, material);

            sphere.position.set(hotspot.position_x, hotspot.position_y, hotspot.position_z);
            sphere.userData = { isHotspot: true, hotspotData: hotspot };

            // Add pulsing effect
            var pulseGeometry = new THREE.SphereGeometry((hotspot.size || 0.1) * 1.5, 16, 16);
            var pulseMaterial = new THREE.MeshBasicMaterial({
                color: hotspot.color || '#ff6b6b',
                transparent: true,
                opacity: 0.3
            });
            var pulseSphere = new THREE.Mesh(pulseGeometry, pulseMaterial);
            sphere.add(pulseSphere);

            scene.add(sphere);
            hotspotMeshes.push(sphere);

            return sphere;
        }

        // Initialize hotspots
        function initHotspots() {
            // Clear existing hotspots
            hotspotMeshes.forEach(function(mesh) {
                scene.remove(mesh);
            });
            hotspotMeshes = [];

            // Create new hotspots
            hotspots.forEach(function(hotspot) {
                if (hotspot.show_on_load !== false) {
                    createHotspot(hotspot);
                }
            });
        }

        // Initialize drag-and-drop labels
        function initLabels() {
            draggableLabelsContainer.innerHTML = '';
            completedLabels = [];

            labels.forEach(function(label) {
                var labelEl = document.createElement('div');
                labelEl.className = 'bg-cyan-100 border border-cyan-300 rounded-lg px-3 py-2 text-sm font-medium text-cyan-800 cursor-move shadow-sm hover:shadow-md transition-shadow';
                labelEl.textContent = label.label_text;
                labelEl.draggable = true;
                labelEl.dataset.labelId = label.id;
                labelEl.dataset.targetX = label.target_position_x;
                labelEl.dataset.targetY = label.target_position_y;
                labelEl.dataset.targetZ = label.target_position_z;
                labelEl.dataset.tolerance = label.tolerance_radius || 0.5;

                labelEl.addEventListener('dragstart', handleLabelDragStart);
                labelEl.addEventListener('dragend', handleLabelDragEnd);

                draggableLabelsContainer.appendChild(labelEl);
            });

            updateLabelProgress();
        }

        function handleLabelDragStart(e) {
            e.dataTransfer.setData('text/plain', e.target.dataset.labelId);
            e.target.classList.add('opacity-50');
        }

        function handleLabelDragEnd(e) {
            e.target.classList.remove('opacity-50');
        }

        // Handle drop on canvas
        canvas.addEventListener('dragover', function(e) {
            e.preventDefault();
        });

        canvas.addEventListener('drop', function(e) {
            e.preventDefault();
            var labelId = e.dataTransfer.getData('text/plain');
            var labelEl = document.querySelector('[data-label-id="' + labelId + '"]');

            if (!labelEl) return;

            // Calculate 3D position from 2D drop
            var rect = canvas.getBoundingClientRect();
            mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

            raycaster.setFromCamera(mouse, camera);

            // Raycast to find point on model
            var intersects = raycaster.intersectObjects(scene.children, true);

            if (intersects.length > 0) {
                var dropPoint = intersects[0].point;
                var targetX = parseFloat(labelEl.dataset.targetX);
                var targetY = parseFloat(labelEl.dataset.targetY);
                var targetZ = parseFloat(labelEl.dataset.targetZ);
                var tolerance = parseFloat(labelEl.dataset.tolerance);

                // Calculate distance to target
                var distance = Math.sqrt(
                    Math.pow(dropPoint.x - targetX, 2) +
                    Math.pow(dropPoint.y - targetY, 2) +
                    Math.pow(dropPoint.z - targetZ, 2)
                );

                if (distance <= tolerance) {
                    // Correct!
                    labelEl.classList.add('bg-green-100', 'border-green-300', 'text-green-800');
                    labelEl.classList.remove('bg-cyan-100', 'border-cyan-300', 'text-cyan-800');
                    labelEl.draggable = false;
                    labelEl.innerHTML += ' ✓';
                    completedLabels.push(labelId);

                    // Show success feedback
                    showFeedback('Correct! 🎉', 'success');
                } else {
                    // Incorrect
                    showFeedback('Try again! Distance: ' + distance.toFixed(2), 'error');
                }

                updateLabelProgress();
            }
        });

        function showFeedback(message, type) {
            var feedback = document.createElement('div');
            feedback.className = 'absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 px-4 py-2 rounded-lg text-white font-bold z-30 ' +
                (type === 'success' ? 'bg-green-500' : 'bg-red-500');
            feedback.textContent = message;
            container.appendChild(feedback);

            setTimeout(function() {
                feedback.remove();
            }, 1500);
        }

        function updateLabelProgress() {
            var total = labels.length;
            var completed = completedLabels.length;
            labelProgress.textContent = completed + '/' + total + ' labels placed';

            if (completed === total && total > 0) {
                labelProgress.textContent += ' - Complete! 🎉';
                labelProgress.classList.add('text-green-600', 'font-bold');
            }
        }

        // Animation system
        function initAnimations() {
            animations.forEach(function(animation) {
                if (animation.auto_play) {
                    playAnimation(animation);
                }
            });
        }

        function playAnimation(animation) {
            if (!loadedModel) return;

            var targetPart = null;
            if (animation.target_part_name) {
                // Find specific part in the model
                loadedModel.traverse(function(child) {
                    if (child.name === animation.target_part_name) {
                        targetPart = child;
                    }
                });
            } else {
                targetPart = loadedModel;
            }

            if (!targetPart) return;

            var startValues = animation.start_values ? JSON.parse(animation.start_values) : [0, 0, 0];
            var endValues = animation.end_values ? JSON.parse(animation.end_values) : [1, 1, 1];
            var duration = animation.duration * 1000; // Convert to milliseconds
            var startTime = Date.now();

            var animObj = {
                target: targetPart,
                type: animation.animation_type,
                startValues: startValues,
                endValues: endValues,
                duration: duration,
                startTime: startTime,
                loop: animation.loop
            };

            activeAnimations.push(animObj);
        }

        function updateAnimations() {
            var currentTime = Date.now();

            activeAnimations = activeAnimations.filter(function(anim) {
                var elapsed = currentTime - anim.startTime;
                var progress = Math.min(elapsed / anim.duration, 1);

                // Easing function (ease-in-out)
                var easedProgress = progress < 0.5
                    ? 2 * progress * progress
                    : 1 - Math.pow(-2 * progress + 2, 2) / 2;

                if (anim.type === 'rotation') {
                    anim.target.rotation.x = anim.startValues[0] + (anim.endValues[0] - anim.startValues[0]) * easedProgress;
                    anim.target.rotation.y = anim.startValues[1] + (anim.endValues[1] - anim.startValues[1]) * easedProgress;
                    anim.target.rotation.z = anim.startValues[2] + (anim.endValues[2] - anim.startValues[2]) * easedProgress;
                } else if (anim.type === 'translation') {
                    anim.target.position.x = anim.startValues[0] + (anim.endValues[0] - anim.startValues[0]) * easedProgress;
                    anim.target.position.y = anim.startValues[1] + (anim.endValues[1] - anim.startValues[1]) * easedProgress;
                    anim.target.position.z = anim.startValues[2] + (anim.endValues[2] - anim.startValues[2]) * easedProgress;
                } else if (anim.type === 'scale') {
                    var scale = anim.startValues[0] + (anim.endValues[0] - anim.startValues[0]) * easedProgress;
                    anim.target.scale.set(scale, scale, scale);
                } else if (anim.type === 'pulse') {
                    var pulseScale = anim.startValues[0] + (anim.endValues[0] - anim.startValues[0]) * Math.sin(elapsed / 1000 * Math.PI * 2);
                    anim.target.scale.set(pulseScale, pulseScale, pulseScale);
                }

                // Handle looping
                if (anim.loop && progress >= 1) {
                    anim.startTime = currentTime;
                    return true; // Keep animation
                }

                return progress < 1; // Remove if complete
            });
        }

        // Handle click on hotspots
        canvas.addEventListener('click', function(e) {
            if (!hotspotsVisible) return;

            var rect = canvas.getBoundingClientRect();
            mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

            raycaster.setFromCamera(mouse, camera);
            var intersects = raycaster.intersectObjects(hotspotMeshes);

            if (intersects.length > 0) {
                var hotspot = intersects[0].object.userData.hotspotData;
                showHotspotPopup(hotspot, e.clientX, e.clientY);
            }
        });

        function showHotspotPopup(hotspot, x, y) {
            hotspotTitle.textContent = hotspot.title;
            hotspotContent.innerHTML = hotspot.popup_content || hotspot.description || '';

            var containerRect = container.getBoundingClientRect();
            var popupX = x - containerRect.left;
            var popupY = y - containerRect.top;

            hotspotPopup.style.left = popupX + 'px';
            hotspotPopup.style.top = popupY + 'px';
            hotspotPopup.classList.remove('hidden');
        }

        // Close popup
        closePopupBtn.addEventListener('click', function() {
            hotspotPopup.classList.add('hidden');
        });

        // Toggle hotspots
        toggleHotspotsBtn.addEventListener('click', function() {
            hotspotsVisible = !hotspotsVisible;
            hotspotMeshes.forEach(function(mesh) {
                mesh.visible = hotspotsVisible;
            });
            toggleHotspotsBtn.classList.toggle('bg-green-500/30', hotspotsVisible);
        });

        // Toggle labels
        toggleLabelsBtn.addEventListener('click', function() {
            labelsVisible = !labelsVisible;
            labelPanel.classList.toggle('hidden', !labelsVisible);
            toggleLabelsBtn.classList.toggle('bg-green-500/30', labelsVisible);

            if (labelsVisible && draggableLabelsContainer && draggableLabelsContainer.children.length === 0) {
                initLabels();
            }
        });

        if (typeof THREE === 'undefined') {
            console.warn('Three.js library is still loading, retrying in 150ms...');
            setTimeout(function() {
                delete container.dataset.threeInitialized;
                init3DViewer(container);
            }, 150);
            return;
        }

        // Load 3D model or show interactive demo
        var cleanPath = (mediaFile || '').trim();
        if (cleanPath) {
            var modelPath = cleanPath;
            var fileExtension = cleanPath.split('?')[0].split('.').pop().toLowerCase();

            console.log('=== 3D Model Load ===', { modelPath: modelPath, fileExtension: fileExtension, sectionId: sectionId });

            if (fileExtension === 'glb' || fileExtension === 'gltf') {
                if (typeof THREE.GLTFLoader === 'undefined') {
                    console.warn('GLTFLoader not ready, retrying in 150ms...');
                    setTimeout(function() {
                        delete container.dataset.threeInitialized;
                        init3DViewer(container);
                    }, 150);
                    return;
                }
                var gltfLoader = new THREE.GLTFLoader();
                gltfLoader.load(modelPath, function(gltf) {
                    loadedModel = gltf.scene;
                    loadedModel.position.set(0, 0, 0);
                    loadedModel.scale.set(1, 1, 1);
                    scene.add(loadedModel);

                    // Auto-center and scale
                    var box = new THREE.Box3().setFromObject(loadedModel);
                    var center = box.getCenter(new THREE.Vector3());
                    var size = box.getSize(new THREE.Vector3());

                    loadedModel.position.sub(center);
                    var maxDim = Math.max(size.x, size.y, size.z) || 1;
                    var scale = 3 / maxDim;
                    loadedModel.scale.set(scale, scale, scale);

                    initHotspots();
                    initAnimations();

                    loading.style.display = 'none';
                }, function(xhr) {
                    if (xhr.total && xhr.total > 0) {
                        var pct = Math.round((xhr.loaded / xhr.total) * 100);
                        var pText = loading.querySelector('p');
                        if (pText) pText.textContent = 'Loading 3D model (' + pct + '%)...';
                    }
                }, function(error) {
                    console.error('Error loading 3D model:', error);
                    loading.innerHTML = '<div class="p-4 text-center"><p class="text-red-400 font-semibold">Could not load 3D model file.</p><p class="text-xs text-gray-400 mt-1">Path: ' + modelPath + '</p><button class="mt-3 px-3 py-1 bg-indigo-600 text-white rounded text-xs" onclick="this.closest(\'.3d-viewer, .three-d-viewer\').querySelector(\'#loading-' + sectionId + '\').style.display=\'none\'">Dismiss</button></div>';
                });
            } else if (fileExtension === 'obj') {
                if (typeof THREE.OBJLoader === 'undefined') {
                    console.warn('OBJLoader not ready, retrying in 150ms...');
                    setTimeout(function() {
                        delete container.dataset.threeInitialized;
                        init3DViewer(container);
                    }, 150);
                    return;
                }
                var objLoader = new THREE.OBJLoader();
                objLoader.load(modelPath, function(obj) {
                    loadedModel = obj;
                    loadedModel.position.set(0, 0, 0);
                    scene.add(loadedModel);

                    // Auto-center and scale
                    var box = new THREE.Box3().setFromObject(loadedModel);
                    var center = box.getCenter(new THREE.Vector3());
                    var size = box.getSize(new THREE.Vector3());

                    loadedModel.position.sub(center);
                    var maxDim = Math.max(size.x, size.y, size.z) || 1;
                    var scale = 3 / maxDim;
                    loadedModel.scale.set(scale, scale, scale);

                    initHotspots();
                    initAnimations();

                    loading.style.display = 'none';
                }, function(xhr) {
                    if (xhr.total && xhr.total > 0) {
                        var pct = Math.round((xhr.loaded / xhr.total) * 100);
                        var pText = loading.querySelector('p');
                        if (pText) pText.textContent = 'Loading 3D model (' + pct + '%)...';
                    }
                }, function(error) {
                    console.error('Error loading OBJ model:', error);
                    loading.innerHTML = '<div class="p-4 text-center"><p class="text-red-400 font-semibold">Could not load 3D model file.</p><p class="text-xs text-gray-400 mt-1">Path: ' + modelPath + '</p><button class="mt-3 px-3 py-1 bg-indigo-600 text-white rounded text-xs" onclick="this.closest(\'.3d-viewer, .three-d-viewer\').querySelector(\'#loading-' + sectionId + '\').style.display=\'none\'">Dismiss</button></div>';
                });
            } else {
                // Unsupported extension
                loading.innerHTML = '<div class="p-4 text-center"><p class="text-yellow-400 font-semibold">Unsupported 3D file format (.' + fileExtension + ').</p><p class="text-xs text-gray-300 mt-1">Please use .glb, .gltf, or .obj 3D models.</p></div>';
            }
        } else {
            // Interactive 3D Demo Object if no media file uploaded
            var geometry = new THREE.TorusKnotGeometry(1.2, 0.4, 64, 16);
            var material = new THREE.MeshStandardMaterial({
                color: 0x6366f1,
                roughness: 0.3,
                metalness: 0.7
            });
            var demoMesh = new THREE.Mesh(geometry, material);
            demoMesh.castShadow = true;
            loadedModel = demoMesh;
            scene.add(demoMesh);
            loading.style.display = 'none';

            initHotspots();
        }

        // Reset view button
        resetBtn.addEventListener('click', function() {
            camera.position.set(0, 2, 5);
            controls.reset();
        });

        // Animation loop
        function animate() {
            requestAnimationFrame(animate);
            controls.update();

            // Animate hotspot pulses
            var time = Date.now() * 0.001;
            hotspotMeshes.forEach(function(mesh) {
                if (mesh.children.length > 0) {
                    mesh.children[0].scale.setScalar(1 + Math.sin(time * 2) * 0.2);
                }
            });

            // Update model animations
            updateAnimations();

            renderer.render(scene, camera);
        }
        animate();

        // Handle resize
        window.addEventListener('resize', function() {
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
        });

        // Initial resize
        setTimeout(function() {
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
        }, 100);
    }

    // Initialize all 3D viewers on the page
    function initAll3DViewers() {
        var viewers = document.querySelectorAll('.3d-viewer');
        viewers.forEach(function(viewer) {
            init3DViewer(viewer);
        });
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll3DViewers);
    } else {
        initAll3DViewers();
    }

    // Also initialize after HTMX content loads
    if (typeof htmx !== 'undefined') {
        htmx.on('htmx:afterSwap', function(evt) {
            initAll3DViewers();
        });
    }

    // Also use MutationObserver for dynamic content
    var observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.addedNodes) {
                mutation.addedNodes.forEach(function(node) {
                    if (node.nodeType === 1) { // Element node
                        var viewers = node.querySelectorAll ? node.querySelectorAll('.3d-viewer') : [];
                        viewers.forEach(function(viewer) {
                            init3DViewer(viewer);
                        });
                    }
                });
            }
        });
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

})();
