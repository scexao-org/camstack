# Will this remain useful??

import os
_CORES = os.sched_getaffinity(0) # AMD fix
import pygame.event
import pygame.font
import pygame.constants as pgm_ct
os.sched_setaffinity(0, _CORES) # AMD fix

# COLORS
WHITE = (255, 255, 255)
GREEN = (147, 181, 44)
BLUE = (0, 0, 255)
RED = (246, 133, 101)  #(185,  95, 196)
RED1 = (255, 0, 0)
BLK = (0, 0, 0)
CYAN = (0, 255, 255)

FGD_COL = WHITE  # foreground color (text)
SAT_COL = RED1  # saturation color (text)
BGD_COL = BLK  # background color
BUT_COL = BLUE  # button color

def gen_zoomed_fonts(system_zoom: int):
    return [
        pygame.font.SysFont("default", 20 * system_zoom),
        pygame.font.SysFont("default", 14 * system_zoom),
        pygame.font.SysFont("monospace", 5 * (system_zoom + 1)),
        pygame.font.SysFont("monospace", 7 + 3 * system_zoom),
        pygame.font.SysFont("monospace", 7 + 3 * system_zoom, bold=True)
    ]