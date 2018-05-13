#!/usr/bin/python3
# -*- encoding: utf8 -*-

import sys
import os
import subprocess
import curses
import time
import multiprocessing
import timeit



class FrameGenerators():

    def __init__(self):
        self.command = None
        self.interval = None
        self.key_time = None
        self.start = None
        self.creation_time = None
        self.ticks_per_iter = 1
        self.cooldown_ticks = None
        self.cooldown_color_map = []
        self.cooldown_color_setup(4)

        current = None
        last = None

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


    def runner(self, command, interval, start, frame_queue, heatmap_queue, timer_queue, instruction_queue ):
        self.command = command
        self.interval = interval
        self.start = start
        self.key_time = start
        self.current = 0
        self.last = 1
        first_run = True
        counter = 0

        while True:
            instruction = instruction_queue.get(False)
            if instruction == "end":
                break
            self.frame_generator(first_run)
            self.heatmap_generator(first_run)

            first_run = False

    def process_interval(self):
        self.put_queues()
        self.flip_pointers()
        self.sleep_till_next_interval()

    def process_precision(self):
        self.key_time += self.interval
        current_time = timeit.default_timer()
        if current_time < self.key_time:
            self.put_queues()
            self.flip_pointers()
            self.sleep_till_next_precision_interval()
        else:
            drop()

    def put_queues(self):
        current = self.current
        last = self.last
        frame_queue.put(self.frame[current])
        heatmap_queue.put(self.heatmap[current])

    def flip_pointers(self):
        self.current = 1 if self.current == 0 else 0
        self.last = 1 if self.current == 0 else 0

    def sleep_till_next_interval(self):
        time.sleep(self.interval)

    def sleep_till_next_precision_interval(self):
        current_time = timeit.default_timer()
        if current_time < self.key_time:
            #time left before next interval, so sleep a bit
            time.sleep(self.key_time - current_time)
        else:
            #exceded next interval, so increase key_time. should only happen if queue transfer exceeded the interval
            self.key_time = self.key_time * int((current_time - key_time) / self.interval) * self.interval

    def drop(self):
        frame_queue.put("dropped")
        heatmap_queue.put("dropped")
        current_time = timeit.default_timer()
        self.key_time = key_time * int((current_time - key_time) / self.interval) * self.interval

    def frame_generator(self, first_run):
        """ create a new frame. a frame is composed of a line by line list of the output from
            the assigned command for this window """

        current = self.current
        last = self.last

        # process desired command for this window
        result = run_linux(self.command)
        # break result into a line by line list
        try:
            self.frame[current] = result.decode().splitlines()
        except AttributeError:
            self.frame[current] = str(result).splitlines()

        if first_run is True:
            # first time run, store it
            self.frame_state[current] = 0
        elif self.frame[current] == self.frame[last]:
            # no change from last one, set the pointer to the last frame
            self.frame_state[current] = 0
        else:
            # frame is different then the last one, store it
            self.frame_state[current] = 1


    def heatmap_generator(self, first_run, ignore=None):
        """ create a new heatmap frame. a heatmap frame is composed of a line by line list of digits indicating the
            difference between each character in this frame versus the last frame.
                0  = no change ever
                1  = changed at some point in the past
                >1 = recent change, will "cooldown" by 1 with with each new frame till it reaches 1
                """
        current = self.current
        last = self.last
        self.heatmap_state[current] = 0
        self.heatmap_ignore[current] = 0

        if first_run is True:
            # first frame, so build a new heatmap of all 0s
            for counter in range(len(self.frame[current])):
                self.heatmap[current] = len(self.frame[current]) * "0"
        elif self.frame_state[current] == 0 and self.heatmap_state[last] == 0:
            # appears nothing has changed and no cooldown needed, so simply point to the prior heatmap
            self.heatmap[current] = self.heatmap[last]
        elif ignore is True:
            # set to ignore any changes on this frame, so point to the prior heatmap
            self.heatmap_ignore[current] = 1
            self.heatmap[current] = self.heatmap[last]
        else:
            # this frame is different than the last, so make a new heatmap just for the lines that are different

            frame = [[], []]
            heatmap = [[], []]

            frame[0], frame[-1], heatmap[-1], max_lines = self.equalize_lengths(
                [""], self.frame[current], self.frame[last], self.heatmap[last])

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
                    self.heatmap_state[current] = 1
                    for cooldown in range(2, self.cooldown_ticks + 3, 1):
                        heatmap[0][line] = heatmap[0][line].replace(str(cooldown),str(cooldown - 1))

                # save the new heatmap for this frame to the main heatmap list
                self.heatmap[current].append(heatmap[0][line])

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


def start_curses():
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


class FrameStorage():

    def __init__(self, command, interval, start):
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

        self.height =None
        self.width = None
        self.x_position = None
        self.y_position = None

        self.generator = FrameGenerators()
        self.frame_queue = multiprocessing.Queue(1)
        self.heatmap_queue = multiprocessing.Queue(1)
        self.timer_queue = multiprocessing.Queue(1)
        self.instruction_queue = multiprocessing.Queue(1)
        self.command = command
        self.interval = interval
        self.start = start
        self.process = multiprocessing.Process(
            target = self.generator.runner,
            args = (
                self.command,
                self.interval,
                self.start,
                self.frame_queue,
                self.heatmap_queue,
                self.timer_queue,
                self.instruction_queue
            ))

    def start_generator(self):
        self.process.start()

class Settings():
    iterations = 100
    start = None
    increment = 1
    stop = None
    diff = None
    commands = [
        'echo "abcdefgxyz abc \n123456\n7890 !@#$&^"',
        'python -c "import timeit; print(str(timeit.default_timer()))"',
        'date',
        'date',
        './test.sh',
        'dmesg' ]
    intervals = [1, 1, 1, 1, 1, 1]
    commands_count = len(commands)


def controller():

    stdscr = start_curses()

    curses.start_color()
    curses_color_setup()

    frames = []
    Settings.start = timeit.default_timer()
    for x in range(Settings.commands_count):
        frames.append(None)
        frames[x] = InitializeClass(
                    Settings.commands[x],
                    Settings.intervals[x],
                    Settings.start)
        frames[x].start_generator()

    for counter in range(Settings.iterations):
        pass



    Settings.stop = timeit.default_timer()
    Settings.diff = Settings.start - Settings.stop


def draw_frame(window, frame, heatmap, height, width, refresh=None, pointer=None):

        height, width = stdscr.getmaxyx()
        if draw_id.value == id:
            draw_frame(height, width)

        iend = timeit.default_timer()
        ipause = (Testing.pause - (iend - istart) - .001 )
        ipause = 0 if ipause < 0 else ipause
        time.sleep(ipause)


if __name__ == "__main__":

    try:
        error = False
        controller()

    except:
        error = True
        terminate_curses()
        raise

    if curses.isendwin() is not True:
        terminate_curses()
