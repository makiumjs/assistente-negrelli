import json
import os

with open("public/data/mappe.json", "r", encoding="utf-8") as f:
    mappe_data = json.load(f)

svgs = {}
for i in range(3):
    with open(f"public/data/mappe/piano_{i}.svg", "r", encoding="utf-8") as f:
        svgs[i] = f.read()

json_str = json.dumps(mappe_data, ensure_ascii=False)
svg_0_json = json.dumps(svgs[0], ensure_ascii=False)
svg_1_json = json.dumps(svgs[1], ensure_ascii=False)
svg_2_json = json.dumps(svgs[2], ensure_ascii=False)

html_content = f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Riferimento Visivo & Modifica Aule — ITIS Negrelli</title>
  <style>
    :root {{
      --bg: #0b1120;
      --card-bg: #1e293b;
      --panel-bg: #0f172a;
      --border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --teal: #14b8a6;
      --teal-hover: #0d9488;
      --blue: #3b82f6;
      --purple: #8b5cf6;
      --green: #10b981;
      --amber: #f59e0b;
      --rose: #f43f5e;
      --radius: 10px;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }}
    header {{
      background: #090d16;
      border-bottom: 1px solid var(--border);
      padding: 10px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
      z-index: 50;
    }}
    .header-left {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .logo-badge {{
      background: linear-gradient(135deg, var(--teal), #0284c7);
      color: #fff;
      font-weight: 800;
      font-size: 13px;
      padding: 6px 12px;
      border-radius: 8px;
      letter-spacing: 0.5px;
    }}
    h1 {{ font-size: 16px; font-weight: 700; color: #fff; }}
    .subtitle {{ font-size: 11.5px; color: var(--text-muted); }}

    .header-actions {{
      display: flex;
      gap: 8px;
      align-items: center;
    }}
    .btn {{
      background: #1e293b;
      color: #f8fafc;
      border: 1px solid var(--border);
      padding: 7px 12px;
      border-radius: 8px;
      font-size: 12.5px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
      text-decoration: none;
    }}
    .btn:hover {{ background: #334155; border-color: #64748b; }}
    .btn-teal {{
      background: var(--teal);
      border-color: var(--teal-hover);
      color: #042f2e;
    }}
    .btn-teal:hover {{ background: var(--teal-hover); color: #fff; }}

    /* Menu a tendina per cartelli stampabili */
    .dropdown {{
      position: relative;
      display: inline-block;
    }}
    .dropdown-content {{
      display: none;
      position: absolute;
      right: 0;
      top: 100%;
      margin-top: 4px;
      background: #1e293b;
      min-width: 250px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.6);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 6px 0;
      z-index: 100;
    }}
    .dropdown:hover .dropdown-content {{ display: block; }}
    .dropdown-content a {{
      color: var(--text);
      padding: 8px 14px;
      text-decoration: none;
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      transition: background 0.12s;
    }}
    .dropdown-content a:hover {{
      background: #334155;
      color: var(--teal);
    }}
    .dropdown-content .category-label {{
      padding: 6px 14px 2px;
      font-size: 10px;
      font-weight: 700;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}

    #workspace {{
      display: flex;
      flex: 1;
      height: calc(100vh - 58px);
      overflow: hidden;
    }}

    /* Left Map Viewer */
    #map-viewer {{
      flex: 1;
      display: flex;
      flex-direction: column;
      background: #020617;
      border-right: 1px solid var(--border);
      position: relative;
      overflow: hidden;
    }}
    #floor-nav {{
      background: #0b1120;
      padding: 8px 14px;
      border-bottom: 1px solid var(--border);
      display: flex;
      gap: 6px;
      align-items: center;
      flex-shrink: 0;
    }}
    .tab-btn {{
      background: #1e293b;
      color: var(--text-muted);
      border: 1px solid var(--border);
      padding: 7px 14px;
      border-radius: 8px;
      font-size: 12.5px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s;
    }}
    .tab-btn:hover {{ background: #334155; color: #fff; }}
    .tab-btn.active {{
      background: var(--teal);
      color: #042f2e;
      border-color: var(--teal);
      font-weight: 700;
    }}

    #map-viewport {{
      flex: 1;
      position: relative;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      background: radial-gradient(circle at 50% 50%, #0f172a 0%, #020617 100%);
      cursor: grab;
      user-select: none;
    }}
    #map-viewport:active {{
      cursor: grabbing;
    }}

    #svg-stage {{
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      transform-origin: center center;
      transition: transform 0.05s linear;
    }}
    #svg-stage svg {{
      max-width: 98%;
      max-height: 98%;
      display: block;
      filter: drop-shadow(0 15px 35px rgba(0,0,0,0.4));
      border-radius: 12px;
    }}

    /* SVG Pin Styling */
    .room-pin {{
      cursor: pointer;
      transition: transform 0.15s ease;
    }}
    .room-pin:hover {{
      filter: brightness(1.2);
    }}
    .room-pin.selected {{
      filter: drop-shadow(0 0 10px rgba(56, 189, 248, 0.9));
    }}
    .room-pin.has-mod .pin-bg {{
      stroke: #10b981 !important;
      stroke-width: 2.2 !important;
    }}

    #zoom-controls {{
      position: absolute;
      bottom: 16px;
      right: 16px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      z-index: 30;
    }}
    .zoom-btn {{
      width: 36px;
      height: 36px;
      background: #1e293b;
      color: #fff;
      border: 1px solid var(--border);
      border-radius: 8px;
      font-size: 16px;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 10px rgba(0,0,0,0.4);
      transition: all 0.15s;
    }}
    .zoom-btn:hover {{ background: #334155; border-color: #64748b; }}

    #map-hint {{
      position: absolute;
      bottom: 16px;
      left: 16px;
      background: rgba(15, 23, 42, 0.85);
      backdrop-filter: blur(8px);
      border: 1px solid var(--border);
      color: var(--text-muted);
      font-size: 11px;
      padding: 6px 12px;
      border-radius: 6px;
      pointer-events: none;
    }}

    /* Right Sidebar: Change Editor */
    #sidebar-editor {{
      width: 440px;
      background: #0f172a;
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
      border-left: 1px solid var(--border);
    }}
    .sidebar-header {{
      padding: 14px 16px;
      border-bottom: 1px solid var(--border);
      background: #090d16;
    }}
    .sidebar-header h2 {{ font-size: 14.5px; font-weight: 700; margin-bottom: 3px; color: #fff; }}
    .sidebar-header p {{ font-size: 11.5px; color: var(--text-muted); }}

    .filter-bar {{
      padding: 8px 14px;
      border-bottom: 1px solid var(--border);
      display: flex;
      gap: 8px;
      background: #131d31;
    }}
    .filter-input {{
      flex: 1;
      background: #0f172a;
      border: 1px solid var(--border);
      color: #fff;
      padding: 7px 12px;
      border-radius: 6px;
      font-size: 12px;
      outline: none;
    }}
    .filter-input:focus {{ border-color: var(--teal); }}

    #room-list {{
      flex: 1;
      overflow-y: auto;
      padding: 10px 14px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .room-item {{
      background: #1e293b;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 10px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      transition: all 0.15s;
    }}
    .room-item:hover, .room-item.selected {{
      border-color: #38bdf8;
      background: #1e3a5f;
    }}
    .room-item.has-mod {{
      border-color: #10b981;
      background: rgba(16, 185, 129, 0.12);
    }}
    .room-info {{
      display: flex;
      flex-direction: column;
      min-width: 140px;
      cursor: pointer;
    }}
    .room-code-tag {{
      font-size: 12.5px;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .badge-pill {{
      font-size: 9.5px;
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: 700;
    }}
    .room-desc {{
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 2px;
    }}
    .mod-input-wrap {{
      flex: 1;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .mod-input {{
      width: 100%;
      background: #090d16;
      border: 1px solid var(--border);
      color: #38bdf8;
      font-weight: 600;
      padding: 6px 10px;
      border-radius: 6px;
      font-size: 12px;
      outline: none;
      transition: border 0.15s;
    }}
    .mod-input:focus {{
      border-color: #38bdf8;
      background: #020617;
    }}
    .mod-input::placeholder {{
      color: #64748b;
      font-weight: normal;
    }}

    /* Bottom Summary Bar */
    .summary-footer {{
      padding: 12px 14px;
      background: #090d16;
      border-top: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    .mod-count-badge {{
      font-size: 12px;
      color: var(--teal);
      font-weight: 600;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .action-btn-row {{
      display: flex;
      gap: 8px;
    }}
    .btn-copy {{
      flex: 1;
      background: linear-gradient(135deg, #10b981, #059669);
      color: #fff;
      border: none;
      padding: 9px;
      border-radius: 8px;
      font-weight: 700;
      font-size: 12.5px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: all 0.2s;
    }}
    .btn-copy:hover {{
      background: linear-gradient(135deg, #059669, #047857);
    }}
    .btn-reset {{
      background: #334155;
      color: #cbd5e1;
      border: 1px solid var(--border);
      padding: 9px 12px;
      border-radius: 8px;
      font-size: 12px;
      cursor: pointer;
    }}
    .btn-reset:hover {{ background: #475569; }}

    /* Toast Notification */
    #toast {{
      position: fixed;
      bottom: 24px;
      left: 50%;
      transform: translateX(-50%) translateY(100px);
      background: #10b981;
      color: #022c22;
      font-weight: 700;
      padding: 12px 24px;
      border-radius: 8px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      transition: all 0.3s ease;
      z-index: 100;
      pointer-events: none;
      font-size: 13.5px;
    }}
    #toast.show {{
      transform: translateX(-50%) translateY(0);
    }}

    @media (max-width: 900px) {{
      #workspace {{ flex-direction: column; }}
      #sidebar-editor {{ width: 100%; height: 45vh; border-left: none; border-top: 1px solid var(--border); }}
      #map-viewer {{ height: 55vh; }}
    }}
  </style>
</head>
<body>

<header>
  <div class="header-left">
    <div class="logo-badge">ITIS NEGRELLI</div>
    <div>
      <h1>Riferimento Visivo & Modulo Modifiche Aule</h1>
      <div class="subtitle">Guarda la planimetria, clicca sull'aula o scrivi la nuova classe nel pannello laterale</div>
    </div>
  </div>
  <div class="header-actions">
    <div class="dropdown">
      <button class="btn" type="button">🖼️ Cartelli A3 (Scarica/Visualizza) ▾</button>
      <div class="dropdown-content">
        <div class="category-label">Formato PDF Vettoriale A3</div>
        <a href="./mappe_stampabili/Tabellone_Generale_Ingresso.pdf" target="_blank">📋 Tabellone Ingresso (PDF)</a>
        <a href="./mappe_stampabili/0_Cartello_Piano_Terra.pdf" target="_blank">0️⃣ Piano Terra (PDF)</a>
        <a href="./mappe_stampabili/1_Cartello_Piano_Primo.pdf" target="_blank">1️⃣ 1° Piano (PDF)</a>
        <a href="./mappe_stampabili/2_Cartello_Piano_Secondo.pdf" target="_blank">2️⃣ 2° Piano (PDF)</a>
        <div class="category-label">Formato PNG 300 DPI</div>
        <a href="./mappe_stampabili/Tabellone_Generale_Ingresso.png" target="_blank">🖼️ Tabellone Ingresso (PNG)</a>
        <a href="./mappe_stampabili/0_Cartello_Piano_Terra.png" target="_blank">🖼️ Piano Terra (PNG)</a>
        <a href="./mappe_stampabili/1_Cartello_Piano_Primo.png" target="_blank">🖼️ 1° Piano (PNG)</a>
        <a href="./mappe_stampabili/2_Cartello_Piano_Secondo.png" target="_blank">🖼️ 2° Piano (PNG)</a>
      </div>
    </div>
    <a href="./index.html" class="btn btn-teal">🤖 Torna all'Assistente Web</a>
  </div>
</header>

<div id="workspace">
  <!-- Map Viewer Area -->
  <div id="map-viewer">
    <div id="floor-nav">
      <button class="tab-btn active" type="button" data-floor="0" onclick="switchFloor(0)">Piano Terra (0)</button>
      <button class="tab-btn" type="button" data-floor="1" onclick="switchFloor(1)">1° Piano (1)</button>
      <button class="tab-btn" type="button" data-floor="2" onclick="switchFloor(2)">2° Piano (2)</button>
      <div style="margin-left:auto; font-size:11.5px; color:var(--text-muted);" id="current-floor-desc">
        Aule 014–022, Laboratori Meccanica/Linux, Palestra, Mensa
      </div>
    </div>
    <div id="map-viewport">
      <div id="svg-stage">
        <!-- SVG Map iniettato dinamicamente -->
      </div>
      <div id="map-hint">🖱️ Trascina per spostarti • Rotella per zoomare • Clicca un'aula per modificarla</div>
      <div id="zoom-controls">
        <button class="zoom-btn" onclick="zoom(1.25)" title="Ingrandisci">＋</button>
        <button class="zoom-btn" onclick="zoom(0.8)" title="Rimpicciolisci">－</button>
        <button class="zoom-btn" onclick="resetZoom()" title="Centra mappa">⟲</button>
      </div>
    </div>
  </div>

  <!-- Sidebar: Room Directory & Change Note Editor -->
  <div id="sidebar-editor">
    <div class="sidebar-header">
      <h2>Elenco Aule & Spazi Didattici</h2>
      <p>Digita la nuova classe o uso accanto all'aula corrispondente:</p>
    </div>
    <div class="filter-bar">
      <input type="text" id="search-filter" class="filter-input" placeholder="🔍 Cerca aula (es. 014, 110, 204, chimica)..." oninput="renderRoomList()" />
    </div>

    <div id="room-list">
      <!-- Inserito dinamicamente via JS -->
    </div>

    <div class="summary-footer">
      <div class="mod-count-badge">
        <span id="mod-counter-text">0 modifiche registrate</span>
        <span style="font-size:11px; color:#64748b;">Pronto da incollare in chat</span>
      </div>
      <div class="action-btn-row">
        <button class="btn-copy" onclick="copyModificationsToClipboard()">
          📋 Copia Modifiche per l'Assistente
        </button>
        <button class="btn-reset" onclick="resetAllModifications()">Azzera</button>
      </div>
    </div>
  </div>
</div>

<div id="toast">Copiato negli appunti! Incollalo nella chat.</div>

<script>
  // Dataset incorporato direttamente per funzionamento garantito sia via file:// sia via web server
  const EMBEDDED_MAP_DATA = {json_str};

  const EMBEDDED_SVGS = {{
    0: {svg_0_json},
    1: {svg_1_json},
    2: {svg_2_json}
  }};

  let mapData = EMBEDDED_MAP_DATA;
  let currentFloor = 0;
  let currentZoom = 1.0;
  let panX = 0;
  let panY = 0;
  let selectedCode = null;
  const userMods = JSON.parse(localStorage.getItem('negrelli_aula_mods') || '{{}}');

  const FLOOR_DESCS = {{
    0: "Aule 014–022, Laboratori Meccanica/Linux, Palestra, Mensa, Infermeria",
    1: "Aule 110–134, Grandi Laboratori (CAD, Chimica, Fisica, Disegno), Segreteria",
    2: "Aule 201–224, Laboratori Informatica, Elettronica, Sistemi e Lingue"
  }};

  function updateTransform() {{
    const stage = document.getElementById('svg-stage');
    stage.style.transform = `translate(${{panX}}px, ${{panY}}px) scale(${{currentZoom}})`;
  }}

  function zoom(factor) {{
    currentZoom = Math.max(0.6, Math.min(3.5, currentZoom * factor));
    updateTransform();
  }}

  function resetZoom() {{
    currentZoom = 1.0;
    panX = 0;
    panY = 0;
    updateTransform();
  }}

  function switchFloor(floorNum) {{
    currentFloor = floorNum;
    document.querySelectorAll('.tab-btn').forEach(btn => {{
      btn.classList.toggle('active', parseInt(btn.dataset.floor) === floorNum);
    }});
    document.getElementById('current-floor-desc').textContent = FLOOR_DESCS[floorNum] || "";
    resetZoom();

    const floorObj = mapData.floors.find(f => f.floor === floorNum);
    if (!floorObj) return;

    // Carica SVG incorporato
    const stage = document.getElementById('svg-stage');
    stage.innerHTML = EMBEDDED_SVGS[floorNum] || "";

    addSvgPins(floorObj);
    renderRoomList();
  }}

  function addSvgPins(floorObj) {{
    const stage = document.getElementById('svg-stage');
    const svgEl = stage.querySelector('svg');
    if (!svgEl) return;

    const ns = "http://www.w3.org/2000/svg";
    const pinsLayer = document.createElementNS(ns, "g");
    pinsLayer.setAttribute("id", "interactive-pins");

    floorObj.rooms.forEach(r => {{
      if (r.cat === 'vuoto') return;
      const mod = userMods[r.code];
      const isSelected = selectedCode === r.code;

      const g = document.createElementNS(ns, "g");
      g.setAttribute("class", `room-pin cat-${{r.cat}}${{isSelected ? " selected" : ""}}${{mod ? " has-mod" : ""}}`);
      g.setAttribute("id", `pin-${{r.code}}`);
      g.setAttribute("transform", `translate(${{r.svgX}}, ${{r.svgY}})`);

      const scalePin = floorObj.floor === 2 ? 0.8 : 1.0;
      const baseLabel = mod ? `${{r.code}} → ${{mod}}` : r.code;
      const fontSize = 11.5 * scalePin;
      const boxW = Math.max(48 * scalePin, baseLabel.length * 7.5 * scalePin + 14 * scalePin);
      const boxH = 22 * scalePin;

      // Sfondo pin
      const rect = document.createElementNS(ns, "rect");
      rect.setAttribute("class", "pin-bg");
      rect.setAttribute("x", String(-boxW / 2));
      rect.setAttribute("y", String(-boxH / 2));
      rect.setAttribute("width", String(boxW));
      rect.setAttribute("height", String(boxH));
      rect.setAttribute("rx", String(5 * scalePin));
      rect.setAttribute("fill", isSelected ? "#0284c7" : (mod ? "#065f46" : r.color));
      rect.setAttribute("stroke", isSelected ? "#38bdf8" : (mod ? "#10b981" : r.borderColor));
      rect.setAttribute("stroke-width", isSelected ? "2.2" : (mod ? "2" : "1.2"));
      g.appendChild(rect);

      // Testo pin
      const text = document.createElementNS(ns, "text");
      text.setAttribute("x", "0");
      text.setAttribute("y", "1");
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("dominant-baseline", "middle");
      text.setAttribute("fill", "#ffffff");
      text.setAttribute("font-size", String(fontSize));
      text.setAttribute("font-weight", "800");
      text.setAttribute("font-family", "system-ui, -apple-system, sans-serif");
      text.textContent = baseLabel;
      g.appendChild(text);

      g.onclick = (e) => {{
        e.stopPropagation();
        selectRoom(r.code);
      }};

      pinsLayer.appendChild(g);
    }});

    svgEl.appendChild(pinsLayer);
  }}

  function renderRoomList() {{
    const listEl = document.getElementById('room-list');
    const filter = document.getElementById('search-filter').value.toLowerCase().trim();
    if (!mapData) return;

    const floorObj = mapData.floors.find(f => f.floor === currentFloor);
    if (!floorObj) return;

    listEl.innerHTML = '';

    const rooms = floorObj.rooms.filter(r => {{
      if (r.cat === 'vuoto') return false;
      if (!filter) return true;
      return r.code.toLowerCase().includes(filter) ||
             r.name.toLowerCase().includes(filter) ||
             (r.sub && r.sub.toLowerCase().includes(filter));
    }});

    rooms.forEach(r => {{
      const item = document.createElement('div');
      item.className = 'room-item' + (selectedCode === r.code ? ' selected' : '');
      item.id = `room-item-${{r.code}}`;
      const modVal = userMods[r.code] || '';
      if (modVal) item.classList.add('has-mod');

      const catBg = r.color || '#3b82f6';

      item.innerHTML = `
        <div class="room-info" onclick="selectRoom('${{r.code}}')">
          <div class="room-code-tag">
            <span class="badge-pill" style="background:${{catBg}}; color:#fff;">${{r.code}}</span>
            <span>${{r.name}}</span>
          </div>
          <div class="room-desc">${{r.sub || r.catLabel}}</div>
        </div>
        <div class="mod-input-wrap">
          <input type="text" 
                 class="mod-input" 
                 id="input-${{r.code}}" 
                 placeholder="Nuova classe/uso..." 
                 value="${{modVal}}" 
                 onfocus="selectRoom('${{r.code}}')"
                 oninput="onModChange('${{r.code}}', this.value)" />
        </div>
      `;
      listEl.appendChild(item);
    }});

    updateModCount();
  }}

  function selectRoom(code) {{
    selectedCode = code;
    document.querySelectorAll('.room-item').forEach(el => el.classList.remove('selected'));
    document.querySelectorAll('.room-pin').forEach(el => el.classList.remove('selected'));

    const itemEl = document.getElementById(`room-item-${{code}}`);
    if (itemEl) {{
      itemEl.classList.add('selected');
      itemEl.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
      const inp = itemEl.querySelector('.mod-input');
      if (inp && document.activeElement !== inp) inp.focus();
    }}

    const pinEl = document.getElementById(`pin-${{code}}`);
    if (pinEl) pinEl.classList.add('selected');
  }}

  function onModChange(code, val) {{
    val = val.trim();
    if (val) {{
      userMods[code] = val;
    }} else {{
      delete userMods[code];
    }}
    localStorage.setItem('negrelli_aula_mods', JSON.stringify(userMods));

    const itemEl = document.getElementById(`room-item-${{code}}`);
    if (itemEl) itemEl.classList.toggle('has-mod', !!val);

    // Aggiorna pin SVG
    const floorObj = mapData.floors.find(f => f.floor === currentFloor);
    if (floorObj) {{
      const pinEl = document.getElementById(`pin-${{code}}`);
      if (pinEl) {{
        const textEl = pinEl.querySelector('text');
        const rectEl = pinEl.querySelector('rect');
        const baseLabel = val ? `${{code}} → ${{val}}` : code;
        if (textEl) textEl.textContent = baseLabel;
        if (rectEl) {{
          const scalePin = floorObj.floor === 2 ? 0.8 : 1.0;
          const boxW = Math.max(48 * scalePin, baseLabel.length * 7.5 * scalePin + 14 * scalePin);
          rectEl.setAttribute("width", String(boxW));
          rectEl.setAttribute("x", String(-boxW / 2));
          if (val) {{
            rectEl.setAttribute("fill", "#065f46");
            rectEl.setAttribute("stroke", "#10b981");
            rectEl.setAttribute("stroke-width", "2");
          }} else {{
            const r = floorObj.rooms.find(x => x.code === code);
            rectEl.setAttribute("fill", r ? r.color : "#3b82f6");
            rectEl.setAttribute("stroke", r ? r.borderColor : "#1e40af");
            rectEl.setAttribute("stroke-width", "1.2");
          }}
        }}
      }}
    }}

    updateModCount();
  }}

  function updateModCount() {{
    const count = Object.keys(userMods).length;
    const counterEl = document.getElementById('mod-counter-text');
    counterEl.textContent = count === 1 ? '1 modifica registrata' : `${{count}} modifiche registrate`;
  }}

  function copyModificationsToClipboard() {{
    const entries = Object.entries(userMods);
    if (entries.length === 0) {{
      showToast("Nessuna modifica inserita! Scrivi le nuove classi nei campi.");
      return;
    }}

    let text = "Ecco le modifiche delle aule da applicare:\\n";
    entries.forEach(([code, newDest]) => {{
      text += `- Aula ${{code}} -> ${{newDest}}\\n`;
    }});

    navigator.clipboard.writeText(text).then(() => {{
      showToast("📋 Modifiche copiate! Incollale nella chat.");
    }}).catch(() => {{
      prompt("Copia manualmente questo testo per la chat:", text);
    }});
  }}

  function resetAllModifications() {{
    if (confirm("Vuoi azzerare tutte le modifiche inserite?")) {{
      Object.keys(userMods).forEach(k => delete userMods[k]);
      localStorage.removeItem('negrelli_aula_mods');
      switchFloor(currentFloor);
    }}
  }}

  function showToast(msg) {{
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2500);
  }}

  // Pan con mouse drag
  const viewport = document.getElementById('map-viewport');
  let isDragging = false;
  let startX = 0, startY = 0;

  viewport.addEventListener('mousedown', (e) => {{
    if (e.target.closest('.room-pin') || e.target.closest('#zoom-controls')) return;
    isDragging = true;
    startX = e.clientX - panX;
    startY = e.clientY - panY;
  }});

  window.addEventListener('mousemove', (e) => {{
    if (!isDragging) return;
    panX = e.clientX - startX;
    panY = e.clientY - startY;
    updateTransform();
  }});

  window.addEventListener('mouseup', () => {{
    isDragging = false;
  }});

  // Zoom con rotella
  viewport.addEventListener('wheel', (e) => {{
    e.preventDefault();
    const delta = e.deltaY < 0 ? 1.15 : 0.87;
    zoom(delta);
  }}, {{ passive: false }});

  // Avvio immediato
  switchFloor(0);
</script>

</body>
</html>
"""

with open("riferimento_visivo.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("✔ riferimento_visivo.html rigenerato con successo (incorporato, 100% self-contained).")
