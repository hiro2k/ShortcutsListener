from flask import Flask, request, send_file
import os
import subprocess
import threading
import time

app = Flask(__name__)
debug = False  # set to True to print debug messages

UPLOAD_FOLDER = os.path.join(os.path.expanduser('~'), 'Downloads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def message(msg, code=200, printMessage=False):
    if debug or printMessage:
        print(msg)
    return msg, code


def extract_filename_from_output(output_text):
    """Extract filename from yt-dlp output"""
    output_lines = output_text.split('\n')
    for line in output_lines:
        if line.startswith('[ExtractAudio] Destination:'):
            # Extract filename from the line
            return line.split('Destination:')[-1].strip()
        elif line.startswith('[CopyStream] Copying stream of'):
            # Extract filename from the CopyStream line
            return line.split('Copying stream of "')[-1].rstrip('"')
        elif line.startswith('[VideoConvertor] Converting video from') and 'Destination:' in line:
            # Extract filename from the VideoConvertor line
            return line.split('Destination:')[-1].strip()
        elif line.startswith('[VideoConvertor] Not converting media file') and 'already is in target format' in line:
            # Extract filename from the VideoConvertor line when no conversion is needed
            # Format: [VideoConvertor] Not converting media file "/path/to/file.mp4"; already is in target format mp4
            start_marker = 'media file "'
            end_marker = '"; already is in target format'
            start_idx = line.find(start_marker) + len(start_marker)
            end_idx = line.find(end_marker)
            if start_idx > len(start_marker) - 1 and end_idx > start_idx:
                return line[start_idx:end_idx]
        elif line.startswith('[ExtractAudio] Not converting audio') and 'file is already in target format' in line:
            # Extract filename from the ExtractAudio line when no conversion is needed
            # Format: [ExtractAudio] Not converting audio /path/to/file.mp3; file is already in target format mp3
            start_marker = 'Not converting audio '
            end_marker = '; file is already in target format'
            start_idx = line.find(start_marker) + len(start_marker)
            end_idx = line.find(end_marker)
            if start_idx > len(start_marker) - 1 and end_idx > start_idx:
                return line[start_idx:end_idx]
    return None


def delete_file_after_delay(file_path, delay_minutes=5):
    """Delete file after specified delay in minutes"""
    def delete_file():
        time.sleep(delay_minutes * 60)  # Convert minutes to seconds
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(
                    f'Deleted file after {delay_minutes} minutes: {file_path}')
        except Exception as e:
            print(f'Error deleting file {file_path}: {e}')

    # Start deletion timer in background thread
    timer_thread = threading.Thread(target=delete_file, daemon=True)
    timer_thread.start()


@app.route('/', methods=['POST'])
def upload_file():
    if 'yta' in request.headers:
        url = request.headers.get('yta')
        popenargs = ['/home/hgarza/.local/bin/yt-dlp', '--no-cache-dir', '--no-mtime',  '-x',
                     '--audio-format', 'mp3', '-o', os.path.join(UPLOAD_FOLDER, '%(title)s.%(ext)s'), url]
        print(f'Downloading audio from: {url}')
    elif 'ytv' in request.headers:
        url = request.headers.get('ytv')
        #popenargs = ['/home/hgarza/.local/bin/yt-dlp', '--no-cache-dir', '--no-mtime',  '-S', 'vcodec:h264/acodec:m4a', '-o', os.path.join(
        #    UPLOAD_FOLDER, '%(title)s.%(ext)s'), '--use-postprocessor', 'FFmpegCopyStream', '--ppa', 'CopyStream:-c:v libx264 -c:a aac -f mp4', url]
        popenargs = ['/home/hgarza/.local/bin/yt-dlp', '--no-cache-dir', '--no-mtime', '-o', os.path.join(
            UPLOAD_FOLDER, '%(title)s.%(ext)s'), '--recode-video', 'mp4', url]
        print(f'Downloading video from: {url}')
    else:
        return message(f'Error: No URL provided', 400)

    try:
        print(popenargs)
        # Use Popen to get real-time output
        process = subprocess.Popen(popenargs, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                 text=True, bufsize=1, universal_newlines=True)
        
        # Collect all output for filename extraction
        full_output = ""
        
        # Stream output in real-time
        if process.stdout:
            for line in process.stdout:
                print(line.rstrip())  # Print each line as it comes
                full_output += line   # Collect for later processing
        
        # Wait for process to complete
        process.wait()
        
        # Check if process was successful
        if process.returncode != 0:
            return message(f'yt-dlp failed with return code: {process.returncode}', 400)
        
        # Extract filename from collected output
        filename = extract_filename_from_output(full_output)
        if filename:
            print(f'Downloaded to: {filename}')
            # Start deletion timer for the downloaded file
            # delete_file_after_delay(filename, 5)
            return send_file(filename, as_attachment=True)
        else:
            print('Could not determine downloaded filename')
            return message('Could not determine downloaded filename', 400)
    except FileNotFoundError as e:
        print(e)
        return message(f'yt-dlp not found. Please install yt-dlp first. {e}', 400)
    except subprocess.CalledProcessError as e:
        print("Command failed!")
        print("Return code:", e.returncode)
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return message(f'yt-dlp failed: {e.stderr}', 400)


if __name__ == '__main__':
    print('Saving to location: ' + UPLOAD_FOLDER)
    # Change the port number as needed
    app.run(debug=debug, host='0.0.0.0', port=2560)
