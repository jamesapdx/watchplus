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
        # state: 0=no change, 1=change
        self.frame_state = [0]
        self.heatmap = [""]
        self.heatmap_pointer = [1]
        # state: 0=no change, 1=change
        self.heatmap_state = [0]
        self.heatmap_ignore = [0]

        self.v_position = 0
        self.h_postion = 0

    def frame_generator(self):
        self.frame.append([])
        self.frame_state.append(0)
        new_pointer = len(self.frame) - 1

        result, error = run_linux("dmesg")
        #result = "abcdefg"
        result = str(timeit.default_timer())
        result = (result.strip("\n") + ("adf" * 60) + str("\n")) * 600

        frame = result.splitlines()
        last_frame = self.frame[self.frame_pointer[new_pointer - 1]]

        if new_pointer == 1:
            self.frame[new_pointer] = frame
            self.frame_pointer.append(1)
            self.frame_state[new_pointer] = 0
        elif frame == last_frame:
            self.frame_pointer.append(self.frame_pointer[new_pointer - 1])
            self.frame_state[new_pointer] = 0
        else:
            self.frame[new_pointer] = frame
            self.frame_pointer.append(new_pointer)
            self.frame_state[new_pointer] = 1

    def heatmap_generator(self, ignore=None):
        new_pointer = len(self.frame) - 1
        self.heatmap.append([])
        self.heatmap_state.append(0)
        self.heatmap_ignore.append(0)

        frame = self.frame[new_pointer]

        if new_pointer == 1:
            # first frame, so build a new heatmap of all 0s
            self.heatmap_pointer.append(1)
            for counter in range(len(frame)):
                self.heatmap[new_pointer].append(len(frame[counter]) * "0")
        elif self.frame_state[new_pointer] == 0 and self.heatmap_state[new_pointer - 1] == 0:
            # appears nothing has changed and no cooldown needed, so simply point to the prior heatmap
            self.heatmap_pointer.append(self.heatmap_pointer[new_pointer -1])
        elif ignore is True:
            # set to ignore this frame, so point to the prior heatmap
            self.heatmap_ignore[new_pointer] = 0
            self.heatmap_pointer.append(self.heatmap_pointer[new_pointer -1])
        else:
            # this frame is different than the last, so make a new heatmap just for the lines that are different
            self.heatmap_pointer.append(new_pointer)

            last_frame =   self.frame[  self.frame_pointer[new_pointer - 1]]
            last_heatmap = self.heatmap[self.heatmap_pointer[new_pointer - 1]]

            max_lines = max(len(last_heatmap), len(frame), len(last_frame))

            # make all items the same length for ease of processing
            frame = frame + ([""] * (max_lines - len(frame)))
            last_frame = last_frame + ([""] * (max_lines - len(last_frame)))
            last_heatmap = last_heatmap + ([""] * (max_lines - len(last_heatmap)))

            # start line by line comparison
            for line in range(max_lines):

                frame_line = frame[line]
                last_frame_line = last_frame[line]
                heatmap_line = last_heatmap[line]
                last_heatmap_line = last_heatmap[line]

                # if this line is different, do a char by char comparison
                if frame_line != last_frame_line:
                    max_char = max(len(frame_line), len(last_frame_line), len(last_heatmap_line))

                    # make all variables of the current line the same length for ease of processing
                    frame_line = frame_line + (" " * (max_char - len(frame_line)))
                    last_frame_line = last_frame_line + (" " * (max_char - len(last_frame_line)))
                    heatmap_line = heatmap_line + ("0" * (max_char - len(last_heatmap_line)))

                    # perform a char by char comparison and mark hot if different
                    heatmap_line = ""
                    for counter in range(max_char):
                        if frame_line[counter] != last_frame_line[counter]:
                            heatmap_line = heatmap_line + str(self.cooldown_ticks + 2)
                        else:
                            heatmap_line = heatmap_line + last_heatmap_line[counter]

                # cooldown any heatmap char that is greater than 1
                if int(max(heatmap_line)) > 1:
                    self.heatmap_state[new_pointer] = 1
                    for cooldown in range(2, self.cooldown_ticks + 3, 1):
                        heatmap_line = heatmap_line.replace(str(cooldown),str(cooldown - 1))

                # write the new heatmap for this frame
                self.heatmap[new_pointer].append(heatmap_line)
        n = ""

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
    iterations = 300
    error = False
    start = timeit.default_timer()
    for y in range(iterations):
        ignore = True if y == 0 else False
        x.frame_generator()
        x.heatmap_generator()

    stop = timeit.default_timer()
    diff = start - stop

    #x.display_frame()
except:
    error = True
    terminate_curses()
    raise

if curses.isendwin() is not True:
    terminate_curses()

