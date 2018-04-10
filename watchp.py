#!/usr/bin/python3
# -*- encoding: utf8 -*-

import sys
import os
import subprocess
import curses
import time
import multiprocessing

import timeit

def run_linux(cmd):
    result, error = subprocess.Popen(
                                cmd.split(" "),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE
                                ).communicate()
    return result, error

class Windows():
    master_windows = []

    def __init__(self, window, cmd, current_time):
        self.window = window
        self.cmd = cmd
        self.creation_time = current_time
        self.window_lines = []
        self.window_columns = []
        self.ticks_per_iter = 1
        self.cooldown_ticks = None
        self.cooldown_color_map = []
        self.cooldown_color_setup(4)

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

    def cooldown_color_setup(self, cooldown_ticks=4):
        self.cooldown_ticks = cooldown_ticks
        self.cooldown_color_map = [0,1] + ([2] * (cooldown_ticks + 1))

    def frame_generator(self, test_case=None):
        """ create a new frame. a frame is composed of a line by line list of the output from
            the assigned command for this window """
        # init variables and add new list items
        new_pointer = len(self.frame)

        # process desired command for this window

        # alternate test cases:
        test_case = 5
        if test_case == 1:
            result = "abcdefgxyz abc \n123456\n7890 !@#$&^"
        elif test_case == 2:
            result = str(timeit.default_timer())
            time.sleep(.2)
        elif test_case == 3:
            result = str(timeit.default_timer())
            result = (result.strip("\n") + ("adf" * 60) + str("\n")) * 600
        elif test_case == 4:
            result, error = run_linux("date")
        elif test_case == 5:
            result, error = run_linux("./test.sh")
        else:
            result, error = run_linux("dmesg")

        # break result into a line by line list
        try:
            frame = result.decode().splitlines()
        except AttributeError:
            frame = str(result).splitlines()

        if new_pointer == 1:
            # first time run, store it
            self.set_frame(frame=frame, pointer=1, state=0)
        elif frame == self.frame[self.frame_pointer[new_pointer - 1]]:
            # no change from last one, set the pointer to the last frame
            self.set_frame(frame=[], pointer=self.frame_pointer[new_pointer - 1], state=0)
        else:
            # frame is different then the last one, store it
            self.set_frame(frame=frame, pointer=new_pointer, state=1)

    def set_frame(self, frame, pointer, state):
        self.frame.append(frame)
        self.frame_pointer.append(pointer)
        self.frame_state.append(state)

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
        heatmap[0] = heatmap[-1]

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
                    #heatmap[-1][line] = heatmap[-1][line].replace(" ","0")

                    # perform a char by char comparison to the last frame and mark hot if different
                    heatmap[0][line] = ""
                    for column in range(max_char):
                        if frame[0][line][column] != frame[-1][line][column]:
                            # char is different, mark hot
                            heatmap[0][line] += str(self.cooldown_ticks + 2)
                        else:
                            # char is same
                            heatmap[0][line] += heatmap[-1][line][column]

                # cooldown by 1 any heatmap char that is greater than 1
                if int(max(heatmap[0][line])) > 1:
                    self.heatmap_state[new_pointer] = 1
                    for cooldown in range(2, self.cooldown_ticks + 3, 1):
                        heatmap[0][line] = heatmap[0][line].replace(str(cooldown),str(cooldown - 1))

                # save the new heatmap for this frame to the main heatmap list
                self.heatmap[new_pointer].append(heatmap[0][line])

    def equalize_lengths(self, adder, *args):
        lengths = [len(value) for value in args]
        max_length = max(lengths)
        values = [value + (adder * (max_length - length)) for length, value in zip(lengths, args) ]
        values.append(max_length)
        return values

    def draw_frame(self, height, width, refresh=None, pointer=None):
        # need draw size, upper left position, last window type
        # extra features: draw receding lines

        self.window.clear()

        if pointer == None:
            pointer = len(self.frame) - 1

        frame = self.frame[self.frame_pointer[pointer]]
        heatmap = self.heatmap[self.heatmap_pointer[pointer]]
        draw_height = min(len(frame), height - 1)

        for line in range(draw_height):
            frame[line], heatmap[line], max_char = self.equalize_lengths(" ", frame[line], heatmap[line])
            heatmap[line] = heatmap[line].replace(" ","0")

            draw_width = min(max_char, width)

            for column in range(draw_width):
                self.window.addstr(
                        line,        elif test_case == 4:
            result, error = run_linux("date")
                        column,
                        str(frame[line][column]),
                        curses.color_pair(self.cooldown_color_map[int("0" + heatmap[line][column])])
                        )

        self.window.refresh()

# start mulitprocessing

def frame_and_heat():



def curses_color_setup():
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_YELLOW)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_RED)


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


def main():
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    curses.curs_set(0)
    stdscr.keypad(True)

    curses.start_color()
    curses_color_setup()
    start = timeit.default_timer()

    for y in range(iterations):
        ignore = True if y == 0 else False

        istart = timeit.default_timer()

        x.frame_generator()
        x.heatmap_generator()

        height, width = stdscr.getmaxyx()
        x.draw_frame(height, width)

        iend = timeit.default_timer()
        ipause = (1 - (iend - istart) - .001 )
        ipause = 0 if ipause < 0 else ipause
        time.sleep(ipause)


    stop = timeit.default_timer()
    diff = start - stop


### start here


try:
    x = Windows(stdscr, "date", 0)

    counter = 1
    iterations = 300
    error = False

    main()

except:
    error = True
    terminate_curses()
    raise

if curses.isendwin() is not True:
    terminate_curses()

