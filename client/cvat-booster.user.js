// ==UserScript==
// @name         CVAT Performance Booster & Solo Focus Mode
// @namespace    https://github.com/cvat-ai/cvat
// @version      1.0.0
// @description  Cảnh báo quá tải Canvas, Slider cấu hình ngưỡng, và Chế độ Solo Focus Mode giúp máy cá nhân luôn mượt 60 FPS trên CVAT
// @author       LocateAnything CVAT Team
// @match        *://*/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(function () {
    "use strict";

    // -------------------------------------------------------------------------
    // 1. Cấu hình & Trạng thái lưu trữ (State & Configuration)
    // -------------------------------------------------------------------------
    const STORAGE_KEY_THRESHOLD = "cvat_booster_threshold";
    const STORAGE_KEY_MINIMIZED = "cvat_booster_minimized";

    const state = {
        threshold: parseInt(localStorage.getItem(STORAGE_KEY_THRESHOLD) || "50", 10),
        minimized: localStorage.getItem(STORAGE_KEY_MINIMIZED) === "true",
        soloActive: false,
        activeSoloLabel: null,
        detectedLabels: new Map(), // name -> { name, color, count, type }
        objectCount: 0,
        fps: 60,
        frameCount: 0,
        lastFpsUpdate: performance.now(),
        isCvatWorkspace: false,
    };

    // -------------------------------------------------------------------------
    // 2. CSS Styles (Glassmorphism & High-Performance Canvas Injections)
    // -------------------------------------------------------------------------
    const BASE_STYLES = `
        /* Khung điều khiển nổi Glassmorphism */
        #cvat-booster-widget {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 999999;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #ffffff;
            user-select: none;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.45);
            transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .cvat-booster-panel {
            background: rgba(22, 27, 34, 0.88);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 12px;
            padding: 14px 16px;
            min-width: 290px;
            max-width: 360px;
        }

        .cvat-booster-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .cvat-booster-title {
            font-size: 13px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 6px;
            color: #58a6ff;
            letter-spacing: 0.3px;
        }

        .cvat-booster-controls {
            display: flex;
            gap: 6px;
        }

        .cvat-booster-btn-icon {
            background: rgba(255, 255, 255, 0.1);
            border: none;
            color: #c9d1d9;
            width: 24px;
            height: 24px;
            border-radius: 6px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            transition: background 0.15s;
        }
        .cvat-booster-btn-icon:hover {
            background: rgba(255, 255, 255, 0.25);
            color: #ffffff;
        }

        /* Thống kê Metrics */
        .cvat-booster-stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-bottom: 12px;
        }

        .cvat-booster-stat-badge {
            background: rgba(0, 0, 0, 0.3);
            border-radius: 8px;
            padding: 6px 10px;
            display: flex;
            flex-direction: column;
        }
        .cvat-booster-stat-label {
            font-size: 10px;
            color: #8b949e;
            text-transform: uppercase;
        }
        .cvat-booster-stat-val {
            font-size: 15px;
            font-weight: 700;
            margin-top: 2px;
        }
        .stat-fps-good { color: #3fb950; }
        .stat-fps-warn { color: #d29922; }
        .stat-fps-bad  { color: #f85149; }

        /* Banner Cảnh báo quá tải */
        .cvat-booster-alert {
            background: rgba(218, 54, 51, 0.2);
            border: 1px solid rgba(248, 81, 73, 0.5);
            border-radius: 8px;
            padding: 8px 10px;
            font-size: 11px;
            color: #ff7b72;
            margin-bottom: 12px;
            display: none;
            animation: pulse-border 2s infinite;
        }
        @keyframes pulse-border {
            0% { border-color: rgba(248, 81, 73, 0.4); }
            50% { border-color: rgba(248, 81, 73, 1); }
            100% { border-color: rgba(248, 81, 73, 0.4); }
        }

        /* Danh sách Label Solo */
        .cvat-booster-section-title {
            font-size: 11px;
            font-weight: 600;
            color: #8b949e;
            margin-bottom: 6px;
            display: flex;
            justify-content: space-between;
        }
        .cvat-booster-labels-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            max-height: 140px;
            overflow-y: auto;
            margin-bottom: 12px;
            padding-right: 4px;
        }
        .cvat-booster-labels-grid::-webkit-scrollbar {
            width: 4px;
        }
        .cvat-booster-labels-grid::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 2px;
        }

        .cvat-booster-label-chip {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 11px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.15s;
        }
        .cvat-booster-label-chip:hover {
            background: rgba(255, 255, 255, 0.18);
        }
        .cvat-booster-label-chip.active {
            border-color: #58a6ff;
            background: rgba(88, 166, 255, 0.25);
            box-shadow: 0 0 8px rgba(88, 166, 255, 0.4);
            font-weight: 600;
        }
        .cvat-booster-color-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }

        /* Slider Threshold */
        .cvat-booster-slider-wrap {
            background: rgba(0, 0, 0, 0.25);
            border-radius: 8px;
            padding: 8px 10px;
            margin-bottom: 10px;
        }
        .cvat-booster-slider-header {
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: #c9d1d9;
            margin-bottom: 6px;
        }
        .cvat-booster-slider {
            width: 100%;
            height: 4px;
            border-radius: 2px;
            background: #30363d;
            outline: none;
            -webkit-appearance: none;
            cursor: pointer;
        }
        .cvat-booster-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 14px;
            height: 14px;
            border-radius: 50%;
            background: #58a6ff;
            cursor: pointer;
            box-shadow: 0 0 4px rgba(0, 0, 0, 0.5);
        }

        /* Nút Actions */
        .cvat-booster-actions {
            display: flex;
            gap: 8px;
        }
        .cvat-booster-btn {
            flex: 1;
            padding: 6px 10px;
            border-radius: 6px;
            border: none;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 4px;
            transition: all 0.15s;
        }
        .cvat-booster-btn-primary {
            background: #238636;
            color: #ffffff;
        }
        .cvat-booster-btn-primary:hover {
            background: #2ea043;
        }
        .cvat-booster-btn-primary.solo-on {
            background: #da3633;
        }
        .cvat-booster-btn-primary.solo-on:hover {
            background: #f85149;
        }
        .cvat-booster-btn-secondary {
            background: rgba(255, 255, 255, 0.1);
            color: #c9d1d9;
        }
        .cvat-booster-btn-secondary:hover {
            background: rgba(255, 255, 255, 0.2);
            color: #ffffff;
        }

        /* Trạng thái thu gọn (Collapsed Badge) */
        .cvat-booster-mini-badge {
            background: rgba(22, 27, 34, 0.9);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 20px;
            padding: 6px 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            font-weight: 600;
        }
        .cvat-booster-mini-badge:hover {
            border-color: #58a6ff;
            box-shadow: 0 0 12px rgba(88, 166, 255, 0.3);
        }

        /* Ẩn các shape khi bật Solo Focus Mode để triệt tiêu tải GPU Canvas */
        .cvat-solo-hidden-shape {
            display: none !important;
            visibility: hidden !important;
            pointer-events: none !important;
        }
    `;

    // -------------------------------------------------------------------------
    // 3. Khởi tạo Giao diện Widget (DOM Creation)
    // -------------------------------------------------------------------------
    let widgetEl = null;
    let soloStyleEl = null;

    function injectStyles() {
        const style = document.createElement("style");
        style.id = "cvat-booster-base-styles";
        style.textContent = BASE_STYLES;
        document.head.appendChild(style);

        soloStyleEl = document.createElement("style");
        soloStyleEl.id = "cvat-booster-solo-active-style";
        document.head.appendChild(soloStyleEl);
    }

    function createWidget() {
        if (document.getElementById("cvat-booster-widget")) return;

        widgetEl = document.createElement("div");
        widgetEl.id = "cvat-booster-widget";
        document.body.appendChild(widgetEl);
        renderWidget();
    }

    function renderWidget() {
        if (!widgetEl) return;

        if (state.minimized) {
            const fpsClass = state.fps >= 45 ? "stat-fps-good" : (state.fps >= 25 ? "stat-fps-warn" : "stat-fps-bad");
            const alertDot = (state.objectCount > state.threshold && !state.soloActive) ? "🔴 " : "";
            widgetEl.innerHTML = `
                <div class="cvat-booster-mini-badge" id="btn-maximize-booster" title="Bấm để mở rộng bảng điều khiển CVAT Booster">
                    <span>⚡ ${alertDot}${state.fps} FPS</span>
                    <span>|</span>
                    <span>📦 ${state.objectCount}</span>
                    ${state.soloActive ? `<span style="color:#58a6ff">🎯 Solo: ${state.activeSoloLabel}</span>` : ""}
                </div>
            `;
            document.getElementById("btn-maximize-booster")?.addEventListener("click", () => {
                state.minimized = false;
                localStorage.setItem(STORAGE_KEY_MINIMIZED, "false");
                renderWidget();
            });
            return;
        }

        const isOverload = state.objectCount > state.threshold;
        const fpsClass = state.fps >= 45 ? "stat-fps-good" : (state.fps >= 25 ? "stat-fps-warn" : "stat-fps-bad");

        widgetEl.innerHTML = `
            <div class="cvat-booster-panel">
                <div class="cvat-booster-header">
                    <div class="cvat-booster-title">
                        <span>⚡ CVAT Booster</span>
                        <span style="font-size:10px; color:#8b949e; font-weight:normal;">v1.0</span>
                    </div>
                    <div class="cvat-booster-controls">
                        <button class="cvat-booster-btn-icon" id="btn-minimize-booster" title="Thu gọn">_</button>
                    </div>
                </div>

                <div class="cvat-booster-stats">
                    <div class="cvat-booster-stat-badge">
                        <span class="cvat-booster-stat-label">Hiệu năng</span>
                        <span class="cvat-booster-stat-val ${fpsClass}">${state.fps} FPS</span>
                    </div>
                    <div class="cvat-booster-stat-badge">
                        <span class="cvat-booster-stat-label">Đối tượng Canvas</span>
                        <span class="cvat-booster-stat-val" style="color:${isOverload ? '#f85149' : '#ffffff'}">${state.objectCount}</span>
                    </div>
                </div>

                <div class="cvat-booster-alert" id="booster-alert-box" style="display:${isOverload && !state.soloActive ? 'block' : 'none'}">
                    ⚠️ <b>Cảnh báo quá tải!</b> Canvas có <b>${state.objectCount}</b> đối tượng (vượt ngưỡng ${state.threshold}). Trình duyệt có thể bị lag. Hãy bấm chọn 1 nhãn bên dưới để bật <b>Solo Mode</b>.
                </div>

                <div class="cvat-booster-slider-wrap">
                    <div class="cvat-booster-slider-header">
                        <span>Ngưỡng cảnh báo:</span>
                        <span id="threshold-val-display" style="font-weight:700; color:#58a6ff;">${state.threshold} đối tượng</span>
                    </div>
                    <input type="range" class="cvat-booster-slider" id="threshold-slider" min="20" max="300" step="5" value="${state.threshold}">
                </div>

                <div class="cvat-booster-section-title">
                    <span>CHỌN NHÃN ĐANG LÀM (SOLO FOCUS)</span>
                    ${state.soloActive ? `<span style="color:#58a6ff; font-weight:bold;">ĐANG LỌC</span>` : ""}
                </div>

                <div class="cvat-booster-labels-grid" id="labels-container">
                    ${renderLabelChips()}
                </div>

                <div class="cvat-booster-actions">
                    <button class="cvat-booster-btn cvat-booster-btn-primary ${state.soloActive ? 'solo-on' : ''}" id="btn-toggle-solo">
                        ${state.soloActive ? "✕ Hủy Solo (Hiện hết)" : "🎯 Bật Solo (Shift+F)"}
                    </button>
                </div>
            </div>
        `;

        // Gắn sự kiện UI
        document.getElementById("btn-minimize-booster")?.addEventListener("click", () => {
            state.minimized = true;
            localStorage.setItem(STORAGE_KEY_MINIMIZED, "true");
            renderWidget();
        });

        const slider = document.getElementById("threshold-slider");
        const sliderDisplay = document.getElementById("threshold-val-display");
        slider?.addEventListener("input", (e) => {
            const val = parseInt(e.target.value, 10);
            state.threshold = val;
            sliderDisplay.textContent = `${val} đối tượng`;
            localStorage.setItem(STORAGE_KEY_THRESHOLD, val.toString());
            checkOverloadState();
        });

        document.getElementById("btn-toggle-solo")?.addEventListener("click", () => {
            if (state.soloActive) {
                disableSoloMode();
            } else {
                // Tự chọn nhãn đầu tiên nếu chưa chọn
                const firstLabel = Array.from(state.detectedLabels.keys())[0];
                if (firstLabel) {
                    enableSoloMode(firstLabel);
                } else {
                    alert("Chưa phát hiện nhãn nào trên màn hình để Solo.");
                }
            }
        });

        // Gắn sự kiện click nhãn chip
        widgetEl.querySelectorAll(".cvat-booster-label-chip").forEach((chip) => {
            chip.addEventListener("click", () => {
                const labelName = chip.getAttribute("data-label");
                if (state.soloActive && state.activeSoloLabel === labelName) {
                    disableSoloMode();
                } else {
                    enableSoloMode(labelName);
                }
            });
        });
    }

    function renderLabelChips() {
        if (state.detectedLabels.size === 0) {
            return `<div style="font-size:11px; color:#8b949e; padding:6px 0;">Đang quét nhãn trên Canvas...</div>`;
        }

        let html = "";
        let index = 1;
        state.detectedLabels.forEach((info, name) => {
            const isSelected = state.soloActive && state.activeSoloLabel === name;
            const hotkeyHint = index <= 9 ? `<span style="opacity:0.6; font-size:9px;">Alt+${index}</span>` : "";
            html += `
                <div class="cvat-booster-label-chip ${isSelected ? 'active' : ''}" data-label="${name}" title="Bấm để cô lập duy nhất nhãn '${name}'">
                    <span class="cvat-booster-color-dot" style="background:${info.color || '#58a6ff'};"></span>
                    <span>${name}</span>
                    <span style="font-size:10px; opacity:0.75;">(${info.count})</span>
                    ${hotkeyHint}
                </div>
            `;
            index++;
        });
        return html;
    }

    // -------------------------------------------------------------------------
    // 4. Cơ chế Quét & Nhận diện Nhãn Đa Hình Học (DOM Scanner)
    // -------------------------------------------------------------------------
    function scanCvatObjects() {
        // Kiểm tra xem có đang ở workspace gán nhãn CVAT không
        const canvas = document.querySelector("#cvat_canvas_wrapper, #cvat_canvas_content, .cvat-canvas-container");
        if (!canvas) {
            state.isCvatWorkspace = false;
            return;
        }
        state.isCvatWorkspace = true;

        // 1. Quét số lượng SVG shapes trên Canvas (hỗ trợ rect, polygon, polyline, cuboids, skeletons)
        const canvasShapes = document.querySelectorAll(
            ".cvat_canvas_shape, polygon.cvat_canvas_shape, rect.cvat_canvas_shape, polyline.cvat_canvas_shape, g.cvat_canvas_shape"
        );
        state.objectCount = canvasShapes.length;

        // 2. Quét danh mục nhãn từ Objects Sidebar của CVAT
        // Trong CVAT: .cvat-objects-sidebar-states-list hoặc các item labels
        const sidebarItems = document.querySelectorAll(".cvat-objects-sidebar-state-item, .cvat-objects-sidebar-label-item");
        const newLabels = new Map();

        // Thử quét từ sidebar
        sidebarItems.forEach((item) => {
            const labelTextEl = item.querySelector(".cvat-objects-sidebar-state-item-header, .ant-typography, [class*='label-name']");
            const colorDotEl = item.querySelector("[class*='color'], [style*='background-color']");
            if (labelTextEl) {
                const name = labelTextEl.textContent.trim().split("#")[0].trim();
                if (name) {
                    const color = colorDotEl ? (colorDotEl.style.backgroundColor || "#58a6ff") : "#58a6ff";
                    const current = newLabels.get(name) || { name, color, count: 0 };
                    current.count++;
                    newLabels.set(name, current);
                }
            }
        });

        // Nếu sidebar đang thu gọn hoặc chưa render, fallback quét từ canvas title/attributes
        if (newLabels.size === 0 && canvasShapes.length > 0) {
            canvasShapes.forEach((shape) => {
                const labelAttr = shape.getAttribute("data-label-name") || shape.getAttribute("title") || "Object";
                const color = shape.getAttribute("stroke") || shape.getAttribute("fill") || "#58a6ff";
                const current = newLabels.get(labelAttr) || { name: labelAttr, color, count: 0 };
                current.count++;
                newLabels.set(labelAttr, current);
            });
        }

        // Cập nhật state nếu có sự thay đổi
        if (newLabels.size > 0) {
            state.detectedLabels = newLabels;
        }

        // Kiểm tra và áp dụng Solo Mode nếu đang kích hoạt
        if (state.soloActive && state.activeSoloLabel) {
            applySoloFilter(state.activeSoloLabel);
        }

        updateStatsUI();
    }

    function checkOverloadState() {
        const isOverload = state.objectCount > state.threshold;
        const alertBox = document.getElementById("booster-alert-box");
        if (alertBox) {
            alertBox.style.display = isOverload && !state.soloActive ? "block" : "none";
        }
    }

    function updateStatsUI() {
        if (state.minimized) {
            renderWidget();
            return;
        }

        const countEl = widgetEl?.querySelector(".cvat-booster-stat-badge:nth-child(2) .cvat-booster-stat-val");
        if (countEl) {
            countEl.textContent = state.objectCount;
            countEl.style.color = state.objectCount > state.threshold ? "#f85149" : "#ffffff";
        }

        checkOverloadState();

        const labelsGrid = document.getElementById("labels-container");
        if (labelsGrid) {
            labelsGrid.innerHTML = renderLabelChips();
            // Gắn lại sự kiện cho các chip mới
            widgetEl.querySelectorAll(".cvat-booster-label-chip").forEach((chip) => {
                chip.addEventListener("click", () => {
                    const labelName = chip.getAttribute("data-label");
                    if (state.soloActive && state.activeSoloLabel === labelName) {
                        disableSoloMode();
                    } else {
                        enableSoloMode(labelName);
                    }
                });
            });
        }
    }

    // -------------------------------------------------------------------------
    // 5. Chế độ Solo Focus Mode (High-Performance Single-Label Isolation)
    // -------------------------------------------------------------------------
    function enableSoloMode(labelName) {
        state.soloActive = true;
        state.activeSoloLabel = labelName;

        // Mô phỏng click con mắt ẩn trên Sidebar của CVAT (nếu có tab Labels)
        triggerCvatNativeLabelVisibility(labelName);

        // Áp dụng lớp ẩn trực tiếp lên Canvas Shapes
        applySoloFilter(labelName);

        renderWidget();
    }

    function disableSoloMode() {
        state.soloActive = false;
        state.activeSoloLabel = null;

        // Bỏ style ẩn
        if (soloStyleEl) {
            soloStyleEl.textContent = "";
        }

        // Hiện lại toàn bộ các shapes trên DOM
        document.querySelectorAll(".cvat-solo-hidden-shape").forEach((el) => {
            el.classList.remove("cvat-solo-hidden-shape");
        });

        // Bật lại toàn bộ mắt trên sidebar CVAT
        restoreCvatNativeLabels();

        renderWidget();
    }

    function applySoloFilter(targetLabel) {
        // Quét các shape trên SVG Canvas
        const canvasShapes = document.querySelectorAll(
            ".cvat_canvas_shape, polygon.cvat_canvas_shape, rect.cvat_canvas_shape, polyline.cvat_canvas_shape, g.cvat_canvas_shape"
        );

        // Lấy thông tin màu hoặc ID của nhãn mục tiêu
        const targetInfo = state.detectedLabels.get(targetLabel);
        const targetColor = targetInfo ? targetInfo.color : null;

        canvasShapes.forEach((shape) => {
            // Xác định xem shape này có thuộc về targetLabel không
            const shapeLabel = shape.getAttribute("data-label-name") || shape.getAttribute("title");
            const shapeStroke = shape.getAttribute("stroke");
            const shapeFill = shape.getAttribute("fill");

            let isMatch = false;
            if (shapeLabel && shapeLabel === targetLabel) {
                isMatch = true;
            } else if (targetColor && (shapeStroke === targetColor || shapeFill === targetColor)) {
                isMatch = true;
            } else {
                // Kiểm tra qua sidebar mapping (nếu có client-id)
                const clientId = shape.getAttribute("data-client-id");
                if (clientId) {
                    const sidebarItem = document.querySelector(`.cvat-objects-sidebar-state-item[data-client-id="${clientId}"]`);
                    if (sidebarItem && sidebarItem.textContent.includes(targetLabel)) {
                        isMatch = true;
                    }
                }
            }

            if (isMatch) {
                shape.classList.remove("cvat-solo-hidden-shape");
            } else {
                shape.classList.add("cvat-solo-hidden-shape");
            }
        });
    }

    function triggerCvatNativeLabelVisibility(focusLabel) {
        // Tìm tab "Labels" trong objects sidebar của CVAT nếu người dùng đang mở tab đó
        const labelItems = document.querySelectorAll(".cvat-objects-sidebar-labels-list-item");
        labelItems.forEach((item) => {
            const nameEl = item.querySelector(".ant-typography");
            const eyeIcon = item.querySelector("[aria-label='eye'], [aria-label='eye-invisible'], .anticon-eye, .anticon-eye-invisible");
            if (nameEl && eyeIcon) {
                const name = nameEl.textContent.trim();
                const isHidden = eyeIcon.classList.contains("anticon-eye-invisible") || eyeIcon.getAttribute("aria-label") === "eye-invisible";
                if (name === focusLabel && isHidden) {
                    eyeIcon.click();
                } else if (name !== focusLabel && !isHidden) {
                    eyeIcon.click();
                }
            }
        });
    }

    function restoreCvatNativeLabels() {
        const labelItems = document.querySelectorAll(".cvat-objects-sidebar-labels-list-item");
        labelItems.forEach((item) => {
            const eyeIcon = item.querySelector("[aria-label='eye-invisible'], .anticon-eye-invisible");
            if (eyeIcon) {
                eyeIcon.click();
            }
        });
    }

    // -------------------------------------------------------------------------
    // 6. Theo dõi FPS Thời gian thực (Realtime FPS Tracker)
    // -------------------------------------------------------------------------
    function trackFps(now) {
        state.frameCount++;
        if (now - state.lastFpsUpdate >= 500) {
            state.fps = Math.round((state.frameCount * 1000) / (now - state.lastFpsUpdate));
            state.frameCount = 0;
            state.lastFpsUpdate = now;

            const fpsEl = widgetEl?.querySelector(".cvat-booster-stat-badge:nth-child(1) .cvat-booster-stat-val");
            if (fpsEl) {
                fpsEl.textContent = `${state.fps} FPS`;
                fpsEl.className = `cvat-booster-stat-val ${state.fps >= 45 ? "stat-fps-good" : (state.fps >= 25 ? "stat-fps-warn" : "stat-fps-bad")}`;
            }
        }
        requestAnimationFrame(trackFps);
    }

    // -------------------------------------------------------------------------
    // 7. Hệ thống Phím tắt (Hotkeys Navigation)
    // -------------------------------------------------------------------------
    function setupKeyboardShortcuts() {
        window.addEventListener("keydown", (e) => {
            // Không can thiệp nếu người dùng đang gõ trong ô text input
            if (["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName)) {
                return;
            }

            // 1. Shift + F: Bật / Tắt Solo Mode
            if (e.shiftKey && e.code === "KeyF") {
                e.preventDefault();
                if (state.soloActive) {
                    disableSoloMode();
                } else {
                    const firstLabel = Array.from(state.detectedLabels.keys())[0];
                    if (firstLabel) enableSoloMode(firstLabel);
                }
                return;
            }

            // 2. Escape: Hủy Solo Mode
            if (e.code === "Escape" && state.soloActive) {
                disableSoloMode();
                return;
            }

            // 3. Alt + [1..9]: Chọn nhanh nhãn 1 đến 9
            if (e.altKey && e.code.startsWith("Digit")) {
                const digit = parseInt(e.code.replace("Digit", ""), 10);
                if (digit >= 1 && digit <= 9) {
                    const labelNames = Array.from(state.detectedLabels.keys());
                    if (digit <= labelNames.length) {
                        e.preventDefault();
                        const selectedLabel = labelNames[digit - 1];
                        enableSoloMode(selectedLabel);
                    }
                }
            }
        });
    }

    // -------------------------------------------------------------------------
    // 8. Khởi chạy Extension (Bootstrap)
    // -------------------------------------------------------------------------
    function init() {
        injectStyles();
        createWidget();
        setupKeyboardShortcuts();
        requestAnimationFrame(trackFps);

        // Quét định kỳ mỗi 500ms
        setInterval(scanCvatObjects, 500);

        // Theo dõi thay đổi DOM của CVAT
        const observer = new MutationObserver(() => {
            scanCvatObjects();
        });
        observer.observe(document.body, { childList: true, subtree: true });

        console.log("🚀 [CVAT Booster] Extension đã được kích hoạt thành công!");
    }

    // Khởi chạy khi DOM đã sẵn sàng
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
