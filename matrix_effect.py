#!/usr/bin/env python
"""
Matrix Effect Demo for Flaschen Taschen

Based on the C++ matrix.cc program but implemented in Python
using the flaschen_np library.
"""

import flaschen_np
import numpy as np
import time
import argparse
import random
import signal
import sys
import json
import os

# Defaults (match the C++ version)
Z_LAYER = 2        # (0-15) 0=background
DELAY = 50         # milliseconds
FADE_STEP = 8      # Match C++ fade step
NUM_DOTS = 6
DEFAULT_MATRIX_COLOR = (0, 255, 0)  # Matrix green
SETTINGS_FILE = 'matrix_settings.json'  # For reading color changes at runtime

# Handle ctrl+c gracefully
interrupt_received = False
def signal_handler(signal, frame):
    global interrupt_received
    interrupt_received = True
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Function to check for color changes
def check_color_change(current_color):
    try:
        if os.path.exists(SETTINGS_FILE):
            # Get file modification time to avoid unnecessary reads
            mod_time = os.path.getmtime(SETTINGS_FILE)
            if not hasattr(check_color_change, 'last_mod_time') or mod_time > check_color_change.last_mod_time:
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                    color_name = settings.get('color', 'green')
                    check_color_change.last_mod_time = mod_time
                    
                    # Convert color name to RGB
                    if color_name == "green":
                        return (0, 255, 0)
                    elif color_name == "red":
                        return (255, 0, 0)
                    elif color_name == "blue":
                        return (0, 170, 255)
                    elif color_name == "yellow":
                        return (255, 255, 0)
                    elif color_name == "random":
                        return "random"
    except Exception as e:
        print(f"Error reading color settings: {e}")
    
    # Return the current color if no change or error
    return current_color

def color_gradient(start, end, r1, g1, b1, r2, g2, b2):
    """Create a color gradient from RGB1 to RGB2"""
    colors = []
    for i in range(end - start + 1):
        k = i / float(end - start)
        r = int(r1 + (r2 - r1) * k)
        g = int(g1 + (g2 - g1) * k)
        b = int(b1 + (b2 - b1) * k)
        colors.append((r, g, b))
    return colors

class MatrixRaindrop:
    def __init__(self, x, height, speed=1, color=None):
        self.x = x                      # x-position
        self.y = 0                      # starts at the top
        self.height = height            # screen height
        self.speed = 1                  # consistent speed like C++ version
        self.length = random.randint(15, 35)  # longer trail lengths to match C++ version
        self.active = True              # whether this raindrop is active
        self.brightness = 255           # start bright (the head)
        # If random colors are enabled, assign a random color to this raindrop
        self.color = color
        if color == "random":
            # Pick a random color from a set of good matrix colors
            color_options = [
                (0, 255, 0),    # green
                (255, 0, 0),    # red
                (0, 170, 255),  # blue (cyan-ish)
                (255, 255, 0),  # yellow
                (255, 0, 255),  # magenta
                (0, 255, 255),  # cyan
            ]
            self.color = random.choice(color_options)
        elif isinstance(color, tuple) and len(color) == 3:
            # If it's already an RGB tuple, use it directly
            self.color = color

    def update(self):
        """Move the raindrop down the screen"""
        self.y += self.speed
        if self.y - self.length > self.height:
            self.active = False
        return self.active

def main():
    parser = argparse.ArgumentParser(
        description='Matrix Effect for Flaschen Taschen',
        formatter_class=lambda prog: argparse.ArgumentDefaultsHelpFormatter(prog)
    )
    
    parser.add_argument('--host', type=str, default='localhost', help='Host to send packets to')
    parser.add_argument('--port', type=int, default=1337, help='Port to send packets to')
    parser.add_argument('--height', type=int, default=35, help='Canvas height')
    parser.add_argument('--width', type=int, default=45, help='Canvas width')
    parser.add_argument('--layer', '-l', type=int, default=Z_LAYER, help='Canvas layer (0-15)')
    parser.add_argument('--time', '-t', type=int, default=24*60*60, help='How long to run for before exiting (seconds)')
    parser.add_argument('--delay', '-d', type=int, default=DELAY, help='Frame delay in milliseconds')
    parser.add_argument('--color', '-c', type=str, default='00ff00', 
                       help='Matrix color in RRGGBB hex format or "random" for random colors (default: green 00ff00)')
    parser.add_argument('--density', type=float, default=1.0/NUM_DOTS, 
                       help=f'Density of raindrops (0.0-1.0, default: 1/{NUM_DOTS})')
    
    args = parser.parse_args()
    
    # Parse the matrix color
    matrix_color = DEFAULT_MATRIX_COLOR
    is_random_color = False
    
    if args.color == "random":
        is_random_color = True
        matrix_color = "random"
    elif args.color and len(args.color) == 6:
        try:
            r = int(args.color[0:2], 16)
            g = int(args.color[2:4], 16)
            b = int(args.color[4:6], 16)
            matrix_color = (r, g, b)
        except ValueError:
            print(f"Invalid color format: {args.color}. Using default green.")
    
    # Set up the color palette (can change during runtime)
    def update_palette(color):
        # Colors from 0 to 240: main gradient from black to matrix color
        if color == "random":
            # For random color mode, we don't need a palette
            return []
            
        palette = []
        bg_color = (0, 0, 0)  # Background is always black
        
        palette.extend(color_gradient(0, 240, bg_color[0], bg_color[1], bg_color[2], 
                                     color[0], color[1], color[2]))
        
        # Colors from 241 to 254: gradient from matrix color to white (for the glow effect)
        palette.extend(color_gradient(241, 254, 
                                     color[0], color[1], color[2],
                                     255, 255, 255))
        
        # Add pure white for the leading edge
        palette.append((255, 255, 255))
        
        return palette
    
    # Initialize the display
    ft = flaschen_np.FlaschenNP(args.host, args.port, args.width, args.height, args.layer)
    ft.zero()  # Clear the display
    
    # Active raindrops
    raindrops = []
    
    # Estimate a good number of initial raindrops based on screen size and density
    max_raindrops = int(args.width * args.height * args.density / 20)
    
    # Main loop
    start_time = time.time()
    frame_count = 0
    last_color_check = time.time()
    
    try:
        while not interrupt_received and (time.time() - start_time) <= args.time:
            # Check for color changes every second
            if time.time() - last_color_check > 1.0:
                new_color = check_color_change(matrix_color)
                if new_color != matrix_color:
                    matrix_color = new_color
                    is_random_color = (matrix_color == "random")
                last_color_check = time.time()
            
            # Clear the display for this frame
            ft.zero()
            
            # Randomly add new raindrops
            if frame_count % 4 == 0:  # Add drops every 4 frames like C++ version
                # Add a specific number of drops at random positions
                if random.random() < 0.5:  # 50% chance of adding a drop
                    x = random.randint(0, args.width - 1)
                    if is_random_color:
                        raindrops.append(MatrixRaindrop(x, args.height, color="random"))
                    else:
                        raindrops.append(MatrixRaindrop(x, args.height, color=matrix_color))
                
                # For wider displays, occasionally add a second drop in the same frame
                if args.width > 100 and random.random() < 0.3:  # 30% chance for second drop on wide displays
                    x = random.randint(0, args.width - 1)
                    if is_random_color:
                        raindrops.append(MatrixRaindrop(x, args.height, color="random"))
                    else:
                        raindrops.append(MatrixRaindrop(x, args.height, color=matrix_color))
            
            # Update each raindrop
            new_raindrops = []
            for drop in raindrops:
                if drop.update():  # If still active
                    # Draw the raindrop
                    for i in range(drop.length):
                        y = drop.y - i
                        if 0 <= y < args.height:
                            # Calculate brightness for this part of the trail
                            # Head is brightest, tail fades out
                            brightness = max(0, 255 - (i * FADE_STEP))
                            
                            # Apply the color based on brightness
                            if getattr(drop, 'color', None) is not None:
                                # Random color mode - use drop's specific color
                                base_color = drop.color
                                if brightness == 255:
                                    # Head is always white
                                    color = (255, 255, 255)
                                else:
                                    # Calculate the color based on brightness
                                    ratio = brightness / 255.0
                                    r = int(base_color[0] * ratio)
                                    g = int(base_color[1] * ratio)
                                    b = int(base_color[2] * ratio)
                                    color = (r, g, b)
                                ft.set(drop.x, y, color)
                            else:
                                # This shouldn't happen with our updated code
                                # But keeping as a fallback
                                palette = update_palette(matrix_color)
                                if palette:
                                    ft.set(drop.x, y, palette[brightness])
                                else:
                                    # Fallback for random mode
                                    ratio = brightness / 255.0
                                    color = (int(0 * ratio), int(255 * ratio), int(0 * ratio))
                                    ft.set(drop.x, y, color)
                    
                    # Keep active raindrops
                    new_raindrops.append(drop)
            
            # Update the active raindrops list
            raindrops = new_raindrops
            
            # Send the frame
            ft.send()
            
            # Sleep to control the frame rate
            time.sleep(args.delay / 1000.0)
            
            frame_count += 1
            if frame_count >= 10000:  # Reset to avoid overflow
                frame_count = 0
    
    finally:
        # Clear the display on exit
        ft.zero()
        ft.send()
        print("\nMatrix effect stopped.")
    
    return 0 if not interrupt_received else 1

if __name__ == '__main__':
    sys.exit(main()) 