#!/bin/bash
# Script to start Matrix web server as a background process that will persist after SSH session ends

# Change to the correct directory
cd /home/raspiled/ft-demos

# Kill any previous instances
sudo pkill -f "python3 matrix_web_controller.py" || true

# Start the server with nohup to keep it running after SSH session ends
# Redirect output to a log file
sudo nohup python3 matrix_web_controller.py > matrix_web.log 2>&1 &

# Output success message
echo "Matrix web server started at http://192.168.86.56"
echo "Log file: matrix_web.log" 