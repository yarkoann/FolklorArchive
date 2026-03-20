let currentPage = 1;
let currentFilters = {};
let currentSort = 'title';

document.addEventListener('DOMContentLoaded', () => {
    console.log('Страница загружена, инициализация...');
    loadFacets();
    performSearch();

    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                performSearch();
            }
        });
    }

    const sortSelect = document.getElementById('sort-select');
    if (sortSelect) {
        sortSelect.addEventListener('change', sortResults);
    }
});

// Функция очистки поиска
function clearSearch() {
    console.log('Очистка поиска');
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.value = '';
    }
    currentFilters = {};
    currentPage = 1;
    loadFacets();
    performSearch(1);
    updateActiveFilters();
}

async function loadFacets() {
    try {
        console.log('Загрузка фасетов...');
        const response = await fetch('/api/facets');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Фасеты загружены:', data);
        displayFacets(data);
    } catch (error) {
        console.error('Error loading facets:', error);
    }
}

function displayFacets(facets) {
    console.log('Отображение фасетов:', facets);

    // Этносы
    let ethnosHtml = '';
    for (let [name, count] of Object.entries(facets.ethnos || {})) {
        const isActive = currentFilters.ethnos === name;
        ethnosHtml += `<div class="facet-item ${isActive ? 'active' : ''}" onclick="addFilter('ethnos', '${name.replace(/'/g, "\\'")}')">
            ${name} <span class="facet-count">(${count})</span>
        </div>`;
    }
    const ethnosDiv = document.getElementById('facet-ethnos');
    if (ethnosDiv) {
        ethnosDiv.innerHTML = ethnosHtml || '<p>Нет данных</p>';
    }

    // Жанры
    let genreHtml = '';
    for (let [name, count] of Object.entries(facets.genre || {})) {
        const isActive = currentFilters.genre === name;
        genreHtml += `<div class="facet-item ${isActive ? 'active' : ''}" onclick="addFilter('genre', '${name.replace(/'/g, "\\'")}')">
            ${name} <span class="facet-count">(${count})</span>
        </div>`;
    }
    const genreDiv = document.getElementById('facet-genre');
    if (genreDiv) {
        genreDiv.innerHTML = genreHtml || '<p>Нет данных</p>';
    }

    // Этический статус
    const statusNames = {
        'публичный_доступ': 'Публичный',
        'ограниченный_доступ': 'Ограниченный',
        'требует_согласия_общины': 'Требует согласия'
    };

    let statusHtml = '';
    for (let [status, count] of Object.entries(facets.status || {})) {
        if (count > 0) {
            const displayName = statusNames[status] || status;
            const isActive = currentFilters.status === status;
            statusHtml += `<div class="facet-item ${isActive ? 'active' : ''}" onclick="addFilter('status', '${status}')">
                ${displayName} <span class="facet-count">(${count})</span>
            </div>`;
        }
    }
    const statusDiv = document.getElementById('facet-status');
    if (statusDiv) {
        statusDiv.innerHTML = statusHtml || '<p>Нет данных</p>';
    }

    // Локации
    let locationHtml = '';
    for (let [name, count] of Object.entries(facets.location || {})) {
        const isActive = currentFilters.location === name;
        locationHtml += `<div class="facet-item ${isActive ? 'active' : ''}" onclick="addFilter('location', '${name.replace(/'/g, "\\'")}')">
            ${name} <span class="facet-count">(${count})</span>
        </div>`;
    }
    const locationDiv = document.getElementById('facet-location');
    if (locationDiv) {
        locationDiv.innerHTML = locationHtml || '<p>Нет данных</p>';
    }

    // Коллекции
    let collectionHtml = '';
    for (let [name, count] of Object.entries(facets.collection || {})) {
        const isActive = currentFilters.collection === name;
        collectionHtml += `<div class="facet-item ${isActive ? 'active' : ''}" onclick="addFilter('collection', '${name.replace(/'/g, "\\'")}')">
            ${name} <span class="facet-count">(${count})</span>
        </div>`;
    }
    const collectionDiv = document.getElementById('facet-collection');
    if (collectionDiv) {
        collectionDiv.innerHTML = collectionHtml || '<p>Нет данных</p>';
    }

    // Десятилетия
    let decadesHtml = '';
    // Сортируем десятилетия по порядку
    const sortedDecades = Object.entries(facets.decades || {}).sort((a, b) => a[0].localeCompare(b[0]));
    for (let [decade, count] of sortedDecades) {
        const isActive = currentFilters.decade === decade;
        decadesHtml += `<div class="facet-item ${isActive ? 'active' : ''}" onclick="addFilter('decade', '${decade}')">
            ${decade} гг. <span class="facet-count">(${count})</span>
        </div>`;
    }
    const decadesDiv = document.getElementById('facet-decades');
    if (decadesDiv) {
        decadesDiv.innerHTML = decadesHtml || '<p>Нет данных</p>';
    }
}

async function performSearch(page = 1) {
    currentPage = page;

    const searchInput = document.getElementById('search-input');
    const query = searchInput ? searchInput.value : '';
    const resultsDiv = document.getElementById('results-list');
    const countSpan = document.getElementById('results-count');

    if (!resultsDiv) return;

    resultsDiv.innerHTML = '<div class="loading"><div class="loading-spinner"></div><p>Загрузка...</p></div>';

    try {
        let url = `/api/facet_search?page=${page}&sort=${currentSort}`;

        if (query) {
            url += `&q=${encodeURIComponent(query)}`;
        }

        // Добавляем все фильтры из currentFilters
        console.log('Добавление фильтров в URL:', currentFilters);
        for (let [key, value] of Object.entries(currentFilters)) {
            if (value) {
                url += `&${key}=${encodeURIComponent(value)}`;
                console.log(`  Добавлен параметр: ${key}=${value}`);
            }
        }

        console.log('Полный URL запроса:', url);
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Получены данные:', data);

        if (countSpan) {
            countSpan.textContent = `Найдено записей: ${data.total || 0}`;
        }

        displayResults(data.results || []);
        displayPagination(data);

    } catch (error) {
        console.error('Search error:', error);
        resultsDiv.innerHTML = '<div class="error">Ошибка при выполнении поиска</div>';
    }
}

function displayResults(results) {
    const resultsDiv = document.getElementById('results-list');
    if (!resultsDiv) return;

    if (!results || results.length === 0) {
        resultsDiv.innerHTML = '<div class="no-results">Ничего не найдено</div>';
        return;
    }

    let html = '';
    results.forEach(recording => {
        const statusClass = getStatusClass(recording.status);
        const statusName = getStatusName(recording.status);

        // Формируем URL для детальной информации
        const detailUrl = `/recording/${recording.id}`;

        // Добавляем отображение коллекции
        const collectionDisplay = recording.collection ? recording.collection : 'Не указана';

        // Форматируем исполнителей
        let performersDisplay = '';
        if (recording.performers && recording.performers.length > 0) {
            performersDisplay = recording.performers.map(p => {
                if (p.ethnos) {
                    return `${p.name} (${p.ethnos})`;
                }
                return p.name;
            }).join(', ');
        } else {
            performersDisplay = 'Неизвестен';
        }

        // Форматируем этносы для фильтрации (берем первый этнос для простоты)
        const ethnosDisplay = recording.performers && recording.performers.length > 0 && recording.performers[0].ethnos
            ? recording.performers[0].ethnos
            : 'Не указан';

        html += `
            <div class="result-card" onclick="window.location.href='${detailUrl}'">
                <div class="result-title">${escapeHtml(recording.title)}</div>
                <div class="result-meta">
                    <span class="meta-item">📅 ${recording.date || 'Дата неизвестна'}</span>
                    <span class="meta-item">🎤 ${escapeHtml(performersDisplay)}</span>
                </div>
                <div class="result-meta">
                    <span class="meta-item">🌍 ${escapeHtml(ethnosDisplay)}</span>
                    <span class="meta-item">🎵 ${escapeHtml(recording.genre || 'Жанр не указан')}</span>
                    <span class="meta-item">📀 ${escapeHtml(collectionDisplay)}</span>
                </div>
                <div class="result-meta">
                    <span class="meta-item">🔖 ${escapeHtml(recording.inventory_number || 'Без номера')}</span>
                    <span class="status-badge ${statusClass}">${statusName}</span>
                </div>
            </div>
        `;
    });

    resultsDiv.innerHTML = html;
}

function displayPagination(data) {
    const paginationDiv = document.getElementById('pagination');
    if (!paginationDiv) return;

    if (!data.total_pages || data.total_pages <= 1) {
        paginationDiv.innerHTML = '';
        return;
    }

    let html = '<div class="pagination-controls">';

    // Кнопка "Предыдущая"
    if (data.page > 1) {
        html += `<button class="page-btn" onclick="performSearch(${data.page - 1})">←</button>`;
    }

    // Номера страниц
    for (let i = 1; i <= data.total_pages; i++) {
        if (i === 1 || i === data.total_pages || (i >= data.page - 2 && i <= data.page + 2)) {
            html += `<button class="page-btn ${i === data.page ? 'active' : ''}" 
                           onclick="performSearch(${i})">${i}</button>`;
        } else if (i === data.page - 3 || i === data.page + 3) {
            html += '<span class="page-dots">...</span>';
        }
    }

    // Кнопка "Следующая"
    if (data.page < data.total_pages) {
        html += `<button class="page-btn" onclick="performSearch(${data.page + 1})">→</button>`;
    }

    html += '</div>';
    paginationDiv.innerHTML = html;
}

function addFilter(type, value) {
    console.log(`Добавление фильтра: ${type}=${value}`);
    currentFilters[type] = value;
    currentPage = 1;
    console.log('Текущие фильтры после добавления:', currentFilters);
    loadFacets();
    performSearch(1);
    updateActiveFilters();
}

function removeFilter(type) {
    console.log(`Удаление фильтра: ${type}`);
    delete currentFilters[type];
    currentPage = 1;
    loadFacets();
    performSearch(1);
    updateActiveFilters();
}

function resetFilters() {
    console.log('Сброс фильтров');
    currentFilters = {};
    currentPage = 1;
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.value = '';
    }
    loadFacets();
    performSearch(1);
    updateActiveFilters();
}

function updateActiveFilters() {
    const container = document.getElementById('active-filters');
    if (!container) return;

    if (Object.keys(currentFilters).length === 0) {
        container.innerHTML = '';
        return;
    }

    let html = '<strong>Активные фильтры:</strong> ';
    for (let [type, value] of Object.entries(currentFilters)) {
        let displayValue = value;
        if (type === 'status') {
            const statusNames = {
                'публичный_доступ': 'Публичный',
                'ограниченный_доступ': 'Ограниченный',
                'требует_согласия_общины': 'Требует согласия'
            };
            displayValue = statusNames[value] || value;
        }
        html += `<span class="filter-tag" onclick="removeFilter('${type}')">${type}: ${displayValue} ✖</span>`;
    }

    container.innerHTML = html;
}

function getStatusClass(status) {
    if (!status || status.includes('публичный')) return 'status-public';
    if (status.includes('ограниченный')) return 'status-restricted';
    if (status.includes('согласия')) return 'status-community';
    return 'status-public';
}

function getStatusName(status) {
    if (!status) return 'Публичный';
    if (status.includes('публичный')) return 'Публичный';
    if (status.includes('ограниченный')) return 'Ограниченный';
    if (status.includes('согласия')) return 'Требует согласия';
    return status;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function exportMETS() {
    window.location.href = '/api/export_mets';
}

function sortResults() {
    currentSort = document.getElementById('sort-select').value;
    performSearch(1);
}