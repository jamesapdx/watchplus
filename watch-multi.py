#!/usr/bin/python3

# -*- encoding: utf8 -*-

import sys
import subprocess
import curses
import time
import multiprocessing
import timeit


class FrameStorage:
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
        self.new_frame()

        self.presentation_mode = "live"
        self.window_id = None

        self.height = None
        self.width = None
        self.x_position = None
        self.y_position = None

        self.generator = FrameGenerators()
        self.frame_queue = multiprocessing.Queue(1)
        self.heatmap_queue = multiprocessing.Queue(1)
        self.state_queue = multiprocessing.Queue(1)
        self.instruction_queue = multiprocessing.Queue(1)
        self.process_runner = multiprocessing.Process(
            target=self.generator.runner,
            args=(
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
        self.command_id = len(FrameStorage.instances) - 1

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

    def start_generator(self):
        self.process_runner.start()

    def terminate_generator(self):
        self.process_runner.terminate()

    def get_state(self, position=None):
        if position is None:
            position = self.current
        try:
            a, b, c, d = self.state_queue.get(False)
        except multiprocessing.queues.Empty:
            return False
        else:
            self.frame_state[position] = a
            self.heatmap_state[position] = b
            self.frame_run_time[position] = c
            self.frame_completion_time[position] = d
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

    def draw_live_frame(self, stdscr):

        if self.presentation_mode == "live" and self.window_id is not None:
            pass

        draw_window(stdscr, self.frame[self.frame_pointer[-1]], self.heatmap[self.heatmap_pointer[-1]])



# noinspection PyAttributeOutsideInit
class FrameGenerators:

    def __init__(self):
        self.creation_time = None
        self.ticks_per_iter = 1
        self.cooldown_ticks = None
        self.cooldown_color_map = []

        self.current = None
        self.last = None

        self.frame = [[], []]
        self.frame_state = None
        self.heatmap = [[], []]
        self.heatmap_state = None


    # noinspection PyAttributeOutsideInit
    def runner(self, command, interval, start, precision, frame_queue, heatmap_queue, state_queue, instruction_queue):
        self.command = command
        self.interval = interval
        self.start = start
        self.precision = precision
        self.frame_queue = frame_queue
        self.heatmap_queue = heatmap_queue
        self.state_queue = state_queue
        self.instrucion_queue = instruction_queue
        self.id = str(timeit.default_timer())

        self.key_time = start if precision is True else None
        self.run_time = None
        self.completion_time = None
        self.current = 0
        self.last = 1
        self.first_run = True
        self.state = None

        while True:
            instruction = None
            try:
                instruction = instruction_queue.get(False)
            except multiprocessing.queues.Empty:
                pass
            if instruction == "done":
                break
            self.frame_generator(first_run=self.first_run)
            self.heatmap_generator(first_run=self.first_run)
            self.put_queues()
            self.first_run = False

    def put_queues(self):
        if self.heatmap_state == "changed":
            self.heatmap_queue.put(self.heatmap[self.current])
        elif self.heatmap_state == "dropped":
            pass
        elif self.heatmap_state == "ignore":
            pass
        elif self.heatmap_state == "unchanged":
            pass

        if self.frame_state == "changed":
            self.frame_queue.put(self.frame[self.current])
            self.flip_pointers()
        elif self.frame_state == "dropped":
            pass
        elif self.frame_state == "unchanged":
            self.flip_pointers()

        self.state_queue.put((
            self.frame_state,
            self.heatmap_state,
            self.run_time,
            self.completion_time
        ))

    def flip_pointers(self):
        self.current = 1 if self.current == 0 else 0
        self.last = 1 if self.current == 0 else 0

    # self.key_time = self.key_time * int((current_time - key_time) / self.interval) * self.interval

    # noinspection PyShadowingNames
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
            self.heatmap[current] = []
            for counter in range(len(self.frame[current])):
                self.heatmap[current].append(len(self.frame[current][counter]) * "0")
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
            heatmap[0] = []

            # start line by line comparison
            for line in range(max_lines):

                heatmap[0].append("")
                # if this line is different, do a char by char comparison
                if frame[0][line] != frame[-1][line]:
                    # get max length of this fame line, last frame line, last heatmap_line
                    frame[0][line], frame[-1][line], heatmap[-1][line], max_char = self.equalize_lengths(
                        " ", frame[0][line], frame[-1][line], heatmap[-1][line])

                    # perform a char by char comparison to the last frame and mark hot if different
                    for column in range(max_char):
                        if frame[0][line][column] != frame[-1][line][column]:
                            # char is different, mark hot
                            heatmap[0][line] += str(Settings.cooldown_ticks + 2)
                        else:
                            # char is same
                            heatmap[0][line] += heatmap[-1][line][column]
                else:
                    heatmap[0][line] = heatmap[-1][line]

                # cooldown by 1 any heatmap char that is greater than 1
                if int(max(heatmap[0][line])) > 1:
                    for cooldown in range(2, Settings.cooldown_ticks + 3, 1):
                        heatmap[0][line] = heatmap[0][line].replace(str(cooldown), str(cooldown - 1))

            # save the new heatmap for this frame to the main heatmap
            self.heatmap[current] = heatmap[0]

    # noinspection PyMethodMayBeStatic
    def equalize_lengths(self, adder, *args):
        # make an array of lengths
        lengths = [len(value) for value in args]
        max_length = max(lengths)
        # take a value and add more of the "adder," for an array it will add more array elements, for a sting it will
        # add more sting length
        values = [value + (adder * (max_length - length)) for length, value in zip(lengths, args)]
        values.append(max_length)
        return values

class Windows:
    isinstance = []

    def __init__(self):
        self.v_position = 0
        self.h_postion = 0
        self.heigth = 0
        self.width = 0

        self.command_id = 0

        self.frame_queue = multiprocessing.Queue(1)
        self.heatmap_queue = multiprocessing.Queue(1)
        self.instruction_queue = multiprocessing.Queue(1)
        self.process_draw_window = multiprocessing.Process(
            target=self.draw_window,
            args=(
                self.frame_queue,
                self.heatmap_queue,
                self.state_queue,
                self.instruction_queue
            ))

        Windows.isinstance.append(self)
        self.window_id = len(Windows) - 1

def draw_window(window, frame_queue, heatmap_queue, geometry="window", custom_height=9999, custom_width=9999, refresh=None):

    if Settings.curses is False:
        subprocess.Popen("clear").communicate()
        print("\n".join(frame_queue))
        print("\n".join(heatmap_queue))

        return

    #while True:
    frame = frame_queue
    heatmap = heatmap_queue

    window.clear()

    terminal_height, terminal_width = window.getmaxyx()

    if geometry == "window":
        draw_height = min(len(frame), terminal_height - 1, custom_height - 1)
        width = min(terminal_width, custom_width)

    for line in range(draw_height):
        #frame[line], heatmap[line], max_char = self.equalize_lengths(" ", frame[line], heatmap[line])
        #heatmap = heatmap.replace(" ", "0")

        draw_width = min(len(frame[line]), width)

        for column in range(draw_width):
            try:
                char = str(frame[line][column])
            except IndexError:
                char = "X"
            try:
                color_pair = curses.color_pair(Settings.cooldown_color_map[int("0" + heatmap[line][column])])
            except IndexError:
                color_pair = 0
            window.addstr(
                line,
                column,
                char,
                color_pair
            )
    window.refresh()


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
            # sys.exit()
        time.sleep(.1)


def run_linux(command, start_time=None):
    run_time = timeit.default_timer()
    if start_time is not None:
        current_time = timeit.default_timer()
        if current_time <= start_time:
            time.sleep(start_time - current_time)
        else:
            return None, "internal error: time out", current_time

    run_time = timeit.default_timer()
    result, error = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True
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
    if Settings.curses is False:
        return
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

class Settings:
    duration = 12
    curses = False
    curses = True
    start = None
    stop = None
    start_all = None
    stop_all = None
    commands = [
        'date'
    ]
    # 'echo "abcdefgxyz abc \n123456\n7890 !@#$&^"',
    # 'python -c "import timeit; print(str(timeit.default_timer()))"',
    # 'date',
    # 'date',
    # './test.sh',
    # 'dmesg' ]
    commands_count = len(commands)
    intervals = [1] * commands_count
    precision = [True] * commands_count
    min_intervals = min(intervals)
    min_space = .0033
    max_space = .1
    spacer = min( max(min_intervals * .1, min_space), max_space)
    cooldown_ticks = 4
    cooldown_color_map = [0, 1] + ([2] * (cooldown_ticks + 1))


def controller():
    if Settings.curses:
        stdscr = start_curses()
        curses.start_color()
        curses_color_setup()
    else:
        stdscr = None

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
    for x in range(Settings.commands_count):
        frames[x].start_generator()

    while True:
        for x in range(Settings.commands_count):
            if frames[x].get_state() is True:
                frames[x].store_frame()
                frames[x].store_heatmap()
                frames[x].draw_live_frame(stdscr)
                frames[x].new_frame()
        time.sleep(Settings.spacer)
        current_time = timeit.default_timer()
        if current_time > Settings.stop:
            break

    Settings.stop = timeit.default_timer()
    Settings.diff = Settings.start - Settings.stop


if __name__ == "__main__":

    # noinspection PyPep8
    try:
        error = False
        controller()

    except:
        error = True
        terminate_program()
        raise

    terminate_program()

    if Settings.curses is True:
        if curses.isendwin() is not True:
            terminate_program()
