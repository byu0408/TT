# server.py
from flask import Flask, request, jsonify, send_file
import os
import subprocess
import json
import mido
from mido import MidiFile, MidiTrack, Message
from pydub import AudioSegment
import io

app = Flask(__name__)

UPLOAD_FOLDER = './uploads'
HTDEMUCS_FOLDER = './separated/htdemucs_6s'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def extract_midi_notes(midi_file_path):
    mid = mido.MidiFile(midi_file_path)
    notes = []
    current_time = 0
    note_on_times = {}

    for msg in mid:
        current_time += msg.time
        if msg.type == 'note_on' and msg.velocity > 0:
            note_on_times[msg.note] = current_time
        elif (msg.type == 'note_off') or (msg.type == 'note_on' and msg.velocity == 0):
            if msg.note in note_on_times:
                start_time = note_on_times.pop(msg.note)
                duration = current_time - start_time
                notes.append({
                    'pitch': msg.note,
                    'position': start_time,
                    'duration': duration
                })
    return notes

# **변환 엔드포인트**
@app.route('/convert', methods=['POST'])
def convert():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    base_name = os.path.splitext(file.filename)[0]  # 파일명에서 확장자 제거
    htdemucs_output = base_name
    full_htdemucs_output = os.path.join(HTDEMUCS_FOLDER, htdemucs_output)

    try:
        # sep.py 스크립트를 입력 인수와 함께 실행
        result = subprocess.run(
            ['python', 'sep.py', '--input', file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )

        print("sep.py 출력:", result.stdout)
        print("sep.py 오류:", result.stderr)

        # htdemucs 출력 경로 확인 (올바른 절대 경로 사용)
        if not os.path.exists(full_htdemucs_output):
            return jsonify({'error': 'MIDI conversion failed'}), 500

        # 악기별 파일 매핑 및 시각화 데이터 추출
        instrument_files = {}
        visualization_data = {}
        for instrument in ['piano', 'guitar', 'bass']:
            midi_file = os.path.join(full_htdemucs_output, f"{instrument}.midi")
            mp3_file = os.path.join(full_htdemucs_output, f"{instrument}.mp3")
            if os.path.exists(midi_file) or os.path.exists(mp3_file):
                instrument_files[instrument] = {
                    'mp3': f"{htdemucs_output}/{instrument}.mp3" if os.path.exists(mp3_file) else '',
                    'midi': f"{htdemucs_output}/{instrument}.midi" if os.path.exists(midi_file) else ''
                }
                # MIDI 파일이 존재하면 시각화 데이터 추출
                if os.path.exists(midi_file):
                    notes = extract_midi_notes(midi_file)
                    visualization_data[instrument] = notes
                else:
                    visualization_data[instrument] = []
            else:
                instrument_files[instrument] = {
                    'mp3': '',
                    'midi': ''
                }
                visualization_data[instrument] = []

        # JSON 응답에 시각화 데이터 포함
        return jsonify({
            'htdemucs_output': htdemucs_output,
            'instrument_files': instrument_files,
            'visualization_data': visualization_data
        })
    except subprocess.CalledProcessError as e:
        print("Error during conversion:")
        print("Return Code:", e.returncode)
        print("Output:", e.output)
        print("Error Output:", e.stderr)
        return jsonify({'error': 'Conversion process failed', 'details': e.stderr}), 500

# **Combined MP3 Download Endpoint**
@app.route('/download_combined', methods=['POST'])
def download_combined_mp3():
    data = request.get_json()
    instruments = data.get('instruments', [])
    htdemucs_output = data.get('htdemucs_output', '')

    if not instruments:
        return jsonify({'error': 'No instruments selected'}), 400

    combined_audio = None

    for instrument in instruments:
        mp3_file = os.path.join(HTDEMUCS_FOLDER, htdemucs_output, f"{instrument}.mp3")
        print(f"Looking for MP3 file: {mp3_file}")  # 디버깅용

        if os.path.exists(mp3_file):
            try:
                audio = AudioSegment.from_mp3(mp3_file)
                if combined_audio is None:
                    combined_audio = audio
                else:
                    combined_audio = combined_audio.overlay(audio)
            except Exception as e:
                print(f"Error loading {mp3_file}: {e}")
                return jsonify({'error': f'Error loading {instrument} MP3'}), 500
        else:
            print(f"MP3 file for {instrument} not found: {mp3_file}")  # 디버깅용
            return jsonify({'error': f'MP3 file for {instrument} not found.'}), 404

    if combined_audio:
        buf = io.BytesIO()
        combined_audio.export(buf, format='mp3')
        buf.seek(0)
        return send_file(buf, mimetype='audio/mpeg', as_attachment=True, attachment_filename='combined.mp3')
    else:
        return jsonify({'error': 'No audio to combine'}), 400

# **Combined MIDI Download Endpoint**
@app.route('/download_combined_midi', methods=['POST'])
def download_combined_midi():
    data = request.get_json()
    instruments = data.get('instruments', [])
    htdemucs_output = data.get('htdemucs_output', '')

    if not instruments:
        return jsonify({'error': 'No instruments selected'}), 400

    combined_mid = MidiFile()
    combined_mid.ticks_per_beat = 480  # 표준 값

    for instrument in instruments:
        midi_file = os.path.join(HTDEMUCS_FOLDER, htdemucs_output, f"{instrument}.midi")
        print(f"Looking for MIDI file: {midi_file}")  # 디버깅용

        if os.path.exists(midi_file):
            try:
                mid = MidiFile(midi_file)
                track = MidiTrack()
                combined_mid.tracks.append(track)

                # 악기 프로그램 번호 설정
                program_number = get_program_number(instrument)
                track.append(Message('program_change', program=program_number, time=0))

                for msg in mid:
                    track.append(msg)
            except Exception as e:
                print(f"Error loading {midi_file}: {e}")
                return jsonify({'error': f'Error loading {instrument} MIDI'}), 500
        else:
            print(f"MIDI file for {instrument} not found: {midi_file}")  # 디버깅용
            return jsonify({'error': f'MIDI file for {instrument} not found.'}), 404

    # 합성된 MIDI를 버퍼에 저장
    buf = io.BytesIO()
    combined_mid.save(file=buf)
    buf.seek(0)
    return send_file(buf, mimetype='audio/midi', as_attachment=True, attachment_filename='combined.midi')

def get_program_number(instrument):
    # General MIDI 프로그램 번호 정의
    instrument_programs = {
        'piano': 0,    # Acoustic Grand Piano
        'guitar': 24,  # Acoustic Guitar (nylon)
        'bass': 32     # Acoustic Bass
    }
    return instrument_programs.get(instrument, 0)  # 기본값: Acoustic Grand Piano

# **파일 다운로드 엔드포인트**
@app.route('/download/<path:filename>', methods=['GET'])
def download_file(filename):
    # 디렉토리 트래버설 공격 방지
    safe_path = os.path.normpath(filename)
    if '..' in safe_path.split(os.path.sep):
        return jsonify({'error': 'Invalid file path'}), 400

    file_path = os.path.join(HTDEMUCS_FOLDER, safe_path)
    print(f"Received download request for: {filename}")
    print(f"Resolved file path: {file_path}")

    if os.path.exists(file_path):
        print(f"File found: {file_path}. Sending to client.")
        return send_file(file_path, as_attachment=True)
    else:
        print(f"File not found: {file_path}")
        return jsonify({'error': 'File not found'}), 404

# **정적 파일 제공**
@app.route('/')
def index():
    return send_file('main.html')

@app.route('/style.css')
def serve_css():
    return send_file('style.css')

@app.route('/script.js')
def serve_js():
    return send_file('script.js')

if __name__ == '__main__':
    app.run(port=5000)
