// script.js

const dropArea = document.getElementById('drop-area');
const fileInput = document.getElementById('file-input');
const fileName = document.getElementById('file-name');
const convertButton = document.getElementById('convert-button');
const downloadMp3Button = document.getElementById('download-mp3');
const downloadMidiButton = document.getElementById('download-midi');

let uploadedFile = null;
let instrumentFiles = {};
let currentHtdemucsOutput = '';

// **1. 드래그 앤 드롭 파일 업로드**
dropArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropArea.classList.add('dragover');
});

dropArea.addEventListener('dragleave', () => {
    dropArea.classList.remove('dragover');
});

dropArea.addEventListener('drop', (e) => {
    e.preventDefault();
    dropArea.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        uploadedFile = files[0];
        fileName.textContent = uploadedFile.name;
    }
});

dropArea.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
        uploadedFile = fileInput.files[0];
        fileName.textContent = uploadedFile.name;
    }
});

// **2. Convert to MIDI**
convertButton.addEventListener('click', async () => {
    console.log('Convert button clicked');
    if (!uploadedFile) {
        alert('파일을 먼저 업로드해주세요!');
        return;
    }

    const formData = new FormData();
    formData.append('file', uploadedFile);

    try {
        const response = await fetch('/convert', { // 상대 경로 사용
            method: 'POST',
            body: formData,
        });

        if (response.ok) {
            const data = await response.json();
            console.log('서버 응답:', data);

            // htdemucs_output을 글로벌 변수에 저장
            currentHtdemucsOutput = data.htdemucs_output;

            // 서버 응답 데이터로 다운로드 버튼 설정
            setupDownloadButtons(data.instrument_files);
            renderVisualization(data.visualization_data || {});
            alert('변환이 성공적으로 완료되었습니다!');
        } else {
            const errorData = await response.json();
            console.error('서버 오류:', errorData);
            alert(`변환 실패: ${errorData.error}`);
        }
    } catch (error) {
        console.error('요청 전송 오류:', error);
        alert('서버로 요청을 보내는 데 실패했습니다.');
    }
});

// **3. 피아노 롤 시각화 함수**
function renderPianoRoll(instrument, notes) {
    const container = document.getElementById(`${instrument}-visualization`);
    
    // 이전 시각화 내용 지우기
    container.innerHTML = '';

    const canvas = document.createElement('canvas');
    canvas.width = container.clientWidth;
    canvas.height = 200; // 필요에 따라 조정
    container.appendChild(canvas);

    const ctx = canvas.getContext('2d');

    // 피아노 롤 파라미터 정의
    const noteHeight = 10;
    const timeScale = 5; // 틱당 픽셀
    const pitchOffset = 21; // A0의 MIDI 노트 번호

    // 최대 시간을 계산하여 캔버스 너비 조정
    const maxTime = Math.max(...notes.map(note => note.position + note.duration), 0);
    canvas.width = Math.max(container.clientWidth, maxTime * timeScale + 100);

    // 노트 그리기
    notes.forEach(note => {
        const x = note.position * timeScale;
        const y = canvas.height - ((note.pitch - pitchOffset) * noteHeight);
        const width = note.duration * timeScale;
        const height = noteHeight;

        ctx.fillStyle = '#3f51b5';
        ctx.fillRect(x, y, width, height);
    });

    // 그리드 라인 추가 (선택 사항)
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 1;
    for (let i = 0; i <= canvas.width; i += 50) {
        ctx.beginPath();
        ctx.moveTo(i, 0);
        ctx.lineTo(i, canvas.height);
        ctx.stroke();
    }
    for (let i = 0; i <= canvas.height; i += 10) {
        ctx.beginPath();
        ctx.moveTo(0, i);
        ctx.lineTo(canvas.width, i);
        ctx.stroke();
    }

    // 피치 라벨 추가
    ctx.fillStyle = '#000';
    ctx.font = '10px Arial';
    for (let pitch = pitchOffset; pitch < pitchOffset + canvas.height / noteHeight; pitch++) {
        const y = canvas.height - ((pitch - pitchOffset) * noteHeight) - 2;
        ctx.fillText(midiNoteToName(pitch), 5, y);
    }
}

// **Helper 함수: MIDI 노트 번호를 노트 이름으로 변환**
function midiNoteToName(note) {
    const octave = Math.floor(note / 12) - 1;
    const names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    const name = names[note % 12];
    return `${name}${octave}`;
}

// **4. 시각화 데이터 렌더링 함수**
function renderVisualization(visualizationData) {
    for (const [instrument, notes] of Object.entries(visualizationData)) {
        renderPianoRoll(instrument, notes);
    }
}

// **5. 다운로드 버튼 설정 함수**
function setupDownloadButtons(files) {
    instrumentFiles = files;
}

// **6. MP3 다운로드 처리**
downloadMp3Button.addEventListener('click', () => {
    const selectedInstruments = getSelectedInstruments();
    if (selectedInstruments.length === 0) {
        alert('다운로드할 악기를 하나 이상 선택해주세요.');
        return;
    }

    fetch('/download_combined', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            instruments: selectedInstruments,
            htdemucs_output: currentHtdemucsOutput
        })
    })
    .then(response => {
        if (response.ok) {
            return response.blob();
        } else {
            return response.json().then(data => { throw new Error(data.error); });
        }
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'combined.mp3';
        document.body.appendChild(a);
        a.click();
        a.remove();
    })
    .catch(error => {
        console.error('MP3 다운로드 오류:', error);
        alert(`다운로드 실패: ${error.message}`);
    });
});

// **7. MIDI 다운로드 처리**
downloadMidiButton.addEventListener('click', () => {
    const selectedInstruments = getSelectedInstruments();
    if (selectedInstruments.length === 0) {
        alert('다운로드할 악기를 하나 이상 선택해주세요.');
        return;
    }

    fetch('/download_combined_midi', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            instruments: selectedInstruments,
            htdemucs_output: currentHtdemucsOutput
        })
    })
    .then(response => {
        if (response.ok) {
            return response.blob();
        } else {
            return response.json().then(data => { throw new Error(data.error); });
        }
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'combined.midi';
        document.body.appendChild(a);
        a.click();
        a.remove();
    })
    .catch(error => {
        console.error('MIDI 다운로드 오류:', error);
        alert(`다운로드 실패: ${error.message}`);
    });
});

// **8. 선택된 악기 가져오는 헬퍼 함수**
function getSelectedInstruments() {
    const instruments = [];
    if (document.getElementById('download-piano-checkbox').checked) instruments.push('piano');
    if (document.getElementById('download-guitar-checkbox').checked) instruments.push('guitar');
    if (document.getElementById('download-bass-checkbox').checked) instruments.push('bass');
    return instruments;
}
