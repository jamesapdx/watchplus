#!/usr/bin/python3
# -*- encoding: utf8 -*-

import sys
import os
import subprocess
import curses
import time
import multiprocessing
import timeit


class Testing():
    iterations = None
    start = None
    pause = None
    stop = None
    diff = None
    total_watches = None

class Generators():

    def __init__(self, cmd, current_time):
        self.cmd = cmd
        self.creation_time = current_time
        self.ticks_per_iter = 1
        self.cooldown_ticks = None
        self.cooldown_color_map = []
        self.cooldown_color_setup(4)

        self.frame = [[],[]]
        # state: 0=no change, 1=change, used for fast comparison of new frames
        self.frame_state = [0,0]
        self.heatmap = [[],[]]
        # state: 0=no change, 1=change, used for fast comparison of new frames
        self.heatmap_state = [0,0]
        # state: 0=no ignore, 1=ignore
        self.heatmap_ignore = [0,0]

    def cooldown_color_setup(self, cooldown_ticks=4):
        self.cooldown_ticks = cooldown_ticks
        self.cooldown_color_map = [0,1] + ([2] * (cooldown_ticks + 1))

    def test_case(self, test_number):
        # alternate test cases:
        test_case = test_number
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
        return result

    def runner(self):
        test_number = 1
        first_run = True
        current_pointer = 0
        last_pointer = 1

        while True:
           self.frame_generator(test_number, first_run, current_pointer, last_pointer)
           self.heatmap_generator(first_run, current_pointer, last_pointer)

    def frame_generator(self, test_number, first_run, current_pointer, last_pointer ):
        """ create a new frame. a frame is composed of a line by line list of the output from
            the assigned command for this window """

        # process desired command for this window
        result = self.test_case(test_number)

        # break result into a line by line list
        try:
            self.frame[current_pointer] = result.decode().splitlines()
        except AttributeError:
            self.frame[current_pointer] = str(result).splitlines()

        if first_run is True:
            # first time run, store it
            self.frame_state[current_pointer] = 0
        elif self.frame[current_pointer] == self.frame[last_pointer]:
            # no change from last one, set the pointer to the last frame
            self.frame_state[current_pointer] = 0
        else:
            # frame is different then the last one, store it
            self.frame_state[current_pointer] = 1

    def heatmap_generator(self, first_run, current_pointer, last_pointer, ignore=None):
        """ create a new heatmap frame. a heatmap frame is composed of a line by line list of digits indicating the
            difference between each character in this frame versus the last frame.
                0  = no change ever
                1  = changed at some point in the past
                >1 = recent change, will "cooldown" by 1 with with each new frame till it reaches 1
                """
        self.heatmap_state[current_pointer] = 0
        self.heatmap_ignore[current_pointer] = 0

        if first_run is True:
            # first frame, so build a new heatmap of all 0s
            for counter in range(len(self.frame[current_pointer])):
                self.heatmap[current_pointer] = len(self.frame[current_pointer]) * "0"
        elif self.frame_state[current_pointer] == 0 and self.heatmap_state[last_pointer] == 0:
            # appears nothing has changed and no cooldown needed, so simply point to the prior heatmap
            self.heatmap[current_pointer] = self.heatmap[last_pointer]
        elif ignore is True:
            # set to ignore any changes on this frame, so point to the prior heatmap
            self.heatmap_ignore[current_pointer] = 1
            self.heatmap[current_pointer] = self.heatmap[last_pointer]
        else:
            # this frame is different than the last, so make a new heatmap just for the lines that are different

            frame = [[], []]
            heatmap = [[], []]

            frame[0], frame[-1], heatmap[-1], max_lines = self.equalize_lengths(
                [""], self.frame[current_pointer], self.frame[last_pointer], self.heatmap[last_pointer])

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
                    self.heatmap_state[current_pointer] = 1
                    for cooldown in range(2, self.cooldown_ticks + 3, 1):
                        heatmap[0][line] = heatmap[0][line].replace(str(cooldown),str(cooldown - 1))

                # save the new heatmap for this frame to the main heatmap list
                self.heatmap[current_pointer].append(heatmap[0][line])

    def equalize_lengths(self, adder, *args):
        lengths = [len(value) for value in args]
        max_length = max(lengths)
        values = [value + (adder * (max_length - length)) for length, value in zip(lengths, args) ]
        values.append(max_length)
        return values

def draw_frame(window, frame, heatmap, height, width, refresh=None, pointer=None):

    window.clear()

    if pointer == None:
        pointer = len(self.frame) - 1

    draw_height = min(len(frame), height - 1)

    for line in range(draw_height):
        frame[line], heatmap[line], max_char = self.equalize_lengths(" ", frame[line], heatmap[line])
        heatmap[line] = heatmap[line].replace(" ","0")

        draw_width = min(max_char, width)

        for column in range(draw_width):
            self.window.addstr(
                line,
                column,
                str(frame[line][column]),
                curses.color_pair(self.cooldown_color_map[int("0" + heatmap[line][column])])
            )

    window.refresh()


def run_linux(cmd):
    result, error = subprocess.Popen(
        cmd.split(" "),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    ).communicate()
    return result, error


def curses_color_setup():
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_YELLOW)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_RED)


def start_curses()
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    curses.curs_set(0)
    stdscr.keypad(True)
    return stdscr


def terminate_curses():
    curses.echo()
    curses.nocbreak()
    curses.curs_set(1)
    curses.endwin()
    if error is False:
        print("{0} iterations, start:{1:.3f} stop:{2:.3f} diff:{3:.3f})".format(
            Testing.iterations,
            Testing.start,
            Testing.stop,
            Testing.diff))

def get_key(stdscr):
    keystroke = stdscr.getch()
    return chr(keystroke)

def process_key(keystroke):
    done = False
    while not done:
        keystroke = get_key(stdscr)
        if keystroke == "1":
            draw_id.value = 1
        elif keystroke == "2":
            draw_id.value = 2
        elif keystroke == "q":
            p1.terminate()
            p2.terminate()
            done = True
            #sys.exit()
        time.sleep(.1)
    pass

class Watches():

    def __init__(self):
        self.cmd = cmd
        self.creation_time = current_time
        self.ticks_per_iter = 1
        self.cooldown_ticks = None
        self.cooldown_color_map = []
        self.cooldown_color_setup(4)

        self.frame_queue = None
        self.heatmap_queue = None
        self.process = None

        self.frame = [""]
        # state: 0=no change, 1=change, used for fast comparison of new frames
        self.frame_state = [0]
        self.heatmap = [""]
        # state: 0=no change, 1=change, used for fast comparison of new frames
        self.heatmap_state = [0]
        # state: 0=no ignore, 1=ignore
        self.heatmap_ignore = [0]


def controller(id, draw_id, test_number):
    Testing.iterations = 100
    Testing.start = timeit.default_timer()
    Testing.pause = 1
    Testing.total_watches = 5

    stdscr = start_curses()
    x = Generators("date", 0)

    curses.start_color()
    curses_color_setup()

    watches = []
    generators = []
    for x in range(Testing.total_watches):
        generators.append()
        generators[x] = Generators()
        watches.append()
        watches[x] = Watches()
        watches[x].frame_queue = multiprocessing.Queue(1)
        watches[x].heatmap_queue = multiprocessing.Queue(1)
        watches[x].process = multiprocessing.Process(
                    target = generators.runner,
                    args = (
                            watches[x].frame_queue,
                            watches[x].heatmap_queue
                    ))
        watches[x].process.start()


    for y in range(Testing.iterations):
        ignore = True if y == 0 else False

        istart = timeit.default_timer()

        x.runner()

        height, width = stdscr.getmaxyx()
        if draw_id.value == id:
            draw_frame(height, width)

        iend = timeit.default_timer()
        ipause = (Testing.pause - (iend - istart) - .001 )
        ipause = 0 if ipause < 0 else ipause
        time.sleep(ipause)


def main():


    controller()

    Testing.stop = timeit.default_timer()
    Testing.diff = Testing.start - Testing.stop


### start here

if __name__ == "__main__":

    try:
        error = False
        main()

    except:
        error = True
        terminate_curses()
        raise

    if curses.isendwin() is not True:
        terminate_curses()
