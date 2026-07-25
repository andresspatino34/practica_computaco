document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const form = document.getElementById('series-form');
    const exprInput = document.getElementById('expression-input');
    const n0Input = document.getElementById('n0-input');
    const termsInput = document.getElementById('terms-input');
    const livePreview = document.getElementById('live-preview');
    const analyzeBtn = document.getElementById('analyze-btn');
    const btnSpinner = document.getElementById('btn-spinner');

    const emptyState = document.getElementById('empty-state');
    const resultsContent = document.getElementById('results-content');
    const statusBanner = document.getElementById('status-banner');
    const statusText = document.getElementById('status-text');
    const seriesDisplay = document.getElementById('series-display');

    const valLimit = document.getElementById('val-limit');
    const valSumExact = document.getElementById('val-sum-exact');
    const valSumNum = document.getElementById('val-sum-num');
    const testsList = document.getElementById('tests-list');
    const termsTableBody = document.getElementById('terms-table-body');

    let partialSumsChart = null;

    // Helper: Render LaTeX using KaTeX
    function renderMath(element, latexStr, displayMode = false) {
        try {
            katex.render(latexStr, element, {
                displayMode: displayMode,
                throwOnError: false
            });
        } catch (e) {
            element.textContent = latexStr;
        }
    }

    // Convert basic user expression to LaTeX preview draft
    function formatExpressionForPreview(raw) {
        let clean = raw.trim();
        if (!clean) return null;
        clean = clean.replace(/\*\*/g, '^');
        clean = clean.replace(/\*/g, ' \\cdot ');
        clean = clean.replace(/factorial\((.*?)\)/g, '($1)!');
        clean = clean.replace(/sqrt\((.*?)\)/g, '\\sqrt{$1}');
        return clean;
    }

    // Update Live LaTeX Preview
    function updateLivePreview() {
        const raw = exprInput.value;
        const formatted = formatExpressionForPreview(raw);
        if (!formatted) {
            livePreview.innerHTML = '<span class="placeholder-text">Vista previa LaTeX...</span>';
            return;
        }
        renderMath(livePreview, `a_n = ${formatted}`, true);
    }

    exprInput.addEventListener('input', updateLivePreview);
    updateLivePreview(); // Init preview

    const seriesSelect = document.getElementById('series-select');
    const seriesCards = document.querySelectorAll('.series-card');

    // Render KaTeX inside Condition (a) series cards
    document.querySelectorAll('.katex-render').forEach(el => {
        const latex = el.dataset.katex;
        if (latex) {
            renderMath(el, latex, false);
        }
    });

    // Helper to select a series
    function selectSeries(expr, n0 = 1) {
        exprInput.value = expr;
        n0Input.value = n0;

        // Sync card active state
        seriesCards.forEach(card => {
            if (card.dataset.expr === expr) {
                card.classList.add('active');
            } else {
                card.classList.remove('active');
            }
        });

        // Sync select dropdown
        if (seriesSelect) {
            const hasOption = Array.from(seriesSelect.options).some(opt => opt.value === expr);
            seriesSelect.value = hasOption ? expr : 'custom';
        }

        updateLivePreview();
        form.dispatchEvent(new Event('submit'));
    }

    // Series cards click handlers
    seriesCards.forEach(card => {
        card.addEventListener('click', () => {
            selectSeries(card.dataset.expr, card.dataset.n0 || 1);
        });
    });

    // Dropdown change handler
    if (seriesSelect) {
        seriesSelect.addEventListener('change', (e) => {
            const val = e.target.value;
            if (val !== 'custom') {
                selectSeries(val, 1);
            } else {
                exprInput.focus();
            }
        });
    }

    // Manual input typing removes active card highlight
    exprInput.addEventListener('input', () => {
        updateLivePreview();
        const current = exprInput.value.trim();
        let matched = false;
        seriesCards.forEach(card => {
            if (card.dataset.expr === current) {
                card.classList.add('active');
                matched = true;
            } else {
                card.classList.remove('active');
            }
        });
        if (seriesSelect) {
            seriesSelect.value = matched ? current : 'custom';
        }
    });

    // Form Submit Handler
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const expr = exprInput.value.trim();
        const n0 = parseInt(n0Input.value, 10);
        const terms = parseInt(termsInput.value, 10);

        if (!expr) return;

        // UI Loading State
        analyzeBtn.disabled = true;
        btnSpinner.hidden = false;

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    expression: expr,
                    start_n: n0,
                    num_terms: terms
                })
            });

            const data = await response.json();

            if (!data.success) {
                alert('Error al analizar la serie: ' + (data.error || 'Expresión no válida.'));
                return;
            }

            renderResults(data);

        } catch (err) {
            alert('Error de conexión con el servidor Python.');
            console.error(err);
        } finally {
            analyzeBtn.disabled = false;
            btnSpinner.hidden = true;
        }
    });

    // Render API Response
    function renderResults(data) {
        emptyState.hidden = true;
        resultsContent.hidden = false;

        // Status Banner Styling
        statusBanner.className = 'status-banner';
        if (data.status === 'CONVERGENTE') {
            statusBanner.classList.add('convergent');
            statusText.textContent = 'SERIE CONVERGENTE';
        } else if (data.status === 'DIVERGENTE') {
            statusBanner.classList.add('divergent');
            statusText.textContent = 'SERIE DIVERGENTE';
        } else {
            statusBanner.classList.add('inconclusive');
            statusText.textContent = 'DETERMINACIÓN INCONCLUSA';
        }

        // Series Formula Display
        renderMath(seriesDisplay, data.series_latex, true);

        // Condition b Rendering (Partial Sum S_N)
        const displayNVal = document.getElementById('display-n-val');
        const valSnExact = document.getElementById('val-sn-exact');
        const valSnNum = document.getElementById('val-sn-num');

        if (displayNVal) displayNVal.textContent = data.num_terms_N;
        if (valSnExact) renderMath(valSnExact, data.sn_exact_latex || `S_{${data.num_terms_N}} = \\text{Calculando...}`, true);
        if (valSnNum) {
            valSnNum.textContent = data.sn_numeric !== null ? 
                `Valor aproximado numérico: ${data.sn_numeric.toLocaleString('es-ES', { maximumFractionDigits: 8 })}` : 
                '';
        }

        // Summary Values
        renderMath(valLimit, data.limit_an_latex || '0');
        renderMath(valSumExact, data.sum_exact_latex || '\\text{N/A}');
        valSumNum.textContent = data.sum_numeric !== null ? data.sum_numeric.toLocaleString('es-ES', { maximumFractionDigits: 6 }) : 'N/A';

        // Tests Breakdown
        testsList.innerHTML = '';
        data.tests.forEach(test => {
            const testEl = document.createElement('div');
            testEl.className = 'test-item';

            let badgeClass = 'badge-inconclusive';
            if (test.conclusion.includes('Converge')) badgeClass = 'badge-converge';
            if (test.conclusion.includes('Diverge')) badgeClass = 'badge-diverge';

            testEl.innerHTML = `
                <div class="test-header">
                    <span class="test-name">${test.name}</span>
                    <span class="test-badge ${badgeClass}">${test.conclusion}</span>
                </div>
                <div class="test-formula"></div>
                <div class="test-details"></div>
            `;

            testsList.appendChild(testEl);

            renderMath(testEl.querySelector('.test-formula'), test.formula, false);
            renderMath(testEl.querySelector('.test-details'), test.details, false);
        });

        // Table Rows
        termsTableBody.innerHTML = '';
        data.partial_sums.forEach(row => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${row.n}</td>
                <td>${row.an}</td>
                <td>${row.Sn}</td>
            `;
            termsTableBody.appendChild(tr);
        });

        // Update Partial Sums Chart
        renderChart(data.partial_sums, data.status);
    }

    // Chart.js Visualization
    function renderChart(partialSums, status) {
        const ctx = document.getElementById('partial-sums-chart').getContext('2d');

        const labels = partialSums.map(item => `n=${item.n}`);
        const dataSn = partialSums.map(item => item.Sn);
        const dataAn = partialSums.map(item => item.an);

        if (partialSumsChart) {
            partialSumsChart.destroy();
        }

        const primaryColor = status === 'CONVERGENTE' ? '#34d399' : (status === 'DIVERGENTE' ? '#fb7185' : '#fbbf24');

        partialSumsChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Suma Parcial (Sₙ)',
                        data: dataSn,
                        borderColor: primaryColor,
                        backgroundColor: primaryColor + '20',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.2,
                        pointRadius: 4
                    },
                    {
                        label: 'Término General (aₙ)',
                        data: dataAn,
                        borderColor: '#38bdf8',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        fill: false,
                        pointRadius: 3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: '#94a3b8', font: { family: 'Inter' } }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#94a3b8' }
                    },
                    y: {
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#94a3b8' }
                    }
                }
            }
        });
    }

    // Auto-analyze default example on startup
    setTimeout(() => {
        form.dispatchEvent(new Event('submit'));
    }, 300);
});
