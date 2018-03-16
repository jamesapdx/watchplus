#!/usr/bin/python

import curses, sys, os, time, subprocess
import timeit
import gc

def run_linux(cmd):
    result, err = subprocess.Popen(
                                cmd.split(" "),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE
                                ).communicate()
    return result.decode("utf-8"), err

class Windows():
    master_windows = []

    def __init__(self, window, cmd, current_time):
        self.window = window
        self.cmd = cmd
        self.creation_time = current_time
        self.window_lines = []
        self.window_columns = []
        self.ticks_per_iter = 1
        self.cooldown_ticks = 4
        self.history_min = 1

        self.frame = [""]
        self.frame_pointer = [1]
        self.frame_state = [0]
        self.heatmap = [""]
        self.heatmap_pointer = [1]
        self.heatmap_state = [0]

        self.v_position = 0
        self.h_postion = 0

    def frame_generator(self):
        self.frame.append([])
        self.frame_state.append(0)
        new_pointer = len(self.frame) - 1

        result, error = run_linux("dmesg")
        #result = str(timeit.default_timer())
        #result = (result.strip("\n") + ("adf" * 60) + str("\n")) * 600

        frame = result.splitlines()
        last_frame =   self.frame[  self.frame_pointer[new_pointer - 1]]

        if new_pointer == 1:
            self.frame[new_pointer] = frame
            self.frame_pointer.append(1)
        elif frame == last_frame:
            self.frame_pointer.append(self.frame_pointer[new_pointer - 1])
            self.frame_state = 1

        self.frame[new_pointer] = frame

    def heatmap_generator(self, ignore=False):

        new_pointer = len(self.frame) - 1
        self.heatmap.append([])

        # make local variables for the current frame, heatmap, last frame, and last heatmap
        # save them to the actual class arrays (self.frame etc) at the end.  this is much easier to work with
        # frame is a list, each list item is a line of text to be displayed
        # heatmap is a list, each list item is a line of text containing the heatmap values
        frame = self.frame[new_pointer]
        frame_length = len(frame)
        last_frame =   self.frame[  self.frame_pointer[new_pointer - 1]]
        last_heatmap = self.heatmap[self.heatmap_pointer[new_pointer - 1]]

        if new_pointer == 1:
            self.heatmap_pointer.append(1)
            for counter in range(len(frame)):
                self.heatmap[new_pointer].append(len(frame[counter]) * "0")
        elif self.frame_state == 1 and self.heatmap_pointer[new_pointer - 1] == self.heatmap_pointer[new_pointer - 2]):
            self.heatmap_pointer.append(self.heatmap_pointer[new_pointer -1])
            ### stopped here
        elif ignore is True:
            self.heatmap_pointer.append(self.heatmap_pointer[new_pointer -1])
        else:
            self.frame_pointer.append(new_pointer)
            self.heatmap_pointer.append(new_pointer)

            last_frame_length = len(last_frame)
            last_heatmap_length = len(last_heatmap)

            # make all lists the same length for ease of processing when comparing current with previous
            # preserve length variables to strip unnecessary lines at the end
            max_lines = max(last_heatmap_length, frame_length)

            for line in range(max_lines):

                frame_line = frame[line]
                last_frame_line = last_frame[line]

                # if there is no change from the last iteration, just point to the last iteration
                if frame_line == last_frame_line:
                    last_heatmap_line = last_heatmap[line]
                    # set the new frame equal to the last frame
                    self.frame[new_pointer].append(self.frame[new_pointer - 1][line])
                    # set heatmap to the last heatmap
                    self.heatmap[new_pointer].append(self.heatmap[new_pointer - 1][line])
                    if int(max(last_heatmap_line)) > 1:
                        # cooldown calculation needed, loop through levels and reduce by one
                        for cooldown in range(self.cooldown_ticks + 1, 2, -1):
                            self.heatmap[new_pointer][line] = last_heatmap_line.replace(str(cooldown),str(cooldown - 1))
                else:
                    # make all variables of the current line the same length for ease of processing
                    frame_line_length = len(frame[line])
                    last_frame_line_length = len(last_frame[line])
                    last_heatmap_line_length = len(last_heatmap[line])

                    max_char = max(frame_line_length, last_frame_line_length, last_heatmap_length)

                    frame_line = frame[line].rstrip("\n") + (" " * (max_char - frame_line_length + 0))
                    last_frame_line = last_frame[line] + (" " * (max_char - last_frame_line_length + 0))
                    last_heatmap_line = last_heatmap[line] + ("0" * (max_char - last_heatmap_line_length + 0))

                    # something is different on this line, so go through char by char
                    heatmap_line = ""
                    for char in range(max_char):
                        if frame_line[char] != last_frame_line[char]:
                            # this char is different than last time, set heatmap char to max cooldown
                            heatmap_line = heatmap_line + str(self.cooldown_ticks + 1)
                        else:
                            if int(last_heatmap_line[char]) == 0 or int(last_heatmap_line[char]) == 1 :
                                # if heatmap char is 0 or 1 no change needed, just add
                                heatmap_line = heatmap_line + last_heatmap_line[char]
                            else:
                                # heatmap char must be in cooldown, so subtract 1
                                heatmap_line = heatmap_line + str(int(last_heatmap_line[char]) - 1)
                    self.frame[new_pointer].append(frame_line.rstrip(" "))
                    self.heatmap[new_pointer].append(heatmap_line.rstrip("0"))

def terminate_curses():
    curses.echo()
    curses.nocbreak()
    curses.curs_set(1)
    curses.endwin()
    if error is False:
        print("{0} iterations, start:{1:.3f} stop:{2:.3f} diff:{3:.3f})".format(
            iterations,
            start,
            stop,
            diff))

stdscr = curses.initscr()
curses.noecho()
curses.cbreak()
curses.curs_set(0)
curses.start_color()
stdscr.keypad(True)

try:
    x = Windows(stdscr, "date", 0)

    counter = 1
    iterations = 2000
    error = False
    start = timeit.default_timer()
    for y in range(iterations):
        ignore = True if y == 0 else False
        x.frame_generator()

    stop = timeit.default_timer()
    diff = start - stop

    #x.display_frame()
except:
    error = True
    terminate_curses()
    raise

if curses.isendwin() is not True:
    terminate_curses()

