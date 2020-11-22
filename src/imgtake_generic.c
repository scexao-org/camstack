# Add CLI opt -816 -- triggers a casting from 8bit full size to 16bit half size
# This will require magic in 

# Also, add a CLI option to ocamdecode for forward and reverse modes
# the reverse mode is gonna be 2x faster on a full frame but pretty poor on slices, as we'll have to do full passes every time.
# Or maaaaaybe we could compute a reduced forward mode with only the useful parts ? As to make it AS FAST as a reverse lookup.
