// 3D Hotspot Editor Logic with AMD Protection & Robust Three.js Loader
let _hsScene, _hsCamera, _hsRenderer, _hsControls, _hsModel, _hsAnimId;
let _currentHotspots = [];
let _hsRaycaster = null;
let _hsMouse = null;
let _pendingModelUrl = '';
let _pendingCaption = '';
let _pendingHeight = '';
let _hsResizeObserver = null;
let _hsPendingClickPoint = null;

function openHotspotEditor(url, caption, height) {
    _pendingModelUrl = (url || '').trim();
    _pendingCaption = (caption || '').trim();
    _pendingHeight = height || '520';
    _currentHotspots = [];

    // Create UI if not exists
    let ui = document.getElementById('model3d-hotspot-ui');
    if (!ui) {
        ui = document.createElement('div');
        ui.id = 'model3d-hotspot-ui';
        ui.style.cssText = 'position:fixed;inset:0;background:#0f0f1a;z-index:99999;display:flex;flex-direction:column;font-family:system-ui,-apple-system,sans-serif;';
        ui.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;padding:14px 24px;background:#1a1a2e;color:white;border-bottom:1px solid #2d2d44;box-shadow:0 4px 6px -1px rgba(0,0,0,0.2);">
                <div>
                    <h2 style="margin:0;font-size:17px;font-weight:700;display:flex;align-items:center;gap:8px;">
                        <span>📍</span> Add Hotspots to 3D Model
                    </h2>
                    <p style="margin:3px 0 0;font-size:12px;color:#a5b4fc;">Click anywhere on the 3D model to place and label a hotspot. Drag to rotate, scroll to zoom.</p>
                </div>
                <div style="display:flex;gap:10px;align-items:center;">
                    <button onclick="closeHotspotEditor()" style="padding:8px 16px;background:rgba(255,255,255,0.06);color:#e2e8f0;border:1px solid #4f4f7a;border-radius:6px;cursor:pointer;font-size:13px;font-weight:500;transition:background 0.2s;">Cancel</button>
                    <button onclick="finishHotspotEditor()" id="hs-insert-btn" style="padding:8px 18px;background:#4f46e5;color:white;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:13px;display:flex;align-items:center;gap:6px;box-shadow:0 2px 8px rgba(79,70,229,0.4);">
                        <span>Insert to Lesson</span>
                        <span id="hs-count-badge" style="background:rgba(255,255,255,0.2);padding:2px 7px;border-radius:10px;font-size:11px;">0</span>
                    </button>
                </div>
            </div>
            <div style="flex:1;position:relative;display:flex;overflow:hidden;">
                <div style="flex:1;position:relative;background:#0f0f1a;" id="hs-canvas-container">
                    <canvas id="hs-canvas" style="width:100%;height:100%;display:block;outline:none;cursor:grab;"></canvas>
                    
                    <!-- Loading / Error Overlay -->
                    <div id="hs-loading" style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;color:white;background:#0f0f1a;z-index:20;">
                        <div id="hs-loading-spinner" style="font-size:42px;margin-bottom:12px;animation:hsspin 1.5s linear infinite;">🧊</div>
                        <p id="hs-loading-text" style="font-size:14px;color:#c7d2fe;margin:0;font-weight:500;">Loading 3D Model...</p>
                        <p id="hs-loading-subtext" style="font-size:11px;color:#818cf8;margin:6px 0 0;max-width:380px;text-align:center;"></p>
                    </div>

                    <!-- Helper pill overlay -->
                    <div style="position:absolute;bottom:16px;left:16px;background:rgba(15,15,26,0.75);backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,0.1);border-radius:24px;padding:6px 14px;display:flex;gap:12px;font-size:11px;color:#94a3b8;pointer-events:none;z-index:10;">
                        <span>🖱️ Drag to rotate</span>
                        <span>🔍 Scroll to zoom</span>
                        <span>📍 Click model to add hotspot</span>
                    </div>

                    <!-- Hotspot Input Popup Dialog -->
                    <div id="hs-dialog" style="display:none;position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:340px;background:#1e1e38;border:1px solid #4338ca;border-radius:12px;box-shadow:0 20px 25px -5px rgba(0,0,0,0.5),0 10px 10px -5px rgba(0,0,0,0.3);padding:18px;color:white;z-index:30;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                            <h4 style="margin:0;font-size:15px;color:#e0e7ff;font-weight:600;display:flex;align-items:center;gap:6px;">
                                <span>📍</span> New Hotspot
                            </h4>
                            <button onclick="cancelNewHotspot()" style="background:transparent;border:none;color:#94a3b8;cursor:pointer;font-size:16px;line-height:1;">✕</button>
                        </div>
                        <div style="margin-bottom:12px;">
                            <label style="display:block;font-size:12px;color:#a5b4fc;margin-bottom:4px;font-weight:500;">Hotspot Title *</label>
                            <input id="hs-input-title" type="text" placeholder="e.g. Heart Valve, Turbine Blade..." 
                                style="width:100%;box-sizing:border-box;background:#0f0f1a;border:1px solid #3730a3;border-radius:6px;padding:8px 10px;color:white;font-size:13px;outline:none;" />
                        </div>
                        <div style="margin-bottom:16px;">
                            <label style="display:block;font-size:12px;color:#a5b4fc;margin-bottom:4px;font-weight:500;">Description (Optional)</label>
                            <textarea id="hs-input-desc" rows="3" placeholder="Explain what students should observe at this point..." 
                                style="width:100%;box-sizing:border-box;background:#0f0f1a;border:1px solid #3730a3;border-radius:6px;padding:8px 10px;color:white;font-size:12px;outline:none;resize:none;"></textarea>
                        </div>
                        <div style="display:flex;justify-content:flex-end;gap:8px;">
                            <button onclick="cancelNewHotspot()" style="padding:6px 12px;background:transparent;border:1px solid #4b5563;color:#d1d5db;border-radius:6px;font-size:12px;cursor:pointer;">Cancel</button>
                            <button onclick="saveNewHotspot()" style="padding:6px 16px;background:#4f46e5;border:none;color:white;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;">Add Hotspot</button>
                        </div>
                    </div>
                </div>

                <!-- Right Sidebar for Hotspots List -->
                <div style="width:300px;background:#1a1a2e;border-left:1px solid #2d2d44;padding:18px;color:white;overflow-y:auto;display:flex;flex-direction:column;" id="hs-list">
                    <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #2d2d44;padding-bottom:12px;">
                        <h3 style="margin:0;font-size:13px;text-transform:uppercase;letter-spacing:0.05em;color:#818cf8;font-weight:700;">Hotspots List</h3>
                        <span id="hs-sidebar-count" style="font-size:11px;color:#94a3b8;">0 added</span>
                    </div>
                    <div id="hs-items" style="display:flex;flex-direction:column;gap:10px;margin-top:14px;flex:1;">
                        <div style="text-align:center;padding:32px 12px;color:#6b7280;">
                            <div style="font-size:28px;margin-bottom:8px;opacity:0.6;">📍</div>
                            <p style="font-size:12px;margin:0;color:#9ca3af;line-height:1.5;">No hotspots yet.<br>Click anywhere on the 3D model to place your first hotspot.</p>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(ui);

        // Add CSS keyframe for spinner if not present
        if (!document.getElementById('hs-spin-style')) {
            const st = document.createElement('style');
            st.id = 'hs-spin-style';
            st.textContent = '@keyframes hsspin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }';
            document.head.appendChild(st);
        }
    }

    ui.style.display = 'flex';
    const loadingEl = document.getElementById('hs-loading');
    loadingEl.style.display = 'flex';
    document.getElementById('hs-loading-spinner').style.display = 'block';
    document.getElementById('hs-loading-text').textContent = 'Loading 3D Model...';
    document.getElementById('hs-loading-subtext').textContent = '';
    document.getElementById('hs-dialog').style.display = 'none';

    updateHotspotSidebar();

    // Ensure Three.js, OrbitControls, and Loaders are loaded safely (bypassing Monaco AMD loader if present)
    ensureThreeStack(function(err) {
        if (err) {
            showHsError("Failed to load 3D graphics libraries: " + err.message);
            return;
        }
        // Wait for DOM layout pass so container has non-zero clientWidth & clientHeight
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                initHsEditor();
            });
        });
    });
}

// Safely load Three.js stack without Monaco's AMD RequireJS capturing it
function ensureThreeStack(callback) {
    if (window.THREE && window.THREE.OrbitControls && window.THREE.GLTFLoader && window.THREE.OBJLoader) {
        return callback(null);
    }

    const scripts = [
        'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js',
        'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js',
        'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js',
        'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/DRACOLoader.js',
        'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/OBJLoader.js'
    ];

    function loadScript(src, next) {
        // Check if library already exposed
        if (src.includes('three.min.js') && window.THREE) return next();
        if (src.includes('OrbitControls.js') && window.THREE && window.THREE.OrbitControls) return next();
        if (src.includes('GLTFLoader.js') && window.THREE && window.THREE.GLTFLoader) return next();
        if (src.includes('DRACOLoader.js') && window.THREE && window.THREE.DRACOLoader) return next();
        if (src.includes('OBJLoader.js') && window.THREE && window.THREE.OBJLoader) return next();

        // Check if script tag with same src exists and loaded
        const existing = document.querySelector(`script[src="${src}"]`);
        if (existing && existing.dataset.loaded === 'true') {
            return next();
        }

        // IMPORTANT: Monaco's loader defines window.define with AMD. If defined, UMD scripts like Three.js
        // call define() instead of assigning to window.THREE! Temporarily hide window.define.
        const hadAmd = typeof window.define === 'function' && window.define.amd;
        const savedDefine = window.define;
        if (hadAmd) {
            window.define = undefined;
        }

        const s = document.createElement('script');
        s.src = src;
        s.async = false;
        s.onload = function() {
            s.dataset.loaded = 'true';
            if (hadAmd && savedDefine) {
                window.define = savedDefine;
            }
            next();
        };
        s.onerror = function(e) {
            if (hadAmd && savedDefine) {
                window.define = savedDefine;
            }
            console.error('Failed to load script:', src, e);
            next(new Error('Failed to load ' + src));
        };
        document.head.appendChild(s);
    }

    let i = 0;
    function step() {
        if (i >= scripts.length) {
            return callback(null);
        }
        loadScript(scripts[i++], function(err) {
            if (err) return callback(err);
            step();
        });
    }
    step();
}

function showHsError(msg, allowInsertAnyway) {
    const loadingEl = document.getElementById('hs-loading');
    if (!loadingEl) return;
    loadingEl.style.display = 'flex';
    document.getElementById('hs-loading-spinner').style.display = 'none';
    document.getElementById('hs-loading-text').innerHTML = `
        <span style="color:#f87171;font-weight:700;">⚠️ Could not load 3D model</span>
    `;
    document.getElementById('hs-loading-subtext').innerHTML = `
        <div style="margin-top:8px;font-size:12px;color:#e2e8f0;background:rgba(239,68,68,0.15);padding:10px 14px;border-radius:8px;border:1px solid rgba(239,68,68,0.3);line-height:1.4;">
            ${msg}
        </div>
        <div style="margin-top:14px;display:flex;gap:10px;justify-content:center;">
            <button onclick="initHsEditor()" style="padding:6px 14px;background:#4f46e5;color:white;border:none;border-radius:6px;font-size:12px;cursor:pointer;font-weight:600;">🔄 Retry Loading</button>
            <button onclick="finishHotspotEditor()" style="padding:6px 14px;background:#374151;color:white;border:none;border-radius:6px;font-size:12px;cursor:pointer;">Insert Without Hotspots</button>
        </div>
    `;
}

function initHsEditor() {
    const canvas = document.getElementById('hs-canvas');
    const container = document.getElementById('hs-canvas-container');
    if (!canvas || !container) return;

    if (_hsAnimId) {
        cancelAnimationFrame(_hsAnimId);
        _hsAnimId = null;
    }

    // Determine dimensions with fallbacks if layout isn't fully ready
    let width = container.clientWidth || (window.innerWidth - 300);
    let height = container.clientHeight || (window.innerHeight - 60);
    if (width <= 0) width = 800;
    if (height <= 0) height = 600;

    // Reset scene
    _hsScene = new THREE.Scene();
    _hsScene.background = new THREE.Color(0x0f0f1a);

    _hsCamera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
    _hsCamera.position.set(0, 1.5, 4);

    if (!_hsRenderer) {
        _hsRenderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: false });
    }
    _hsRenderer.setSize(width, height);
    _hsRenderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    _hsRenderer.shadowMap.enabled = true;

    if (_hsControls) {
        _hsControls.dispose();
    }
    _hsControls = new THREE.OrbitControls(_hsCamera, _hsRenderer.domElement);
    _hsControls.enableDamping = true;
    _hsControls.dampingFactor = 0.08;
    _hsControls.minDistance = 0.5;
    _hsControls.maxDistance = 50;

    // High quality studio lighting
    _hsScene.add(new THREE.AmbientLight(0xffffff, 0.85));

    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444466, 0.6);
    _hsScene.add(hemiLight);

    const dl1 = new THREE.DirectionalLight(0xffffff, 1.0);
    dl1.position.set(5, 10, 7);
    dl1.castShadow = true;
    _hsScene.add(dl1);

    const dl2 = new THREE.DirectionalLight(0xa5b4fc, 0.6);
    dl2.position.set(-5, -6, -6);
    _hsScene.add(dl2);

    // Subtle 3D floor grid for spatial reference
    const grid = new THREE.GridHelper(10, 10, 0x312e81, 0x1e1e38);
    grid.position.y = -1.5;
    _hsScene.add(grid);

    _hsRaycaster = new THREE.Raycaster();
    _hsMouse = new THREE.Vector2();

    // Auto resize handler via ResizeObserver
    if (_hsResizeObserver) {
        _hsResizeObserver.disconnect();
    }
    _hsResizeObserver = new ResizeObserver(entries => {
        for (let entry of entries) {
            const cr = entry.contentRect;
            if (cr.width > 50 && cr.height > 50 && _hsRenderer && _hsCamera) {
                _hsCamera.aspect = cr.width / cr.height;
                _hsCamera.updateProjectionMatrix();
                _hsRenderer.setSize(cr.width, cr.height);
            }
        }
    });
    _hsResizeObserver.observe(container);

    // Animation render loop
    const animate = () => {
        _hsAnimId = requestAnimationFrame(animate);
        _hsControls.update();

        // Pulsing animation for hotspot sphere markers
        if (_hsModel) {
            const time = Date.now() * 0.003;
            _hsModel.children.forEach(child => {
                if (child.userData && child.userData.isHotspot) {
                    const sc = (1 / (_hsModel.scale.x || 1)) * (1 + Math.sin(time) * 0.2);
                    child.scale.setScalar(sc);
                }
            });
        }

        _hsRenderer.render(_hsScene, _hsCamera);
    };
    animate();

    // Setup Click vs Drag detection on canvas to prevent rotating from triggering hotspot prompt
    setupCanvasClickHandler(canvas);

    // Load Model File
    loadTargetModel(_pendingModelUrl);
}

function loadTargetModel(modelUrl) {
    if (!modelUrl) {
        showHsError("No 3D model URL provided.");
        return;
    }

    const loadingText = document.getElementById('hs-loading-text');
    const loadingSubtext = document.getElementById('hs-loading-subtext');
    const loadingSpinner = document.getElementById('hs-loading-spinner');
    if (loadingText) loadingText.textContent = 'Downloading 3D model...';
    if (loadingSpinner) loadingSpinner.style.display = 'block';

    const urlClean = modelUrl.split('?')[0];
    const ext = urlClean.includes('.') ? urlClean.split('.').pop().toLowerCase() : '';

    const onProgress = (xhr) => {
        if (xhr.lengthComputable && xhr.total > 0) {
            const pct = Math.round((xhr.loaded / xhr.total) * 100);
            if (loadingText) loadingText.textContent = `Loading 3D Model (${pct}%)...`;
        }
    };

    const afterLoad = (obj) => {
        _hsModel = obj;

        // Traverse meshes to ensure visible materials and shadows
        obj.traverse(child => {
            if (child.isMesh) {
                child.castShadow = true;
                child.receiveShadow = true;
                if (child.material) {
                    if (Array.isArray(child.material)) {
                        child.material.forEach(m => { m.side = THREE.DoubleSide; });
                    } else {
                        child.material.side = THREE.DoubleSide;
                    }
                }
            }
        });

        // Compute bounding box and center model
        const box = new THREE.Box3().setFromObject(obj);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z) || 1;
        const scale = 3.2 / maxDim;

        obj.scale.setScalar(scale);
        obj.position.sub(center.multiplyScalar(scale));

        _hsScene.add(obj);

        // Position camera to view model nicely
        _hsCamera.position.set(0, 1.2, 3.8);
        _hsControls.target.set(0, 0, 0);
        _hsControls.update();

        // Render any existing hotspots
        renderHotspotsOnModel();

        // Hide loading
        const loadingEl = document.getElementById('hs-loading');
        if (loadingEl) loadingEl.style.display = 'none';
    };

    // Loaders
    function tryGLTF(onFail) {
        if (!window.THREE.GLTFLoader) {
            return onFail && onFail(new Error("GLTFLoader not available"));
        }
        const loader = new THREE.GLTFLoader();

        // Attach DRACOLoader if available
        if (window.THREE.DRACOLoader) {
            try {
                const dracoLoader = new THREE.DRACOLoader();
                dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/');
                loader.setDRACOLoader(dracoLoader);
            } catch(e) {
                console.warn("DRACOLoader init warning:", e);
            }
        }

        loader.load(
            modelUrl,
            gltf => afterLoad(gltf.scene || gltf.scenes[0]),
            onProgress,
            err => {
                console.warn("GLTFLoader error on", modelUrl, err);
                if (onFail) onFail(err);
                else showHsError("Failed to parse GLTF/GLB model: " + (err.message || 'Check file format or CORS permissions.'));
            }
        );
    }

    function tryOBJ(onFail) {
        if (!window.THREE.OBJLoader) {
            return onFail && onFail(new Error("OBJLoader not available"));
        }
        const loader = new THREE.OBJLoader();
        loader.load(
            modelUrl,
            obj => afterLoad(obj),
            onProgress,
            err => {
                console.warn("OBJLoader error on", modelUrl, err);
                if (onFail) onFail(err);
                else showHsError("Failed to load OBJ model: " + (err.message || 'Check file format or CORS permissions.'));
            }
        );
    }

    // Determine strategy:
    if (ext === 'obj') {
        tryOBJ(() => tryGLTF());
    } else {
        // .glb, .gltf, or Cloudinary raw upload URLs
        tryGLTF(gltfErr => {
            console.log("GLTF load failed, attempting OBJ loader fallback...");
            tryOBJ(objErr => {
                showHsError(`Could not load model. Both GLTF and OBJ loaders failed. (${gltfErr.message || 'Unsupported format'})`);
            });
        });
    }
}

// Click vs Drag handler: only trigger hotspot creation if the user clicked without rotating
function setupCanvasClickHandler(canvas) {
    let downPos = { x: 0, y: 0, time: 0 };

    canvas.onpointerdown = (e) => {
        downPos = { x: e.clientX, y: e.clientY, time: Date.now() };
    };

    canvas.onpointerup = (e) => {
        const dist = Math.hypot(e.clientX - downPos.x, e.clientY - downPos.y);
        const elapsed = Date.now() - downPos.time;

        // If mouse moved > 6px or was held > 500ms, user was rotating/panning/zooming
        if (dist > 6 || elapsed > 500) return;

        // Valid click on canvas! Perform Raycasting
        handleCanvasModelClick(e, canvas);
    };
}

function handleCanvasModelClick(e, canvas) {
    if (!_hsModel || !_hsCamera || !_hsRaycaster) return;

    const rect = canvas.getBoundingClientRect();
    _hsMouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    _hsMouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    _hsRaycaster.setFromCamera(_hsMouse, _hsCamera);

    const intersects = _hsRaycaster.intersectObject(_hsModel, true);
    if (intersects.length > 0) {
        // We clicked a point on the model surface!
        const hitPoint = intersects[0].point;
        const localPoint = _hsModel.worldToLocal(hitPoint.clone());

        _hsPendingClickPoint = {
            x: localPoint.x,
            y: localPoint.y,
            z: localPoint.z,
            clientX: e.clientX,
            clientY: e.clientY
        };

        // Open hotspot input dialog
        const dialog = document.getElementById('hs-dialog');
        const titleInput = document.getElementById('hs-input-title');
        const descInput = document.getElementById('hs-input-desc');

        titleInput.value = '';
        descInput.value = '';
        dialog.style.display = 'block';

        // Auto-focus title
        setTimeout(() => titleInput.focus(), 50);
    }
}

function cancelNewHotspot() {
    _hsPendingClickPoint = null;
    const dialog = document.getElementById('hs-dialog');
    if (dialog) dialog.style.display = 'none';
}

function saveNewHotspot() {
    if (!_hsPendingClickPoint) return;

    const titleInput = document.getElementById('hs-input-title');
    const descInput = document.getElementById('hs-input-desc');

    const title = (titleInput.value || '').trim();
    if (!title) {
        alert('Please enter a title for this hotspot.');
        titleInput.focus();
        return;
    }

    const desc = (descInput.value || '').trim();
    const hsId = 'hs_' + Date.now();

    _currentHotspots.push({
        id: hsId,
        title: title,
        description: desc,
        x: _hsPendingClickPoint.x,
        y: _hsPendingClickPoint.y,
        z: _hsPendingClickPoint.z
    });

    cancelNewHotspot();
    renderHotspotsOnModel();
    updateHotspotSidebar();
}

function renderHotspotsOnModel() {
    if (!_hsModel) return;

    // Remove existing hotspot meshes from the model
    for (let i = _hsModel.children.length - 1; i >= 0; i--) {
        const child = _hsModel.children[i];
        if (child.userData && child.userData.isHotspot) {
            _hsModel.remove(child);
        }
    }

    const geo = new THREE.SphereGeometry(0.06, 16, 16);
    const mat = new THREE.MeshBasicMaterial({ color: 0xef4444 });

    _currentHotspots.forEach(hs => {
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.set(hs.x, hs.y, hs.z);

        // Keep marker visual scale consistent regardless of model scale
        const sc = 1 / (_hsModel.scale.x || 1);
        mesh.scale.setScalar(sc);
        mesh.userData = { isHotspot: true, hsData: hs };

        _hsModel.add(mesh);
    });
}

function updateHotspotSidebar() {
    const list = document.getElementById('hs-items');
    const countBadge = document.getElementById('hs-count-badge');
    const sidebarCount = document.getElementById('hs-sidebar-count');

    if (countBadge) countBadge.textContent = _currentHotspots.length;
    if (sidebarCount) sidebarCount.textContent = `${_currentHotspots.length} added`;

    if (!list) return;

    if (_currentHotspots.length === 0) {
        list.innerHTML = `
            <div style="text-align:center;padding:32px 12px;color:#6b7280;">
                <div style="font-size:28px;margin-bottom:8px;opacity:0.6;">📍</div>
                <p style="font-size:12px;margin:0;color:#9ca3af;line-height:1.5;">No hotspots yet.<br>Click anywhere on the 3D model to place your first hotspot.</p>
            </div>
        `;
        return;
    }

    let html = '';
    _currentHotspots.forEach((hs, idx) => {
        html += `
            <div style="background:#252540;border:1px solid #3730a3;padding:12px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.2);">
                <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;">
                    <div style="flex:1;">
                        <span style="font-size:10px;font-weight:700;color:#818cf8;text-transform:uppercase;">#${idx + 1}</span>
                        <h4 style="margin:2px 0 4px;font-size:13px;font-weight:600;color:#f1f5f9;">${escapeHtml(hs.title)}</h4>
                        ${hs.description ? `<p style="margin:0;font-size:11px;color:#94a3b8;line-height:1.4;">${escapeHtml(hs.description)}</p>` : ''}
                    </div>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.08);">
                    <button onclick="focusHotspot('${hs.id}')" style="background:rgba(99,102,241,0.15);color:#a5b4fc;border:1px solid rgba(99,102,241,0.3);padding:3px 8px;border-radius:4px;font-size:11px;cursor:pointer;">🎯 Focus</button>
                    <button onclick="deleteHotspot('${hs.id}')" style="background:rgba(239,68,68,0.15);color:#f87171;border:1px solid rgba(239,68,68,0.3);padding:3px 8px;border-radius:4px;font-size:11px;cursor:pointer;">Delete</button>
                </div>
            </div>
        `;
    });
    list.innerHTML = html;
}

function focusHotspot(id) {
    const hs = _currentHotspots.find(h => h.id === id);
    if (!hs || !_hsModel || !_hsControls || !_hsCamera) return;

    // Convert local point to world
    const worldPoint = _hsModel.localToWorld(new THREE.Vector3(hs.x, hs.y, hs.z));
    _hsControls.target.copy(worldPoint);
    _hsControls.update();
}

function deleteHotspot(id) {
    _currentHotspots = _currentHotspots.filter(h => h.id !== id);
    renderHotspotsOnModel();
    updateHotspotSidebar();
}

function closeHotspotEditor() {
    const ui = document.getElementById('model3d-hotspot-ui');
    if (ui) ui.style.display = 'none';

    if (_hsAnimId) {
        cancelAnimationFrame(_hsAnimId);
        _hsAnimId = null;
    }
    if (_hsResizeObserver) {
        _hsResizeObserver.disconnect();
        _hsResizeObserver = null;
    }
}

function finishHotspotEditor() {
    closeHotspotEditor();

    let targetUrl = (_pendingModelUrl || '').trim();
    if (window.location.protocol === 'https:' && targetUrl.startsWith('http://')) {
        targetUrl = 'https://' + targetUrl.slice(7);
    }
    if (!targetUrl.startsWith('http://') && !targetUrl.startsWith('https://') && !targetUrl.startsWith('/') && !targetUrl.startsWith('blob:') && !targetUrl.startsWith('data:')) {
        targetUrl = '/static/uploads/' + targetUrl;
    }

    let embedSrc = `/static/3d-viewer-embed.html?model=${encodeURIComponent(targetUrl)}`;
    if (_currentHotspots && _currentHotspots.length > 0) {
        embedSrc += `#hotspots=${encodeURIComponent(JSON.stringify(_currentHotspots))}`;
    }

    const captionHtml = _pendingCaption
        ? `<p class="ql-align-center" style="text-align: center; margin: 0 0 10px 0; font-size: 15px; color: #111827; font-weight: 600;">${escapeHtml(_pendingCaption)}</p>`
        : '';

    const iframeHtml = `<div class="ql-3d-embed-wrapper" style="width: 100%; max-width: 800px; margin: 4px auto 18px auto; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); background: #0f0f1a;">
        <iframe src="${embedSrc}" width="100%" height="${_pendingHeight}" frameborder="0" allowfullscreen="true" allow="autoplay; fullscreen; xr-spatial-tracking" style="width: 100%; height: ${_pendingHeight}px; display: block; border: none;"></iframe>
    </div>`;

    const html = `${captionHtml}${iframeHtml}<p><br></p>`;

    if (window.currentQuill) {
        const range = window.currentQuill.getSelection(true) || { index: 0 };
        window.currentQuill.clipboard.dangerouslyPasteHTML(range.index, html);
        window.currentQuill.root.setAttribute('data-custom-html', 'true');

        // Update textarea
        const textarea = document.getElementById('content-editor') || 
                         document.getElementById('content') ||
                         document.getElementById('announcement-content') ||
                         document.getElementById('course-description');
        if (textarea) {
            textarea.value = window.currentQuill.root.innerHTML;
        }
    }

    const modal = document.getElementById('model3d-modal');
    if (modal) modal.style.display = 'none';
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
