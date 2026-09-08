const $ = s => document.querySelector(s);

let course = null;
let currentVideo = null;
let lastSave = 0;

async function getJSON(url, options = {}) {
    const response = await fetch(url, options);

    if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
    }

    return response.json();
}

async function load() {
    course = await getJSON('/api/course');

    renderActivities();
    renderConcepts();
    renderTimeline();
    initVideos();

    await refresh();
}

function initVideos() {
    const select = $('#videoSelect');

    select.innerHTML =
        '<option value="">Selecciona una grabación…</option>';

    (course.videos || []).forEach(video => {
        const option = document.createElement('option');

        option.value = video.id;
        option.textContent = video.title;

        select.appendChild(option);
    });

    select.addEventListener('change', () => {
        selectVideo(select.value);
    });
}

async function selectVideo(id) {
    if (!id) {
        return;
    }

    currentVideo = (course.videos || []).find(
        video => video.id === id
    );

    if (!currentVideo) {
        return;
    }

    const player = $('#player');

    /*
     * El JSON contiene solamente el nombre del archivo:
     *
     *     Und_Bien.mp4
     *
     * Flask expone:
     *
     *     /media/videos/<archivo>
     *
     * Por eso NO debemos volver a agregar
     * "media/videos" desde el JSON.
     */
    const filename = String(currentVideo.file || '')
        .split('/')
        .pop();

    player.src =
        '/media/videos/' +
        encodeURIComponent(filename);

    player.load();

    $('#videoState').textContent =
        'Cargando evidencia…';

    try {
        const progress =
            await getJSON('/api/progress/' + currentVideo.id);

        player.onloadedmetadata = () => {
            if (
                progress.position > 5 &&
                progress.position < player.duration - 3
            ) {
                player.currentTime = progress.position;
            }
        };
    } catch (error) {
        console.warn(
            'No se pudo recuperar el progreso:',
            error
        );
    }
}

async function save(force = false) {
    if (
        !currentVideo ||
        !$('#player').duration ||
        !Number.isFinite($('#player').duration)
    ) {
        return;
    }

    const player = $('#player');
    const now = Date.now();

    if (!force && now - lastSave < 5000) {
        return;
    }

    lastSave = now;

    const duration = player.duration;
    const position = player.currentTime;

    const completed =
        position / duration >= 0.95;

    try {
        await getJSON(
            '/api/progress/' + currentVideo.id,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    position,
                    duration,
                    completed
                })
            }
        );

        await refresh();
    } catch (error) {
        console.error(
            'Error guardando progreso:',
            error
        );
    }
}

$('#player').addEventListener(
    'timeupdate',
    () => {
        const player = $('#player');

        if (
            !player.duration ||
            !Number.isFinite(player.duration)
        ) {
            return;
        }

        const percentage = Math.round(
            player.currentTime /
            player.duration *
            100
        );

        $('#videoBar').style.width =
            percentage + '%';

        $('#videoPct').textContent =
            percentage + '%';

        $('#videoState').textContent =
            percentage >= 95
                ? '✅ VIDEO COMPLETADO · evidencia observada'
                : '▶ EN PROGRESO · evidencia observada';

        $('#truthVideo').textContent =
            percentage >= 95
                ? 'VERIFIED'
                : 'PENDING';

        save(false);
    }
);

$('#player').addEventListener(
    'pause',
    () => save(true)
);

$('#player').addEventListener(
    'ended',
    () => save(true)
);

$('#sync').addEventListener(
    'click',
    refresh
);

function esc(value) {
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

async function refresh() {
    try {
        const state =
            await getJSON('/api/state');

        if (state.overall_progress !== undefined) {
            const value =
                Math.round(
                    Number(state.overall_progress) * 100
                );

            $('#overall').textContent =
                value + '%';

            $('#overallbar').style.width =
                value + '%';
        }

        if (state.mastery !== undefined) {
            const value =
                Math.round(
                    Number(state.mastery) * 100
                );

            $('#mastery').textContent =
                value + '%';

            $('#masterybar').style.width =
                value + '%';
        }

        if (state.evidence_count !== undefined) {
            $('#evidence').textContent =
                state.evidence_count;
        }

        if (state.unknown !== undefined) {
            $('#unknown').textContent =
                state.unknown;
        }
    } catch (error) {
        console.warn(
            'No se pudo actualizar el estado:',
            error
        );
    }
}

function renderActivities() {
    const container = $('#activityList');

    if (!container) {
        return;
    }

    container.innerHTML = '';

    (course.items || []).forEach(item => {
        const div = document.createElement('div');

        div.className = 'task';

        div.innerHTML = `
            <input
                type="checkbox"
                disabled
            >
            <div>
                <strong>${esc(item.title)}</strong>
                <p>${esc(item.brief || '')}</p>
            </div>
        `;

        container.appendChild(div);
    });
}

function renderConcepts() {
    const container = $('#conceptList');

    if (!container) {
        return;
    }

    container.innerHTML = '';

    (course.concepts || []).forEach(concept => {
        const div = document.createElement('div');

        div.className = 'concept';

        div.innerHTML = `
            <strong>${esc(concept.title)}</strong>
            <p>${esc(concept.definition || '')}</p>
        `;

        container.appendChild(div);
    });
}

function renderTimeline() {
    const container = $('#timeline');

    if (!container) {
        return;
    }

    container.innerHTML = '';

    (course.items || []).forEach(item => {
        const div = document.createElement('div');

        div.className = 'task';

        div.innerHTML = `
            <div>
                <strong>${esc(item.title)}</strong>
                <p>
                    Fecha:
                    ${esc(item.due || 'Sin fecha')}
                </p>
            </div>
        `;

        container.appendChild(div);
    });
}

load().catch(error => {
    console.error(error);

    $('#videoState').textContent =
        'Error: ' + error.message;
});
