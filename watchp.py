#!/usr/bin/python
# -*- encoding: utf8 -*-

import curses, sys, os, time, subprocess
import timeit
import gc

def run_linux(cmd):
    result, err = subprocess.Popen(
                                cmd.split(" "),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE
                                ).communicate()
    return result, err
    #return result.decode("utf-8"), err

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

        self.frame = [""]
        # use a pointer to point back to frames that are equal, prevents storage increase
        self.frame_pointer = [1]
        # state: 0=no change, 1=change, used for fast comparison of new frames
        self.frame_state = [0]
        self.heatmap = [""]
        self.heatmap_pointer = [1]
        # state: 0=no change, 1=change, used for fast comparison of new frames
        self.heatmap_state = [0]
        self.heatmap_ignore = [0]

        self.v_position = 0
        self.h_postion = 0

    def frame_generator(self, test_case=None):
        """ create a new frame. a frame is composed of a line by line list of the output from
            the assigned command for this window """
        # init variables and add new list items
        self.frame.append([])
        self.frame_state.append(0)
        new_pointer = len(self.frame) - 1
        test_case = 1

        # process desired command for this window
        result, error = run_linux("dmesg")

        # alternate test cases:
        if test_case == 1:
            result = "abcdefgxyz abc \n123456\n7890 !@#$&^"

        if test_case == 2:
            result = str(timeit.default_timer())
        if test_case == 3:
            result = str(timeit.default_timer())
            result = (result.strip("\n") + ("adf" * 60) + str("\n")) * 600
        # break it into a line by line list
        frame = result.splitlines()
        last_frame = self.frame[self.frame_pointer[new_pointer - 1]]

        if new_pointer == 1:
            # first time run, store it in the main list
            self.frame[new_pointer] = frame
            self.frame_pointer.append(1)
            self.frame_state[new_pointer] = 0
        elif frame == last_frame:
            # no change from last one, set the pointer to the last frame
            self.frame_pointer.append(self.frame_pointer[new_pointer - 1])
            self.frame_state[new_pointer] = 0
        else:
            # frame is different then the last one, store it in the main list
            self.frame[new_pointer] = frame
            self.frame_pointer.append(new_pointer)
            self.frame_state[new_pointer] = 1
        n = ""

    def heatmap_generator(self, ignore=None):
        """ create a new heatmap frame. a heatmap frame is composed of a line by line list of digits indicating the
            difference between each character in this frame versus the last frame.
                0  = no change ever
                1  = changed at some point in the past
                >1 = recent change, will "cooldown" by 1 with with each new frame till it reaches 1
                """
        # init variables and add new list items
        new_pointer = len(self.frame) - 1
        self.heatmap.append([])
        self.heatmap_state.append(0)
        self.heatmap_ignore.append(0)

        frame = ['','']
        heatmap = ['','']

        frame[0] = self.frame[self.frame_pointer[new_pointer]]
        frame[-1] = self.frame[self.frame_pointer[new_pointer - 1]]
        heatmap[-1] = self.heatmap[self.heatmap_pointer[new_pointer - 1]]

        if new_pointer == 1:
            # first frame, so build a new heatmap of all 0s
            self.heatmap_pointer.append(1)
            for counter in range(len(frame[0])):
                self.heatmap[new_pointer].append(len(frame[0][counter]) * "0")
        elif self.frame_state[new_pointer] == 0 and self.heatmap_state[new_pointer - 1] == 0:
            # appears nothing has changed and no cooldown needed, so simply point to the prior heatmap
            self.heatmap_pointer.append(self.heatmap_pointer[new_pointer -1])
        elif ignore is True:
            # set to ignore any changes on this frame, so point to the prior heatmap
            self.heatmap_ignore[new_pointer] = 0
            self.heatmap_pointer.append(self.heatmap_pointer[new_pointer -1])
        else:
            # this frame is different than the last, so make a new heatmap just for the lines that are different
            self.heatmap_pointer.append(new_pointer)

            frame[0], frame[-1], heatmap[-1], max_lines = self.equalize_lengths(
                            [""], frame[0], frame[-1], heatmap[-1])

            # start line by line comparison
            for line in range(max_lines):

                # if this line is different, do a char by char comparison
                if frame[0][line] != frame[-1][line]:
                    # get max length of this fame line, last frame line, last heatmap_line
                    frame[0][line], frame[-1][line], heatmap[-1][line], max_char = self.equalize_lengths(
                                " ", frame[0][line], frame[-1][line], heatmap[-1][line])
                    heatmap[-1][line] = heatmap[-1][line].replace(" ","0")

                    # perform a char by char comparison to the last frame and mark hot if different
                    heatmap[line] = ""
                    for column in range(max_char):
                        if frame[0][line][column] != frame[-1][line][column]:
                            heatmap[line] = heatmap[line] + str(self.cooldown_ticks + 2)
                        else:
                            heatmap[line] += heatmap[-1][line][column]

                # cooldown by 1 any heatmap char that is greater than 1
                if int(max(heatmap[line])) > 1:
                    self.heatmap_state[new_pointer] = 1
                    for cooldown in range(2, self.cooldown_ticks + 3, 1):
                        heatmap[line] = heatmap[line].replace(str(cooldown),str(cooldown - 1))

                # save the new heatmap for this frame to the main heatmap list
                self.heatmap[new_pointer].append(heatmap[line])

    def equalize_lengths(self, adder, *args):
        lengths = [len(value) for value in args]
        max_length = max(lengths)
        values = [value + (adder * (max_length - length)) for length, value in zip(lengths, args) ]
        values.append(max_length)
        return values

    def draw_frame(self, height, width, refresh=None, pointer=None):
        # need draw size, upper left position, last window type
        # extra features: draw receding lines

        self.window.erase()

        if pointer == None:
            pointer = len(self.frame) - 1

        frame = self.frame[self.frame_pointer[pointer]]
        heatmap = self.heatmap[self.heatmap_pointer[pointer]]
        l_frame = len(frame)
        l_heatmap = len(heatmap)

        max_lines = max(l_heatmap, l_frame)
        draw_height = min(max_lines, height)

        for row in range(draw_height - 1):
            frame_line = frame[row]
            heatmap_line = heatmap[row]
            l_frame_line = len(frame_line)
            l_heatmap_line = len(heatmap_line)

            max_char = max(l_frame_line, l_heatmap_line)
            draw_width = min(max_char, width)

            for column in range(draw_width - 1):
                a = frame_line[column]
                self.window.addch(row, column, a )

        self.window.refresh()

        #time.sleep(.1)



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
        print(stdscr)

stdscr = curses.initscr()
curses.noecho()
curses.cbreak()
curses.curs_set(0)
curses.start_color()
stdscr.keypad(True)


try:
    x = Windows(stdscr, "date", 0)

    counter = 1
    iterations = 1500
    error = False
    start = timeit.default_timer()
    for y in range(iterations):
        ignore = True if y == 0 else False
        x.frame_generator()
        x.heatmap_generator()
        height, width = stdscr.getmaxyx()
        x.draw_frame(height, width)

    stop = timeit.default_timer()
    diff = start - stop

    #x.display_frame()
except:
    error = True
    terminate_curses()
    raise

if curses.isendwin() is not True:
    terminate_curses()

