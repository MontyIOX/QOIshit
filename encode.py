"""
An image encoder following the specification of the Quite Okay Image Format (QOI),
written by Toni Kathert.

https://qoiformat.org/qoi-specification.pdf

Pixels are encoded as:
• a run-length of the previous pixel 
• an index into an array of previously seen pixels
• a difference to the previous pixel value in r,g,b
• full r,g,b values

Ignores alpha values, may be updated to support full transparency in the future
QOI_OP_LUMA for encoder has been omitted for now
decode option will be added
"""

import errno
import sys
import os

from pathlib import Path
from PIL import Image

def index_hash(rgb):
    'Calculates Hash for color index'
    return (rgb[0]*3 + rgb[1]*5 + rgb[2]*7 + 255*11) % 64

def encode (path):

    index = [[0,0,0]] * 64 # Color index

    # open image
    # check if image exists
    if os.path.isfile(path):
        try:
            with Image.open(path) as im:
                pixVals = list(im.getdata())
                height = im.height
                width = im.width
        except IOError as e:
            if e.errno == errno.EACCESS:
                print("Permission Denied.")
                return
            else:
                print(e)
                return
    else:
        print(f"File {path} does not exist.")
        return
        
    # Make binary data for header as per qoif specification
    magic = b"qoif"
    bwidth = width.to_bytes(4, byteorder='big', signed=False)
    bheight = height.to_bytes(4, byteorder='big', signed=False)
    channels = (3).to_bytes(1, byteorder='big', signed=False)    # no Alpha
    colorspace = (0).to_bytes(1, byteorder='big', signed=False)  # assumed sRGB

    # Create output folder if it doesn't exist
    if not os.path.exists("./output"):
        os.mkdir("output")

    try:
        with open(f"./output/{Path(path).stem}.qoi", "wb") as fo:
            
            # write QOI header
            # Python only allows one at a time, for whatever reason
            fo.write(magic)
            fo.write(bwidth)
            fo.write(bheight)
            fo.write(channels)
            fo.write(colorspace)

            last = [0, 0, 0] # Starts with r: 0 g: 0 b: 0 as per specification
            run_counter = 0 # run-length repetition counter
            current = 0 # Pixel counter for progress meter

            for rgb in pixVals:

                index_pos = index_hash(rgb)

                # QOI_OP_RUN - run-length encoding
                # Max runlength is 62. 63 and 64 are occupied by QOI_OP_RGB and QOI_OP_RGBA tags respectively
                if last[0] == rgb[0] and last[1] == rgb[1] and last[2] == rgb[2] and run_counter < 62:
                    run_counter += 1
                    current += 1
                    continue

                # Write runlength if pixel repetition ends
                if run_counter > 0:
                    # binary 192 = 1100 0000 (QOI_OP_RUN tag)
                    fo.write((192 | (run_counter - 1)).to_bytes(1, byteorder='big', signed=False)) 
                    run_counter = 0
                
                # QOI_OP_INDEX
                # Both encoder and decoder keep a running array[64] of prev. seen colors
                if not rgb == index[index_pos]:
                    # If color is not in index, add it. 
                    index[index_pos] = rgb
                else:
                    # Write index position to file
                    fo.write(index_pos.to_bytes(1, byteorder='big', signed=False))
                    last = rgb
                    current += 1
                    continue

                # QOI_OP_DIFF
                # Check if channel difference is within range of specification (-2..1)
                dr = rgb[0] - last[0]
                dg = rgb[1] - last[1]
                db = rgb[2] - last[2]

                if ( dr < 2 and dr > -3 and 
                     dg < 2 and dg > -3 and
                     db < 2 and db > -3 ):
                    # Bitshifting to line up the difference values
                    # Eight bits, first are 01 (64 = 01000000) dr = 000000xx is shifted by four bits to 00xx0000 and so on
                    # Difference has a bias of two, so we add two to each value
                    fo.write((64 | dr + 2 << 4 | dg + 2 << 2 | db + 2).to_bytes(1, byteorder='big', signed=False))
                    last = rgb
                    current += 1
                    continue

                # QOI_OP_RGB if all else fails
                # Write RBG tag followed by raw color values
                fo.write((254).to_bytes(1, byteorder='big', signed=False))
                fo.write(rgb[0].to_bytes(1, byteorder='big', signed=False))
                fo.write(rgb[1].to_bytes(1, byteorder='big', signed=False))
                fo.write(rgb[2].to_bytes(1, byteorder='big', signed=False))
                last = rgb

                # Print progress. End parameter important for writing over previous line
                current += 1
                max = width * height
                prog = round(current / max * 100)  # Progress in %

                print (f"Encoding {path}... {prog}%", end="\r")

            # End bytestream with 7 0x00 and 1 0x01 bytes as per specification
            fo.write(bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01]))

            # Prevents new progress meter from overwriting old one when encoding multiple files
            print("") 

    except Exception as e:
        # Never encountered an error here, but just in case.
        # Open filestreams are errors waiting to happen
        print(f"An unexpected error occoured: {e.message}")

# Remove first item of argv because it contains name of this file
del sys.argv[0]

if not sys.argv:
    print("Please specify one or more image files to encode.")
    sys.exit()

# Minimal Help
if sys.argv[0].lower() == "help":
    print("Usage: python encode.py <files>")
    sys.exit()
    
for e in sys.argv:
    encode(e)