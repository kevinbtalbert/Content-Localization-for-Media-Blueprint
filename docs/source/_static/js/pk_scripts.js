/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

document.addEventListener("DOMContentLoaded", function () {
    var params = window.location.search.substring(1).split("&").reduce(function (params, param) {
        if (!param) {
            return params;
        }

        var values = param.split("=");
        var name = values[0];
        var value = values[1];
        params[name] = value;
        return params;
    }, {});

    var form = document.getElementById("feedback-form");
    if (form) {
        for (var name in params) {
            var input = form.querySelector("[name=" + name + "]");
            if (input) {
                input.value = params[name];
            }
        }
    }

    // Initialize Mermaid diagram zoom controls
    initializeMermaidZoom();
});

function initializeMermaidZoom() {
    // Wait for Mermaid to finish rendering
    var checkMermaidInterval = setInterval(function() {
        var mermaidDivs = document.querySelectorAll('.mermaid');
        
        if (mermaidDivs.length > 0) {
            // Check if at least one has been rendered (has SVG child)
            var hasRendered = Array.from(mermaidDivs).some(function(div) {
                return div.querySelector('svg') !== null;
            });
            
            if (hasRendered) {
                clearInterval(checkMermaidInterval);
                wrapMermaidDiagrams();
            }
        }
    }, 100);

    // Stop checking after 10 seconds
    setTimeout(function() {
        clearInterval(checkMermaidInterval);
    }, 10000);
}

function wrapMermaidDiagrams() {
    var mermaidDivs = document.querySelectorAll('.mermaid');
    
    mermaidDivs.forEach(function(mermaidDiv, index) {
        // Skip if already wrapped
        if (mermaidDiv.parentElement.classList.contains('mermaid-wrapper')) {
            return;
        }

        // Create wrapper structure
        var wrapper = document.createElement('div');
        wrapper.className = 'mermaid-wrapper';
        
        var container = document.createElement('div');
        container.className = 'mermaid-container';
        
        var content = document.createElement('div');
        content.className = 'mermaid-content';
        content.setAttribute('data-zoom-level', '1');
        
        // Create toolbar
        var toolbar = document.createElement('div');
        toolbar.className = 'mermaid-zoom-toolbar';
        
        var zoomInBtn = document.createElement('button');
        zoomInBtn.className = 'mermaid-zoom-btn';
        zoomInBtn.textContent = '+';
        zoomInBtn.title = 'Zoom In';
        
        var zoomOutBtn = document.createElement('button');
        zoomOutBtn.className = 'mermaid-zoom-btn';
        zoomOutBtn.textContent = '−';
        zoomOutBtn.title = 'Zoom Out';
        
        var resetBtn = document.createElement('button');
        resetBtn.className = 'mermaid-zoom-btn';
        resetBtn.textContent = '⟲';
        resetBtn.title = 'Reset Zoom';
        
        toolbar.appendChild(zoomInBtn);
        toolbar.appendChild(zoomOutBtn);
        toolbar.appendChild(resetBtn);
        
        // Insert wrapper before the original mermaid div
        mermaidDiv.parentNode.insertBefore(wrapper, mermaidDiv);
        
        // Move mermaid div into the content div
        content.appendChild(mermaidDiv);
        container.appendChild(content);
        wrapper.appendChild(toolbar);
        wrapper.appendChild(container);
        
        // Add event listeners
        zoomInBtn.addEventListener('click', function() {
            zoomDiagram(content, 0.2);
        });
        
        zoomOutBtn.addEventListener('click', function() {
            zoomDiagram(content, -0.2);
        });
        
        resetBtn.addEventListener('click', function() {
            resetZoom(content);
        });
    });
}

function zoomDiagram(contentDiv, delta) {
    var currentZoom = parseFloat(contentDiv.getAttribute('data-zoom-level'));
    var newZoom = Math.max(0.5, Math.min(3.0, currentZoom + delta));
    
    contentDiv.setAttribute('data-zoom-level', newZoom);
    contentDiv.style.transform = 'scale(' + newZoom + ')';
}

function resetZoom(contentDiv) {
    contentDiv.setAttribute('data-zoom-level', '1');
    contentDiv.style.transform = 'scale(1)';
}