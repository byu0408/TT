# sep.py

import argparse
import demucs.separate
import shlex
import os
import glob
import mido
import subprocess
import json

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

def main():
    parser = argparse.ArgumentParser(description="Separate MP3 and convert to MIDI")
    parser.add_argument('--input', type=str, required=True, help='Path to input MP3 file')

    args = parser.parse_args()

    input_mp3 = args.input

    # demucs를 사용하여 오디오 분리 실행
    demucs_command = f'--mp3 -n htdemucs_6s -d cpu "{input_mp3}"'
    print(f"Running demucs with command: {demucs_command}")
    try:
        demucs.separate.main(shlex.split(demucs_command))
    except Exception as e:
        print(f"demucs 실행 중 오류 발생: {e}")
        exit(1)

    # 분리된 MP3 파일 경로
    base_name = os.path.splitext(os.path.basename(input_mp3))[0]
    music_folder = os.path.join('./separated/htdemucs_6s/', base_name)

    # 모든 분리된 MP3 파일 찾기
    mp3_files = glob.glob(os.path.join(music_folder, '*.mp3'), recursive=True)

    # 악기별 MIDI 프로그램 번호 설정 (General MIDI 기준)
    instrument_programs = {
        'piano': 0,    # Acoustic Grand Piano
        'guitar': 24,  # Acoustic Guitar (nylon)
        'bass': 32     # Acoustic Bass
    }

    # MIDI 파일에서 악기 변경 함수
    def change_instrument(midi_file_path, program_number):
        mid = mido.MidiFile(midi_file_path)
        for track in mid.tracks:
            for msg in track:
                if msg.type == 'program_change':
                    msg.program = program_number
        mid.save(midi_file_path)

    # 각 분리된 MP3 파일 처리
    visualization_data = {}
    for mp3_file in mp3_files:
        file_name = os.path.splitext(os.path.basename(mp3_file))[0]
        midi_file_path = os.path.join(music_folder, f"{file_name}.midi")

        # 파일 이름을 기반으로 악기 결정
        instrument = None
        for inst in instrument_programs.keys():
            if inst in mp3_file.lower():
                instrument = inst
                break

        if not instrument:
            print(f'Skipping {mp3_file} (no matching instrument)')
            continue

        program_number = instrument_programs[instrument]

        # transkun을 사용하여 MP3를 MIDI로 변환
        transkun_command = f'transkun "{mp3_file}" "{midi_file_path}" --device cpu'
        print(f"Executing transkun command: {transkun_command}")
        try:
            transkun_result = subprocess.run(
                shlex.split(transkun_command),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            print(f"transkun 출력: {transkun_result.stdout}")
        except subprocess.CalledProcessError as e:
            print(f"transkun 실행 중 오류 발생 for {mp3_file}:")
            print(e.stderr)
            continue

        # MIDI 파일이 생성되었는지 확인
        if not os.path.exists(midi_file_path):
            print(f'Failed to generate MIDI file for {mp3_file}')
            continue

        # MIDI 파일에서 악기 번호 변경
        try:
            change_instrument(midi_file_path, program_number)
            print(f'Instrument changed to {instrument} for {midi_file_path}')
        except Exception as e:
            print(f"MIDI 파일 수정 중 오류 발생 for {midi_file_path}: {e}")

        # 시각화를 위한 MIDI 노트 추출
        try:
            notes = extract_midi_notes(midi_file_path)
            visualization_data[instrument] = notes
            print(f"Extracted {len(notes)} notes for {instrument}")
        except Exception as e:
            print(f"Failed to extract notes from {midi_file_path}: {e}")
            visualization_data[instrument] = []

    # 시각화 데이터를 JSON 형식으로 저장 (옵션, 디버깅용)
    # with open(os.path.join(music_folder, 'visualization_data.json'), 'w') as f:
    #     json.dump(visualization_data, f, indent=4)

if __name__ == '__main__':
    main()
