# -*- mode: python; c-basic-offset: 2; indent-tabs-mode: nil; -*-
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation version 2.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://gnu.org/licenses/gpl-2.0.txt>

import socket
import numpy as np
import math

class FlaschenNP(object):
  '''A Framebuffer display interface that sends a frame via UDP.

  JBY: modified to use numpy as storage backend.'''

  # Maximum UDP packet size (safe value)
  MAX_UDP_PACKET = 65507

  def __init__(self, host, port, width, height, layer=0, transparent=False):
    '''

    Args:
      host: The flaschen taschen server hostname or ip address.
      port: The flaschen taschen server port number.
      width: The width of the flaschen taschen display in pixels.
      height: The height of the flaschen taschen display in pixels.
      layer: The layer of the flaschen taschen display to write to.
      transparent: If true, black(0, 0, 0) will be transparent and show the layer below.
    '''
    self.width = width
    self.height = height
    self.layer = layer
    self.transparent = transparent
    self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self._sock.connect((host, port))
    header = ''.join(["P6\n",
                      "%d %d\n" % (self.width, self.height),
                      "255\n"])
    footer = ''.join(["0\n",
                      "0\n",
                      "%d\n" % self.layer])
    self._bytedata = bytearray(width * height * 3 + len(header) + len(footer))
    self._bytedata[0:len(header)] = str.encode(header)
    self._bytedata[-1 * len(footer):] = str.encode(footer)
    self.data = np.zeros((height, width, 3), 'uint8')
    self._header_len = len(header)
    self._footer_len = len(footer)
    self._buffer_size = len(self._bytedata)

  def set(self, x, y, color):
    '''Set the pixel at the given coordinates to the specified color.

    Args:
      x: x offset of the pixel to set
      y: y offset of the piyel to set
      color: A 3 tuple of (r, g, b) color values, 0-255
    '''
    if x >= self.width or y >= self.height or x < 0 or y < 0:
      return
    if color == (0, 0, 0) and not self.transparent:
      color = (1, 1, 1)

    #offset = (x + y * self.width) * 3 + self._header_len
    #self._data[offset] = color[0]
    #self._data[offset + 1] = color[1]
    #self._data[offset + 2] = color[2]
    self.data[y, x, 0] = color[0]
    self.data[y, x, 1] = color[1]
    self.data[y, x, 2] = color[2]

  def ijset(self, ii, jj, color):
    return self.set(jj, ii, color)

  def zero(self):
    self.data[:] = 0
  
  def send(self):
    '''Send the updated pixels to the display.
    
    For large images, this breaks the image into tiles that fit within 
    the maximum UDP packet size and sends each tile individually with the
    correct offset.
    '''
    # Check if we need to tile the image
    if self._buffer_size > self.MAX_UDP_PACKET:
      # Calculate the max tile size that can fit in a UDP packet
      pixels_per_packet = (self.MAX_UDP_PACKET - self._header_len - self._footer_len) // 3
      
      # Calculate optimal tile dimensions
      tile_height = min(self.height, int(math.sqrt(pixels_per_packet)))
      tile_width = min(self.width, pixels_per_packet // tile_height)
      
      # If we can't fit even one row, reduce height
      if tile_width < 1:
        tile_width = 1
        tile_height = min(self.height, pixels_per_packet)
      
      # Send tiles
      for y_offset in range(0, self.height, tile_height):
        for x_offset in range(0, self.width, tile_width):
          # Calculate the current tile dimensions
          current_tile_width = min(tile_width, self.width - x_offset)
          current_tile_height = min(tile_height, self.height - y_offset)
          
          # Create a header for this tile
          tile_header = ''.join(["P6\n",
                               "%d %d\n" % (current_tile_width, current_tile_height),
                               "255\n"])
          
          # Create a footer with the offset
          tile_footer = ''.join(["%d\n" % x_offset,
                              "%d\n" % y_offset,
                              "%d\n" % self.layer])
          
          # Create the tile data
          tile_data = bytearray(current_tile_width * current_tile_height * 3 + len(tile_header) + len(tile_footer))
          tile_data[0:len(tile_header)] = str.encode(tile_header)
          tile_data[-1 * len(tile_footer):] = str.encode(tile_footer)
          
          # Extract the relevant portion of the image
          tile_image = self.data[y_offset:y_offset + current_tile_height, 
                                x_offset:x_offset + current_tile_width, :]
          
          # Copy the tile image data into the buffer
          tile_bytes = tile_image.tobytes()
          tile_data[len(tile_header):len(tile_header) + len(tile_bytes)] = tile_bytes
          
          # Send the tile
          self._sock.send(tile_data)
    else:
      # Send the entire image in one packet
      self._bytedata[self._header_len:self._header_len + self.data.nbytes] = self.data.tobytes()
      self._sock.send(self._bytedata)

