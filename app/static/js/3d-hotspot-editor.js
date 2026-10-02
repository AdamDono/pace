// 3D Hotspot Editor Logic
let _hsScene, _hsCamera, _hsRenderer, _hsControls, _hsModel, _hsAnimId;
let _currentHotspots = [];
let _hsRaycaster = null;
let _hsMouse = null;
let _pendingModelUrl = '';
let _pendingCaption = '';
let _pendingHeight = '';

function openHotspotEditor(url, caption, height) {
    _pendingModelUrl = url;
    _pendingCaption = caption;
    _pendingHeight = height;
    _currentHotspots = [];

    // Create UI if not exists
    let ui = document.getElementById('model3d-hotspot-ui');
    if (!ui) {
        ui = document.createElement('div');
        ui.id = 'model3d-hotspot-ui';
        ui.style.cssText = 'position:fixed;inset:0;background:#0f0f1a;z-index:99999;display:flex;flex-direction:column;font-family:system-ui,sans-serif;';
        ui.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;padding:16px 24px;background:#1a1a2e;color:white;border-bottom:1px solid #2d2d44;">
                <div>
                    <h2 style="margin:0;font-size:18px;">📍 Add Hotspots to 3D Model</h2>
                    <p style="margin:4px 0 0;font-size:13px;color:#a5b4fc;">Click anywhere on the model to place a hotspot. Click "Insert to Lesson" when done.</p>
                </div>
                <div style="display:flex;gap:12px;">
                    <button onclick="closeHotspotEditor()" style="padding:8px 16px;background:transparent;color:white;border:1px solid #4f4f7a;border-radius:6px;cursor:pointer;">Cancel</button>
                    <button onclick="finishHotspotEditor()" style="padding:8px 16px;background:#4f46e5;color:white;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">Insert to Lesson</button>
                </div>
            </div>
            <div style="flex:1;position:relative;display:flex;">
                <div style="flex:1;position:relative;" id="hs-canvas-container">
                    <canvas id="hs-canvas" style="width:100%;height:100%;display:block;"></canvas>
                    <div id="hs-loading" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:white;background:#0f0f1a;">Loading Model...</div>
                </div>
                <div style="width:300px;background:#1a1a2e;border-left:1px solid #2d2d44;padding:16px;color:white;overflow-y:auto;" id="hs-list">
                    <h3 style="margin-top:0;font-size:14px;text-transform:uppercase;color:#818cf8;">Current Hotspots</h3>
                    <div id="hs-items" style="display:flex;flex-direction:column;gap:12px;margin-top:16px;"></div>
                </div>
            </div>
        `;
        document.body.appendChild(ui);
    }
    ui.style.display = 'flex';
    document.getElementById('hs-loading').style.display = 'flex';
    document.getElementById('hs-items').innerHTML = '<p style="color:#6b7280;font-size:13px;">No hotspots yet.</p>';

    // Load Three.js
    function loadS(src, cb) {
        if (document.querySelector(`script[src="${src}"]`)) return cb();
        let s = document.createElement('script');
        s.src = src; s.onload = cb; document.head.appendChild(s);
    }
    loadS('https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js', () => {
        loadS('https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js', () => {
            loadS('https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js', () => {
                loadS('https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/OBJLoader.js', () => {
                    initHsEditor();
                });
            });
        });
    });
}

function initHsEditor() {
    const canvas = document.getElementById('hs-canvas');
    const container = document.getElementById('hs-canvas-container');
    
    _hsScene = new THREE.Scene();
    _hsScene.background = new THREE.Color(0x0f0f1a);
    
    _hsCamera = new THREE.PerspectiveCamera(60, container.clientWidth / container.clientHeight, 0.1, 1000);
    _hsCamera.position.set(0, 1.5, 4);
    
    _hsRenderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
    _hsRenderer.setSize(container.clientWidth, container.clientHeight);
    
    _hsControls = new THREE.OrbitControls(_hsCamera, _hsRenderer.domElement);
    _hsControls.enableDamping = true;
    
    _hsScene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const dl = new THREE.DirectionalLight(0xffffff, 0.9);
    dl.position.set(5, 10, 7);
    _hsScene.add(dl);
    
    _hsRaycaster = new THREE.Raycaster();
    _hsMouse = new THREE.Vector2();
    
    // Load Model
    const ext = _pendingModelUrl.split('?')[0].split('.').pop().toLowerCase();
    const afterLoad = (obj) => {
        _hsModel = obj;
        const box = new THREE.Box3().setFromObject(obj);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        const scale = 3 / maxDim;
        obj.scale.setScalar(scale);
        obj.position.sub(center.multiplyScalar(scale));
        _hsScene.add(obj);
        document.getElementById('hs-loading').style.display = 'none';
    };
    
    if (ext === 'obj') {
        new THREE.OBJLoader().load(_pendingModelUrl, afterLoad);
    } else {
        new THREE.GLTFLoader().load(_pendingModelUrl, g => afterLoad(g.scene), undefined, () => {
            new THREE.OBJLoader().load(_pendingModelUrl, afterLoad); // fallback
        });
    }
    
    const animate = () => {
        _hsAnimId = requestAnimationFrame(animate);
        _hsControls.update();
        _hsRenderer.render(_hsScene, _hsCamera);
    };
    animate();
    
    // Click to add hotspot
    canvas.onclick = (e) => {
        const rect = canvas.getBoundingClientRect();
        _hsMouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        _hsMouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
        _hsRaycaster.setFromCamera(_hsMouse, _hsCamera);
        
        if (!_hsModel) return;
        const intersects = _hsRaycaster.intersectObject(_hsModel, true);
        if (intersects.length > 0) {
            const point = intersects[0].point;
            // Convert to model's local coordinate space
            const localPoint = _hsModel.worldToLocal(point.clone());
            
            const title = prompt("Enter Hotspot Title:");
            if (!title) return;
            const desc = prompt("Enter Description:");
            
            const hsId = 'hs_' + Date.now();
            _currentHotspots.push({
                id: hsId,
                title: title,
                description: desc || '',
                x: localPoint.x,
                y: localPoint.y,
                z: localPoint.z
            });
            
            renderHotspots();
        }
    };
    
    window.addEventListener('resize', () => {
        if(document.getElementById('model3d-hotspot-ui').style.display !== 'none') {
            _hsCamera.aspect = container.clientWidth / container.clientHeight;
            _hsCamera.updateProjectionMatrix();
            _hsRenderer.setSize(container.clientWidth, container.clientHeight);
        }
    });
}

function renderHotspots() {
    // Remove old meshes
    for(let i = _hsModel.children.length - 1; i >= 0; i--) {
        if(_hsModel.children[i].userData.isHotspot) {
            _hsModel.remove(_hsModel.children[i]);
        }
    }
    
    const list = document.getElementById('hs-items');
    list.innerHTML = '';
    
    const geo = new THREE.SphereGeometry(0.05, 16, 16);
    const mat = new THREE.MeshBasicMaterial({ color: 0xff3b30 });
    
    _currentHotspots.forEach(hs => {
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.set(hs.x, hs.y, hs.z);
        // Important: un-scale the sphere so it doesn't get squished by model's scale
        mesh.scale.setScalar(1 / _hsModel.scale.x);
        mesh.userData.isHotspot = true;
        _hsModel.add(mesh);
        
        list.innerHTML += `
            <div style="background:#2d2d44;padding:12px;border-radius:6px;">
                <h4 style="margin:0 0 4px;font-size:14px;">${hs.title}</h4>
                <p style="margin:0;font-size:12px;color:#9ca3af;">${hs.description}</p>
                <button onclick="deleteHotspot('${hs.id}')" style="margin-top:8px;background:#ef4444;color:white;border:none;padding:4px 8px;border-radius:4px;font-size:11px;cursor:pointer;">Delete</button>
            </div>
        `;
    });
}

function deleteHotspot(id) {
    _currentHotspots = _currentHotspots.filter(h => h.id !== id);
    renderHotspots();
}

function closeHotspotEditor() {
    document.getElementById('model3d-hotspot-ui').style.display = 'none';
    if(_hsAnimId) cancelAnimationFrame(_hsAnimId);
}

function finishHotspotEditor() {
    closeHotspotEditor();
    const vid = 'v3d_' + Math.random().toString(36).slice(2, 7);
    const hsAttr = _currentHotspots.length ? ` data-hotspots='${JSON.stringify(_currentHotspots).replace(/'/g, "&apos;")}'` : '';
    
    const captionHtml = _pendingCaption
        ? `<p style="text-align:center;font-size:13px;color:#6b7280;margin:6px 0 0;font-style:italic;">${_pendingCaption}</p>`
        : '';
        
    const html = `<div class="ql-3d-viewer-block" data-ql-3d="1" data-src="${_pendingModelUrl}" data-height="${_pendingHeight}" data-viewer-id="${vid}"${hsAttr} contenteditable="false"
        style="margin:20px 0;border-radius:12px;overflow:hidden;border:2px solid #e0e7ff;background:#0f0f1a;">
        <div style="background:linear-gradient(135deg,#0f0f1a,#1a1a3e);min-height:${_pendingHeight}px;display:flex;flex-direction:column;align-items:center;justify-content:center;position:relative;">
            <div style="text-align:center;color:#a5b4fc;">
                <div style="font-size:48px;margin-bottom:12px;">🧊</div>
                <p style="font-size:14px;font-weight:600;margin:0;">3D Model: ${_pendingCaption || _pendingModelUrl.split('/').pop()}</p>
                <p style="font-size:12px;opacity:0.6;margin:4px 0 0;">Interactive viewer will appear for students</p>
                ${_currentHotspots.length ? `<p style="font-size:11px;color:#34d399;margin-top:4px;">📍 ${_currentHotspots.length} hotspots added</p>` : ''}
            </div>
            <div style="position:absolute;top:8px;right:8px;background:rgba(99,102,241,0.8);color:white;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600;">🧊 3D</div>
        </div>
        ${captionHtml}
    </div><p><br></p>`;
    
    if (window.currentQuill) {
        const range = window.currentQuill.getSelection(true) || {index: 0};
        window.currentQuill.clipboard.dangerouslyPasteHTML(range.index, html);
        window.currentQuill.root.setAttribute('data-custom-html', 'true');
        
        // Update textarea
        const textarea = document.getElementById('content-editor') || document.getElementById('announcement-content');
        if (textarea) {
            textarea.value = window.currentQuill.root.innerHTML;
        }
    }
    
    document.getElementById('model3d-modal').style.display = 'none';
}
