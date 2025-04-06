#!/usr/bin/env python3
"""
Web controller for Matrix Effect Animation

This script creates a web server that allows controlling the Matrix animation
via a web interface. You can start, pause, and stop the animation through
a browser at http://192.168.86.56.
"""

import os
import subprocess
import threading
import time
import signal
import json
from flask import Flask, render_template_string, request, jsonify
import flaschen_np

# Configuration
HOST = '0.0.0.0'  # Listen on all interfaces
PORT = 80  # Changed from 8080 to 80
DISPLAY_WIDTH = 192
DISPLAY_HEIGHT = 128
DISPLAY_LAYER = 2        # Animation layer
DISPLAY_TEXT_LAYER = 1   # Text layer (lower than animation)
FT_HOST = 'localhost'
FT_PORT = 1337
SETTINGS_FILE = 'matrix_settings.json'

# Animation process
matrix_process = None
animation_paused = False
stop_event = threading.Event()
animation_state = "Stopped"  # Initial state tracker: "Running", "Paused", or "Stopped"
current_color = "green"  # Default color will be loaded from settings if available
custom_text = ""  # No default text, will be loaded from settings
color_change_event = threading.Event()  # Added to signal color change to animation process

# Initialize Flask app
app = Flask(__name__)

# Initialize the display interface
ft = None

# Load settings from file if it exists
def load_settings():
    global current_color, custom_text
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
                current_color = settings.get('color', 'green')
                custom_text = settings.get('text', '')
                print(f"Loaded settings: color={current_color}, text='{custom_text}'")
    except Exception as e:
        print(f"Error loading settings: {e}")

# Save settings to file
def save_settings():
    try:
        settings = {
            'color': current_color,
            'text': custom_text
        }
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f)
            print(f"Saved settings: {settings}")
    except Exception as e:
        print(f"Error saving settings: {e}")

# HTML template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Matrix Animation Controller</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #000;
            color: #0f0;
            margin: 0;
            padding: 20px;
            text-align: center;
        }
        h1 {
            margin-bottom: 30px;
            font-size: 28px;
            text-shadow: 0 0 10px #0f0;
        }
        .control-panel {
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: rgba(0, 40, 0, 0.7);
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0, 255, 0, 0.5);
        }
        .button-container {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 20px;
        }
        button {
            background-color: #003300;
            border: 2px solid #00ff00;
            color: #00ff00;
            padding: 15px 30px;
            font-size: 18px;
            cursor: pointer;
            border-radius: 5px;
            transition: all 0.3s;
        }
        button:hover {
            background-color: #005500;
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.7);
        }
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .status {
            margin-top: 30px;
            font-size: 20px;
            font-weight: bold;
        }
        .current-status {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            background-color: rgba(0, 80, 0, 0.8);
            margin-top: 10px;
        }
        .color-options {
            margin-top: 30px;
            padding: 15px;
            background-color: rgba(0, 40, 0, 0.5);
            border-radius: 10px;
        }
        .text-options {
            margin-top: 30px;
            padding: 15px;
            background-color: rgba(0, 40, 0, 0.5);
            border-radius: 10px;
        }
        .section-title {
            margin-bottom: 15px;
            font-size: 18px;
        }
        .color-selector {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 15px;
        }
        .color-option {
            display: flex;
            align-items: center;
            cursor: pointer;
            padding: 5px 10px;
            border-radius: 5px;
            background-color: rgba(0, 60, 0, 0.7);
            transition: all 0.3s;
        }
        .color-option:hover {
            background-color: rgba(0, 100, 0, 0.7);
        }
        .color-option input {
            margin-right: 8px;
        }
        .color-green {
            text-shadow: 0 0 5px #0f0;
        }
        .color-red {
            text-shadow: 0 0 5px #f00;
            color: #f55;
        }
        .color-blue {
            text-shadow: 0 0 5px #00f;
            color: #5ff;
        }
        .color-yellow {
            text-shadow: 0 0 5px #ff0;
            color: #ff5;
        }
        .color-random {
            text-shadow: 0 0 5px #f0f;
            color: #f5f;
        }
        .text-input {
            width: 80%;
            padding: 10px;
            background-color: rgba(0, 60, 0, 0.7);
            color: #0f0;
            border: 2px solid #00ff00;
            border-radius: 5px;
            font-size: 16px;
            margin-bottom: 10px;
        }
        .text-input:focus {
            outline: none;
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.7);
        }
        .update-text-btn {
            padding: 8px 15px;
            background-color: #003300;
            border: 2px solid #00ff00;
            color: #00ff00;
            cursor: pointer;
            border-radius: 5px;
            font-size: 16px;
            transition: all 0.3s;
        }
        .update-text-btn:hover {
            background-color: #005500;
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.7);
        }
    </style>
</head>
<body>
    <div class="control-panel">
        <h1>Matrix Animation Controller</h1>
        
        <div class="button-container">
            <button id="startBtn" onclick="controlAnimation('start')">Start Animation</button>
            <button id="pauseBtn" onclick="controlAnimation('pause')" disabled>Pause</button>
            <button id="stopBtn" onclick="controlAnimation('stop')" disabled>Stop</button>
        </div>
        
        <div class="status">
            Status: <div class="current-status" id="status">Stopped</div>
        </div>
        
        <div class="text-options">
            <div class="section-title">Display Text</div>
            <input type="text" id="customText" class="text-input" placeholder="Enter text to display" maxlength="20">
            <button class="update-text-btn" onclick="updateText()">Update Text</button>
        </div>
        
        <div class="color-options">
            <div class="section-title">Matrix Color</div>
            <div class="color-selector">
                <label class="color-option">
                    <input type="radio" name="color" value="green" checked onchange="changeColor('green')">
                    <span class="color-green">Green</span>
                </label>
                <label class="color-option">
                    <input type="radio" name="color" value="red" onchange="changeColor('red')">
                    <span class="color-red">Red</span>
                </label>
                <label class="color-option">
                    <input type="radio" name="color" value="blue" onchange="changeColor('blue')">
                    <span class="color-blue">Blue</span>
                </label>
                <label class="color-option">
                    <input type="radio" name="color" value="yellow" onchange="changeColor('yellow')">
                    <span class="color-yellow">Yellow</span>
                </label>
                <label class="color-option">
                    <input type="radio" name="color" value="random" onchange="changeColor('random')">
                    <span class="color-random">Random</span>
                </label>
            </div>
        </div>
    </div>

    <script>
        // Update UI based on current state
        function updateUI(state, text) {
            document.getElementById('status').textContent = state;
            
            if (state === 'Running') {
                document.getElementById('startBtn').disabled = true;
                document.getElementById('pauseBtn').disabled = false;
                document.getElementById('stopBtn').disabled = false;
            } else if (state === 'Paused') {
                document.getElementById('startBtn').disabled = false;
                document.getElementById('pauseBtn').disabled = true;
                document.getElementById('stopBtn').disabled = true;
            } else if (state === 'Stopped') {
                document.getElementById('startBtn').disabled = false;
                document.getElementById('pauseBtn').disabled = true;
                document.getElementById('stopBtn').disabled = true;
            }
            
            // Update the text input field if provided
            if (text) {
                document.getElementById('customText').value = text;
            }
        }

        // Get current status and color on page load
        window.onload = function() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    updateUI(data.status, data.text);
                    // Set the color radio button based on server state
                    document.querySelector(`input[name="color"][value="${data.color}"]`).checked = true;
                });
        };

        // Control the animation
        function controlAnimation(action) {
            fetch('/control', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ action: action }),
            })
            .then(response => response.json())
            .then(data => {
                updateUI(data.status);
            });
        }
        
        // Change the animation color
        function changeColor(color) {
            fetch('/color', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ color: color }),
            })
            .then(response => response.json())
            .then(data => {
                console.log("Color changed to: " + data.color);
            });
        }
        
        // Update the custom text
        function updateText() {
            const text = document.getElementById('customText').value;
            fetch('/text', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text: text }),
            })
            .then(response => response.json())
            .then(data => {
                console.log("Text updated to: " + data.text);
            });
        }
    </script>
</body>
</html>
"""

def get_color_code(color_name):
    """Convert color name to RGB tuple"""
    if color_name == "green":
        return "00ff00"  # Green
    elif color_name == "red":
        return "ff0000"  # Red
    elif color_name == "blue":
        return "00aaff"  # Blue (slightly cyan for better visibility)
    elif color_name == "yellow":
        return "ffff00"  # Yellow
    elif color_name == "random":
        return "random"  # Special case for random
    else:
        return "00ff00"  # Default to green

def draw_time_text():
    """Draw current time in HH:MM:SS format"""
    current_time = time.strftime("%H:%M:%S")
    return current_time

def draw_text(text, color=(0, 255, 0), layer=None, clear_first=True):
    """Draw text on the display"""
    global ft
    
    # Use specified layer or default text layer
    if layer is None:
        layer = DISPLAY_TEXT_LAYER
    
    # Create a new FlaschenNP instance for the text layer
    text_ft = flaschen_np.FlaschenNP(FT_HOST, FT_PORT, DISPLAY_WIDTH, DISPLAY_HEIGHT, layer)
    
    if clear_first:
        # Clear just the text layer if not drawing multiple lines
        text_ft.zero()
    
    # Simple 5x7 pixel font for uppercase letters and some special characters
    font = {
        'A': [0x3E, 0x51, 0x51, 0x3E, 0x00],  # Reverted to original pattern
        'B': [0x7F, 0x49, 0x49, 0x36, 0x00],
        'C': [0x3E, 0x41, 0x41, 0x22, 0x00],
        'D': [0x7F, 0x41, 0x41, 0x3E, 0x00],
        'E': [0x7F, 0x49, 0x49, 0x41, 0x00],
        'F': [0x7F, 0x48, 0x48, 0x40, 0x00],
        'G': [0x3E, 0x41, 0x49, 0x2F, 0x00],
        'H': [0x7F, 0x08, 0x08, 0x7F, 0x00],
        'I': [0x41, 0x7F, 0x41, 0x00, 0x00],
        'J': [0x06, 0x01, 0x01, 0x7E, 0x00],
        'K': [0x7F, 0x08, 0x14, 0x63, 0x00],
        'L': [0x7F, 0x01, 0x01, 0x01, 0x00],
        'M': [0x7F, 0x20, 0x10, 0x20, 0x7F],
        'N': [0x7F, 0x10, 0x08, 0x04, 0x7F],
        'O': [0x3E, 0x41, 0x41, 0x3E, 0x00],
        'P': [0x7F, 0x48, 0x48, 0x30, 0x00],
        'Q': [0x3E, 0x41, 0x45, 0x3F, 0x00],
        'R': [0x7F, 0x48, 0x4C, 0x33, 0x00],
        'S': [0x32, 0x49, 0x49, 0x26, 0x00],
        'T': [0x40, 0x40, 0x7F, 0x40, 0x40],
        'U': [0x7E, 0x01, 0x01, 0x7E, 0x00],
        'V': [0x7C, 0x02, 0x01, 0x02, 0x7C],
        'W': [0x7F, 0x02, 0x04, 0x02, 0x7F],
        'X': [0x63, 0x14, 0x08, 0x14, 0x63],
        'Y': [0x70, 0x08, 0x07, 0x08, 0x70],
        'Z': [0x43, 0x45, 0x49, 0x51, 0x61],
        ' ': [0x00, 0x00, 0x00, 0x00, 0x00],
        '.': [0x01, 0x01, 0x00, 0x00, 0x00],
        ',': [0x01, 0x02, 0x00, 0x00, 0x00],
        ':': [0x14, 0x14, 0x00, 0x00, 0x00],
        '!': [0x7D, 0x00, 0x00, 0x00, 0x00],
        '?': [0x20, 0x40, 0x45, 0x38, 0x00],
        '(': [0x3E, 0x41, 0x00, 0x00, 0x00],
        ')': [0x41, 0x3E, 0x00, 0x00, 0x00],
        '+': [0x08, 0x08, 0x3E, 0x08, 0x08],
        '-': [0x08, 0x08, 0x08, 0x08, 0x00],
        '/': [0x01, 0x02, 0x04, 0x08, 0x10],
        '\\': [0x10, 0x08, 0x04, 0x02, 0x01],
        '0': [0x3E, 0x45, 0x49, 0x51, 0x3E],
        '1': [0x00, 0x21, 0x7F, 0x01, 0x00],
        '2': [0x21, 0x43, 0x45, 0x49, 0x31],
        '3': [0x22, 0x41, 0x49, 0x49, 0x36],
        '4': [0x0C, 0x14, 0x24, 0x7F, 0x04],
        '5': [0x72, 0x51, 0x51, 0x51, 0x4E],
        '6': [0x1E, 0x29, 0x49, 0x49, 0x06],
        '7': [0x40, 0x40, 0x47, 0x58, 0x60],
        '8': [0x36, 0x49, 0x49, 0x49, 0x36],
        '9': [0x30, 0x49, 0x49, 0x4A, 0x3C],
    }
    
    # Add current time to text
    if text.strip():
        text = text + "\n" + draw_time_text()
    else:
        # When showing welcome text, show time as well
        if "PRESS START" in text:
            text = text + "\n" + draw_time_text()
    
    # Handle newlines in text
    lines = text.split('\n')
    
    # Calculate total height needed for all lines
    char_height = 7  # Original size
    line_spacing = 10  # Space between lines
    total_height = len(lines) * char_height + (len(lines) - 1) * (line_spacing - char_height)
    
    # Start position for the first line (centered vertically)
    start_y = (DISPLAY_HEIGHT - total_height) // 2
    
    # Process each line
    for i, line in enumerate(lines):
        line = line.upper()  # Convert to uppercase
        
        # Calculate text width and center position horizontally for this line
        char_width = 6  # Original size
        text_width = len(line) * char_width
        start_x = (DISPLAY_WIDTH - text_width) // 2
        
        # Current Y position for this line
        current_y = start_y + i * line_spacing
        
        # Draw the line of text
        x = start_x
        for char in line:
            if char in font:
                # Draw the character (no scaling)
                pattern = font[char]
                for col in range(5):
                    bits = pattern[col]
                    for row in range(7):
                        if bits & (1 << (6 - row)):  # Flip vertically
                            # Draw a single pixel (normal size)
                            text_ft.set(x + col, current_y + row, color)
            x += char_width
    
    # Send to display
    text_ft.send()

def draw_welcome_text():
    """Draw the welcome message with IP address using a single text call"""
    ip_address = f"HTTP://{HOST}" if HOST != '0.0.0.0' else f"HTTP://192.168.86.56"
    # Use a single draw_text call with a newline character
    draw_text(f"PRESS START AT:\n{ip_address}", 
              color=(0, 180, 0))  # Use same color for both lines

def fill_screen(color, layer=None):
    """Fill the display with a single color"""
    global ft
    
    # Use specified layer or default animation layer
    if layer is None:
        layer = DISPLAY_LAYER
    
    fill_ft = flaschen_np.FlaschenNP(FT_HOST, FT_PORT, DISPLAY_WIDTH, DISPLAY_HEIGHT, layer)
    
    for y in range(DISPLAY_HEIGHT):
        for x in range(DISPLAY_WIDTH):
            fill_ft.set(x, y, color)
    fill_ft.send()

def update_time_display():
    """Updates time display without affecting main text"""
    global custom_text, animation_state, current_color
    
    if animation_state == "Stopped":
        # Just update the welcome text with current time
        draw_welcome_text()
    elif animation_state in ["Running", "Paused"] and custom_text.strip():
        # Determine color based on current setting
        color_rgb = (0, 255, 0)  # Default green
        if current_color == "red":
            color_rgb = (255, 0, 0)
        elif current_color == "blue":
            color_rgb = (0, 170, 255)
        elif current_color == "yellow":
            color_rgb = (255, 255, 0)
            
        # Update the text with the current time
        draw_text(custom_text, color=color_rgb)

def run_matrix_animation():
    """Run the matrix animation in a separate thread"""
    global matrix_process, animation_paused, stop_event, animation_state, current_color, color_change_event, custom_text
    
    # Text display thread reference
    text_thread = None
    text_thread_stop = threading.Event()
    
    # Clock update thread
    clock_thread_stop = threading.Event()
    
    # Function for clock thread
    def clock_update_thread():
        """Thread to update the clock display"""
        while not clock_thread_stop.is_set():
            update_time_display()
            time.sleep(1)  # Update every second
    
    # Start the clock update thread
    clock_thread = threading.Thread(target=clock_update_thread)
    clock_thread.daemon = True
    clock_thread.start()
    
    # Skip initial welcome text as it's already drawn in main thread
    initial_startup = True
    
    while not stop_event.is_set():
        if animation_state == "Running":
            # Get color parameter
            color_param = get_color_code(current_color)
            
            # Command to start the matrix effect
            cmd = [
                "python", "matrix_effect.py",
                "--width", str(DISPLAY_WIDTH),
                "--height", str(DISPLAY_HEIGHT),
                "--layer", str(DISPLAY_LAYER)
            ]
            
            # Add color parameter if not random
            if color_param != "random":
                cmd.extend(["--color", color_param])
            else:
                cmd.extend(["--color", "random"])
            
            # If animation should be running but isn't, start it
            if matrix_process is None or matrix_process.poll() is not None:
                matrix_process = subprocess.Popen(cmd)
                # Clear the color change event since we're starting fresh
                color_change_event.clear()
                
                # If there's custom text, display it overlay after a short delay
                if custom_text and custom_text.strip() != "":
                    # Wait a moment for the matrix to initialize
                    time.sleep(0.5)
                    # Display the text overlay
                    color_rgb = (0, 255, 0)  # Default green
                    if current_color == "red":
                        color_rgb = (255, 0, 0)
                    elif current_color == "blue":
                        color_rgb = (0, 170, 255)
                    elif current_color == "yellow":
                        color_rgb = (255, 255, 0)
                    
                    # Stop any existing text thread
                    if text_thread and text_thread.is_alive():
                        text_thread_stop.set()
                        text_thread.join(timeout=1.0)
                    
                    # Create thread stop event
                    text_thread_stop = threading.Event()
                    
                    # Draw custom text only once on the background layer
                    draw_text(custom_text, color=color_rgb)
        elif animation_state == "Paused":
            # If paused and process is running, just leave it (will be frozen by signal)
            pass
        elif animation_state == "Stopped":
            # If stopped and process is running, terminate it
            if matrix_process and matrix_process.poll() is None:
                matrix_process.terminate()
                matrix_process.wait()
                matrix_process = None
                
            # Always display welcome text when stopped (but skip if it's the initial startup)
            if not initial_startup:
                draw_welcome_text()
        
        # After first loop, we're no longer in initial startup
        initial_startup = False
        
        # If color has changed, we don't need to restart the process, new raindrops will use the new color
        if color_change_event.is_set():
            color_change_event.clear()
            
            # If there's custom text and we're running, update the text color
            if custom_text and custom_text.strip() != "" and animation_state in ["Running", "Paused"]:
                color_rgb = (0, 255, 0)  # Default green
                if current_color == "red":
                    color_rgb = (255, 0, 0)
                elif current_color == "blue":
                    color_rgb = (0, 170, 255)
                elif current_color == "yellow":
                    color_rgb = (255, 255, 0)
                    
                # Update the text with the new color
                draw_text(custom_text, color=color_rgb)
        
        time.sleep(0.5)
    
    # Ensure the process is stopped when exiting
    if matrix_process and matrix_process.poll() is None:
        matrix_process.terminate()
        matrix_process.wait()
        matrix_process = None
    
    # Clear the display
    fill_screen((0, 0, 0))
    fill_screen((0, 0, 0), layer=DISPLAY_TEXT_LAYER)

    # Stop clock thread when exiting
    clock_thread_stop.set()
    if clock_thread.is_alive():
        clock_thread.join(timeout=1.0)

@app.route('/')
def index():
    """Serve the main web interface"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/status')
def get_status():
    """Return the current animation status and color"""
    global animation_state, current_color, custom_text
    return jsonify({"status": animation_state, "color": current_color, "text": custom_text})

@app.route('/color', methods=['POST'])
def change_color():
    """Change the matrix color"""
    global current_color, animation_state, matrix_process, color_change_event
    
    # Get the new color from the request
    new_color = request.json.get('color', 'green')
    current_color = new_color
    
    # Save the updated settings
    save_settings()
    
    # Set the color change event to notify the animation thread
    color_change_event.set()
    
    # Don't restart the animation when color changes
    # The color changes will affect newly spawned raindrops
    
    return jsonify({"color": current_color})

@app.route('/control', methods=['POST'])
def control_animation():
    """Handle animation control commands"""
    global matrix_process, animation_state
    action = request.json.get('action')
    
    if action == 'start':
        if animation_state == "Paused":
            # Resume from pause (send SIGCONT to resume the process)
            if matrix_process and matrix_process.poll() is None:
                os.kill(matrix_process.pid, signal.SIGCONT)
        elif animation_state == "Stopped":
            # Start fresh
            if matrix_process and matrix_process.poll() is None:
                matrix_process.terminate()
                matrix_process.wait()
                matrix_process = None
        
        animation_state = "Running"
    
    elif action == 'pause':
        if animation_state == "Running":
            # Pause the animation (send SIGSTOP to freeze the process)
            if matrix_process and matrix_process.poll() is None:
                os.kill(matrix_process.pid, signal.SIGSTOP)
            animation_state = "Paused"
    
    elif action == 'stop':
        # Stop the animation regardless of current state
        if matrix_process and matrix_process.poll() is None:
            matrix_process.terminate()
            matrix_process.wait()
            matrix_process = None
        # Always show welcome text when stopped
        draw_welcome_text()
        animation_state = "Stopped"
    
    return jsonify({"status": animation_state})

@app.route('/text', methods=['POST'])
def update_text():
    """Update the text overlay"""
    global custom_text, animation_state, matrix_process
    
    # Get the new text from the request
    new_text = request.json.get('text', '')
    custom_text = new_text
    
    # Save the updated settings
    save_settings()
    
    # If the animation is running or paused, update the text display
    if animation_state in ["Running", "Paused"] and custom_text.strip():
        # Determine color based on current setting
        color_rgb = (0, 255, 0)  # Default green
        if current_color == "red":
            color_rgb = (255, 0, 0)
        elif current_color == "blue":
            color_rgb = (0, 170, 255)
        elif current_color == "yellow":
            color_rgb = (255, 255, 0)
            
        # Update the text with the new content
        draw_text(custom_text, color=color_rgb)
    elif animation_state == "Stopped":
        # In stopped state, always show welcome text regardless of custom text
        draw_welcome_text()
    
    return jsonify({"text": custom_text})

def signal_handler(sig, frame):
    """Handle SIGINT and SIGTERM signals"""
    stop_event.set()
    if matrix_process and matrix_process.poll() is None:
        matrix_process.terminate()
    print("\nShutting down web server...")
    os._exit(0)

if __name__ == '__main__':
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Load settings from file
    load_settings()
    
    # This ensures the welcome message is shown BEFORE any Flask initialization
    print("Initializing display and showing welcome message...")
    
    # Initialize both layers immediately
    fill_screen((0, 0, 0))  # Clear animation layer
    fill_screen((0, 0, 0), layer=DISPLAY_TEXT_LAYER)  # Clear text layer
    
    # Draw welcome text including time directly without any threading
    ip_address = f"HTTP://{HOST}" if HOST != '0.0.0.0' else f"HTTP://192.168.86.56"
    welcome_text = f"PRESS START AT:\n{ip_address}"
    draw_text(welcome_text, color=(0, 180, 0))
    
    # Ensure text is visible by forcing the send
    ft = flaschen_np.FlaschenNP(FT_HOST, FT_PORT, DISPLAY_WIDTH, DISPLAY_HEIGHT, DISPLAY_TEXT_LAYER)
    ft.send()
    
    # More time to ensure display update completes
    time.sleep(2)
    
    # Wait for confirmation (if needed)
    print("Welcome message displayed.")
    
    # Set initial state
    animation_state = "Stopped"
    
    # Start animation control thread AFTER welcome text is already displayed
    animation_thread = threading.Thread(target=run_matrix_animation)
    animation_thread.daemon = True
    animation_thread.start()
    
    # Wait a bit more to ensure the thread doesn't immediately overwrite our text
    time.sleep(0.5)
    
    # Start the web server
    print(f"Starting web server at http://192.168.86.56:{PORT}")
    app.run(host=HOST, port=PORT, debug=False) 