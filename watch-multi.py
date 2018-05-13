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
        self.creation_time = None
        self.ticks_per_iter = 1
        self.cooldown_ticks = None
        self.cooldown_color_map = []
        self.cooldown_color_setup(4)

        self.current = None
        self.last = None

        self.frame = [[],[]]
        self.frame_state = None
        self.heatmap = [[],[]]
        self.heatmap_state = None


    def cooldown_color_setup(self, cooldown_ticks=4):
        self.cooldown_ticks = cooldown_ticks
        self.cooldown_color_map = [0,1] + ([2] * (cooldown_ticks + 1))

    def runner(self,command,interval,start,precision,frame_queue,heatmap_queue,state_queue,instruction_queue):
        self.command = command
        self.interval = interval
        self.start = start
        self.precision = precision
        self.frame_queue = frame_queue
        self.heatmap_queue = heatmap_queue
        self.state_queue = state_queue
        self.instrucion_queue = instruction_queue

        self.key_time = start if precision is True else None
        self.run_time = None
        self.completion_time = None
        self.current = 0
        self.last = 1
        self.first_run = True
        self.state = None

        while True:
            instruction = instruction_queue.get(False)
            if instruction == "end":
                break
            self.frame_generator(self.first_run)
            self.heatmap_generator(self.first_run)
            self.put_queues()
            self.flip_pointers()
            self.first_run = False

    def put_queues(self):
        self.timer_queue.put(self.run_time)
        if self.frame_state == "changed":
            self.frame_queue.put(self.frame[self.current])
            self.flip_pointers()
        elif self.frame_state == "dropped":
            pass
        elif self.frame_state == "unchanged":
            self.flip_pointers()

        if self.heatmap_state == "changed":
            self.heatmap_queue.put(self.heatmap[self.current])
        elif self.heatmap_state == "dropped":
            pass
        elif self.heatmap_state == "ignore":
            pass
        elif self.heatmap_state == "unchanged":
            pass

        self.state_queue.put(
                    self.frame_state,
                    self.heatmap_state,
                    self.run_time,
                    self.completion_time
                    )

    def flip_pointers(self):
        self.current = 1 if self.current == 0 else 0
        self.last = 1 if self.current == 0 else 0

     #self.key_time = self.key_time * int((current_time - key_time) / self.interval) * self.interval

    def frame_generator(self, first_run=False):
        """ create a new frame. a frame is composed of a line by line list of the output from
            the assigned command for this window """

        if first_run is True:
            # first time run
            result, error, self.run_time, self.completion_time = run_linux(self.command)
            self.run_time = 0
            self.frame_state = "changed"
        elif self.precision is True:
            self.key_time = self.key_time + self.interval
            result, error, self.run_time, self.completion_time = run_linux(self.command, self.key_time)
            if error == "internal error: time out":
                self.frame_state = "dropped"
            if self.completion_time > self.key_time + self.interval:
                self.frame_state = "dropped"
        else:
            current_time = timeit.default_timer()
            self.key_time = current_time + self.interval
            result, error, self.run_time, self.completion_time = run_linux(self.command, self.key_time)

        # break result into a line by line list
        try:
            self.frame[self.current] = result.decode().splitlines()
        except AttributeError:
            self.frame[self.current] = str(result).splitlines()

        if self.frame[self.current] == self.frame[self.last]:
            # no change from last one
            self.frame_state = "unchanged"
        else:
            # frame is different then the last one
            self.frame_state = "changed"

    def heatmap_generator(self, first_run=False, ignore=None):
        """ create a new heatmap frame. a heatmap frame is composed of a line by line list of digits indicating the
            difference between each character in this frame versus the last frame.
                0  = no change ever
                1  = changed at some point in the past
                >1 = recent change, will "cooldown" by 1 with with each new frame till it reaches 1
                """
        current = self.current
        last = self.last

        if first_run is True:
            # first frame, so build a new heatmap of all 0s
            self.heatmap_state = "changed"
            for counter in range(len(self.frame[current])):
                self.heatmap[current] = len(self.frame[current]) * "0"
        elif self.frame_state == "dropped":
            self.heatmap_state = "dropped"
        elif self.frame_state != "changed" and self.heatmap_state != "changed":
            # appears nothing has changed and no cooldown needed, so simply point to the prior heatmap
            self.heatmap_state = "unchanged"
            self.heatmap[current] = self.heatmap[last]
        elif ignore is True:
            # set to ignore any changes on this frame, so point to the prior heatmap
            self.heatmap_state = "ignore"
            self.heatmap[current] = self.heatmap[last]
        else:
            # this frame is different than the last, so make a new heatmap just for the lines that are different
            self.heatmap_state = "changed"

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


def run_linux(command,start_time=None):
    run_time = timeit.default_timer()
    if start_time is not None:
        current_time = timeit.default_timer()
        if current_time <= start_time:
            time.sleep(start_time - current_time)
        else:
            return None, "internal error: time out", current_time

    run_time = timeit.default_timer()
    result, error = subprocess.Popen(
                command.split(" "),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            ).communicate()
    completion_time = timeit.default_timer()

    return result, error, run_time, completion_time


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


def terminate_program():
    for frame in FrameStorage.instances:
        frame.terminate_generator()
    curses.echo()
    curses.nocbreak()
    curses.curs_set(1)
    curses.endwin()
    # if error is False:
    #     print("{0} iterations, start:{1:.3f} stop:{2:.3f} diff:{3:.3f})".format(
    #         Testing.iterations,
    #         Testing.start,
    #         Testing.stop,
    #         Testing.diff))

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

class FrameStorage():

    instances = []

    def __init__(self, command, interval, start, precision):
        self.command = command
        self.interval = interval
        self.start = start
        self.precision = precision

        self.ticks_per_iter = 1
        self.cooldown_ticks = None
        self.cooldown_color_map = []

        self.frame = []
        self.frame_pointer = []
        self.frame_state = []
        self.frame_run_time = []
        self.frame_completion_time = []
        self.heatmap = []
        self.heatmap_pointer = []
        self.heatmap_state = []
        self.current = 0

        self.v_position = 0
        self.h_postion = 0

        self.height = None
        self.width = None
        self.x_position = None
        self.y_position = None

        self.generator = FrameGenerators()
        self.frame_queue = multiprocessing.Queue(1)
        self.heatmap_queue = multiprocessing.Queue(1)
        self.state_queue = multiprocessing.Queue(1)
        self.instruction_queue = multiprocessing.Queue(1)
        self.process = multiprocessing.Process(
            target = self.generator.runner,
            args = (
                    self.command,
                    self.interval,
                    self.start,
                    self.precision,
                    self.frame_queue,
                    self.heatmap_queue,
                    self.state_queue,
                    self.instruction_queue
            ))

        FrameStorage.instances.append(self)

    def start_generator(self):
        self.process.start()

    def terminate_generator(self):
        self.instruction_queue.put("done")

    def new_frame(self):
        self.frame.append("")
        self.frame_pointer.append("")
        self.frame_state.append("")
        self.frame_run_time.append("")
        self.frame_completion_time.append("")
        self.heatmap.append("")
        self.heatmap_pointer.append("")
        self.heatmap_state.append("")
        self.current = len(self.frame) - 1

    def get_state(self, position=None):
        if position is None:
            position = self.current
        try:
            a,b,c,d = self.state_queue.get(False)
        except multiprocessing.queues.Empty:
            return False
        else:
            self.frame_state[position] = a
            self.heatmap_state[position] = b
            self.run_time[position] = c
            self.completion_time[position] = d
            return True

    def store_frame(self, position=None):
        if position is None:
            position = self.current
        if self.frame_state[position] == "changed":
            try:
                self.frame[position] = self.frame_queue.get(False)
            except multiprocessing.queues.Empty:
                self.frame_state[position] = "dropped"
                self.heatmap_state[position] = "dropped"
                self.frame_pointer[position] = self.frame_pointer[position - 1]
            else:
                self.frame_pointer[position] = position
        elif self.frame_state[position] == "unchanged":
            self.frame_pointer[position] = self.frame_pointer[position - 1]
        elif self.frame_state[position] == "dropped":
            self.frame_pointer[position] = self.frame_pointer[position - 1]

    def store_heatmap(self, position=None):
        if position is None:
            position = self.current
        if self.heatmap_state[position] == "changed":
            try:
                self.heatmap[position] = self.heatmap_queue.get(False)
            except multiprocessing.queues.Empty:
                self.heatmap_state[position] = "ignore"
                self.heatmap_pointer[position] = self.heatmap_pointer[position - 1]
            else:
                self.heatmap_pointer[position] = position
        elif self.heatmap_state[position] == "unchanged":
            self.heatmap_pointer[position] = self.heatmap_pointer[position - 1]
        elif self.heatmap_state[position] == "dropped":
            self.heatmap_pointer[position] = self.heatmap_pointer[position - 1]
        elif self.heatmap_state[position] == "ignored":
            self.heatmap_pointer[position] = self.heatmap_pointer[position - 1]


class Settings():
    duration = 10
    start = None
    stop = None
    start_all = None
    stop_all = None
    commands = [
        'echo "abcdefgxyz abc \n123456\n7890 !@#$&^"',
        'python -c "import timeit; print(str(timeit.default_timer()))"',
        'date',
        'date',
        './test.sh',
        'dmesg' ]
    commands_count = len(commands)
    intervals = [1] * commands_count
    precision = [False] * commands_count
    key = None

def controller():

    stdscr = start_curses()

    curses.start_color()
    curses_color_setup()

    Settings.start = timeit.default_timer()
    Settings.stop = Settings.start + Settings.duration
    Settings.start_all = [Settings.start] * Settings.commands_count
    Settings.key = Settings.start

    frames = []
    for x in range(Settings.commands_count):
        frames.append("")
        frames[x] = FrameStorage(
                        Settings.commands[x],
                        Settings.intervals[x],
                        Settings.start_all[x],
                        Settings.precision[x]
                        )
        frames[x].start_generator()

    while True:
        for x in range(Settings.commands_count):
            if frames[x].get_state() is True:
                frames[x].store_frame()
                frames[x].tore_heatmap()
                frames[x].new_frame()
        current_time = timeit.default_timer()
        if current_time > Settings.stop:
            break


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
        terminate_program()
        raise

    if curses.isendwin() is not True:
        terminate_program()
