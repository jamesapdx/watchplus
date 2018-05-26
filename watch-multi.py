#!/usr/bin/python3

# -*- encoding: utf8 -*-

import sys
import subprocess
import curses
import time
import multiprocessing
import timeit


class FrameController:
    instances = []

    def __init__(self):
        # class fields
        FrameController.instances.append(self)
        self.command_id = len(FrameController.instances) - 1

        # frame storage fields
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

        # window fields
        self.window = None
        self.window_id = None
        self.heigth = 0
        self.width = 0
        self.v_position = 0
        self.h_position = 0
        self.x_position = 0
        self.y_position = 0

    def initialize_generator_subprocess(self):
        #self.cooldown_ticks = None
        #self.cooldown_color_map = []

        self.generator_seed = FrameGenerators()
        self.generator_frame_queue = multiprocessing.Queue(1)
        self.generator_heatmap_queue = multiprocessing.Queue(1)
        self.generator_state_queue = multiprocessing.Queue(1)
        self.generator_instruction_queue = multiprocessing.Queue(1)
        self.process_generator = multiprocessing.Process(
            target=self.generator_seed.controller,
            args=(
                self.command,
                self.interval,
                self.start,
                self.precision,
                self.generator_frame_queue,
                self.generator_heatmap_queue,
                self.generator_state_queue,
                self.generator_instruction_queue,
                self.controller_instruction_queue
            ))

    def initialize_draw_window_subprocess(self):
        self.window = None
        if Settings.curses is True:
            self.window = curses.newwin(self.heigth, self.width, self.v_position, self.h_position)
        self.draw_frame_queue = multiprocessing.Queue(1)
        self.draw_heatmap_queue = multiprocessing.Queue(1)
        self.draw_instruction_queue = multiprocessing.Queue(1)
        self.process_draw_window = multiprocessing.Process(
            target=draw_window,
            args=(
                self.window,
                self.draw_frame_queue,
                self.draw_heatmap_queue,
                self.draw_instruction_queue,
                self.controller_instruction_queue
            ))

    def initialize_subprocesses(self):
        self.initialize_generator_subprocess()
        self.initialize_draw_window_subprocess()

    def start_subprocesses(self):
        self.process_generator.start()
        self.process_draw_window.start()

    def terminate_subprocesses(self):
        self.process_generator.terminate()
        self.process_draw_window.terminate()

    def controller(self, command, interval, start, precision, instruction_queue, system_queue):
        self.command = command
        self.interval = interval
        self.start = start
        self.precision = precision
        self.controller_instruction_queue = instruction_queue
        self.system_queue = system_queue
        self.controller_sleep = Settings.controller_sleep
        self.controller_instruction = None
        self.controller_sleep = .01
        self.key_press = None
        self.presentation_mode = "live"

        # start sub-processes
        self.process_generator = None
        self.process_draw_window = None
        self.initialize_subprocesses()
        self.start_subprocesses()

        while True:
            self.controller_instruction = self.controller_instruction_queue.get()
            if self.controller_instruction == "terminate":
                self.terminate_subprocesses()
                break
            if self.controller_instruction == "generator":
                Settings.debug("c1")
                if self.get_frame_state() is True:
                    Settings.debug("c2")
                    self.store_frame()
                    Settings.debug("c3")
                    self.store_heatmap()
                    Settings.debug("c4")
                    self.write_frame()
                    if self.presentation_mode == "live":
                        self.draw_live_frame()
                    if self.presentation_mode == "playback":
                        pass
                Settings.debug("c5")
            Settings.debug("c6")

    def get_key_press(self):
        return False

    def get_frame_state(self):
        try:
            state_timeout = 1
            a, b, c, d = self.generator_state_queue.get(block=True,timeout=state_timeout)
        except multiprocessing.queues.Empty:
            Settings.debug("state_timeout")
            return False
        else:
            self.new_frame()
            self.frame_state[self.current] = a
            self.heatmap_state[self.current] = b
            self.frame_run_time[self.current] = c
            self.frame_completion_time[self.current] = d
            return True

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

    def store_frame(self):
        if self.frame_state[self.current] == "changed":
            try:
                frame_timeout = 1
                self.frame[self.current] = self.generator_frame_queue.get(block=True,timeout=frame_timeout)
            except multiprocessing.queues.Empty:
                self.frame_state[self.current] = "dropped"
                self.heatmap_state[self.current] = "dropped"
                self.frame_pointer[self.current] = self.frame_pointer[self.current - 1]
            else:
                self.frame_pointer[self.current] = self.current
        elif self.frame_state[self.current] == "unchanged":
            self.frame_pointer[self.current] = self.frame_pointer[self.current - 1]
        elif self.frame_state[self.current] == "dropped":
            self.frame_pointer[self.current] = self.frame_pointer[self.current - 1]

    def store_heatmap(self):
        if self.heatmap_state[self.current] == "changed":
            try:
                heatmap_timeout = 1
                self.heatmap[self.current] = self.generator_heatmap_queue.get(block=True,timeout=heatmap_timeout)
            except multiprocessing.queues.Empty:
                self.heatmap_state[self.current] = "ignore"
                self.heatmap_pointer[self.current] = self.heatmap_pointer[self.current - 1]
            else:
                self.heatmap_pointer[self.current] = self.current
        elif self.heatmap_state[self.current] == "unchanged":
            self.heatmap_pointer[self.current] = self.heatmap_pointer[self.current - 1]
        elif self.heatmap_state[self.current] == "dropped":
            self.heatmap_pointer[self.current] = self.heatmap_pointer[self.current - 1]
        elif self.heatmap_state[self.current] == "ignored":
            self.heatmap_pointer[self.current] = self.heatmap_pointer[self.current - 1]

    def write_frame(self):
        pass

    def draw_live_frame(self):
        if self.presentation_mode == "live" and self.window_id is not None:
            pass

        self.draw_frame_queue.put(self.frame[self.frame_pointer[-1]])
        self.draw_heatmap_queue.put(self.heatmap[self.heatmap_pointer[-1]])

    def draw_playback_frame(self):
        pass

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
    def controller(self, command, interval, start, precision, frame_queue, heatmap_queue, state_queue,
                   instruction_queue, controller_instruction_queue):
        self.command = command
        self.interval = interval
        self.start = start
        self.precision = precision
        self.frame_queue = frame_queue
        self.heatmap_queue = heatmap_queue
        self.state_queue = state_queue
        self.instruction_queue = instruction_queue
        self.controller_instruction_queue = controller_instruction_queue
        self.instruction = None

        #self.key_time = start if precision is True else 0
        self.key_time = start
        self.run_time = None
        self.completion_time = None
        self.current = 0
        self.last = 1
        self.first_run = True
        self.state = None
        self.dont_wait_gap = .008

        while True:
            current_time = timeit.default_timer()
            instruction_timeout = max((self.key_time - self.dont_wait_gap) - current_time, 0)
            Settings.debug("instruction timeout: " + str(instruction_timeout))

            try:
                self.instruction = instruction_queue.get(timeout=instruction_timeout)
            except multiprocessing.queues.Empty:
                pass
            else:
                if self.instruction == "done":
                    break

            Settings.debug("starting frame generator: ")
            self.frame_generator()
            Settings.debug("starting heatmap generator: ")
            self.heatmap_generator()
            Settings.debug("starting put_queues generator: ")
            self.put_queues()
            Settings.debug("ending put_queues generator: ")

            self.first_run = False
            if self.precision is True:
                self.key_time = self.key_time + self.interval
            else:
                self.key_time = current_time + self.interval

    def put_queues(self):
        Settings.debug("q1")
        if self.heatmap_state == "changed":
            self.heatmap_queue.put(self.heatmap[self.current])
        elif self.heatmap_state == "dropped":
            pass
        elif self.heatmap_state == "ignore":
            pass
        elif self.heatmap_state == "unchanged":
            pass
        Settings.debug("q2")

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
        #time.sleep(.0001)

        self.controller_instruction_queue.put("generator")

    def flip_pointers(self):
        self.current = 1 if self.current == 0 else 0
        self.last = 1 if self.current == 0 else 0

    # self.key_time = self.key_time * int((current_time - key_time) / self.interval) * self.interval

    # noinspection PyShadowingNames
    def frame_generator(self):
        """ create a new frame. a frame is composed of a line by line list of the output from
            the assigned command for this window """

        result, error, self.run_time, self.completion_time = self.run_command()
        #print("aa" + str(self.frame[self.current]))
        #print("key1:" + str(self.key_time))
        if self.precision is True:
            if self.completion_time > self.key_time + self.interval:
                self.frame_state = "dropped"
        if self.frame_state == "dropped":
            return

        # break result into a line by line list
        try:
            self.frame[self.current] = result.decode().splitlines()
        except AttributeError:
            self.frame[self.current] = str(result).splitlines()

        if self.first_run is True:
            # first time run
            self.frame_state = "changed"
        elif self.frame[self.current] == self.frame[self.last]:
            # no change from last one
            self.frame_state = "unchanged"
        else:
            # frame is different then the last one
            self.frame_state = "changed"


    def heatmap_generator(self, ignore=None):
        """ create a new heatmap frame. a heatmap frame is composed of a line by line list of digits indicating the
            difference between each character in this frame versus the last frame.
                0  = no change ever
                1  = changed at some point in the past
                >1 = recent change, will "cooldown" by 1 with with each new frame till it reaches 1
                """
        current = self.current
        last = self.last

        if self.first_run is True:
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


    def run_command(self):
        current_time = timeit.default_timer()
        sleep_time = max(self.key_time - current_time, 0)
        if self.precision is True and self.first_run is False:
            #sleep_time = 0
            if sleep_time == 0:
                self.frame_state = "dropped"
                return None, None, current_time, current_time
        time.sleep(sleep_time)

        run_time = timeit.default_timer()
        result, error = subprocess.Popen(
            self.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        ).communicate()
        completion_time = timeit.default_timer()

        return result, error, run_time, completion_time


def draw_window(window, frame_queue, heatmap_queue, instruction_queue, controller_instruction_queue):

    custom_height = 9999
    custom_width = 9999

    while True:
        if Settings.curses is False:
            frame = frame_queue.get()
            heatmap = heatmap_queue.get()
            #subprocess.Popen("clear").communicate()
            print("\n".join(frame))
            print("\n".join(heatmap))
            continue

        frame = frame_queue.get()
        heatmap = heatmap_queue.get()

        window.clear()

        terminal_height, terminal_width = window.getmaxyx()

        #if geometry == "window":
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
                    char = "?"
                try:
                    color_pair = curses.color_pair(Settings.cooldown_color_map[int("0" + heatmap[line][column])])
                except IndexError:
                    color_pair = 0
                window.addstr(line, column, char, color_pair)
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
    for queue in Main.instruction_queues:
        queue.put("terminate")

    if Settings.curses is False:
        return

    curses.echo()
    curses.nocbreak()
    curses.curs_set(1)
    curses.endwin()

class Settings:
    duration = 49
    curses = True
    curses = False
    debug_mode = False
    debug_mode = True
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
    controller_sleep = .01
    cooldown_ticks = 4
    cooldown_color_map = [0, 1] + ([2] * (cooldown_ticks + 1))
    windows_count = 1

    @classmethod
    def debug(cls, item):
        if Settings.debug_mode is True:
            print(item)


class Main:
    instruction_queues = []
    system_queues = []
    process_frame_controllers = []

def main_controller():
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

    #def controller(self, command, interval, start, precision, instruction_queue, system_queue):
    frame_controller_seed = FrameController()
    for x in range(Settings.commands_count):
        Main.instruction_queues.append("")
        Main.system_queues.append("")
        Main.process_frame_controllers.append("")

        Main.instruction_queues[x] = multiprocessing.Queue(1)
        Main.system_queues[x] = multiprocessing.Queue(1)
        Main.process_frame_controllers[x] = multiprocessing.Process(
            target=frame_controller_seed.controller,
            args=(
                Settings.commands[x],
                Settings.intervals[x],
                Settings.start_all[x],
                Settings.precision[x],
                Main.instruction_queues[x],
                Main.system_queues[x]
            ))
    for x in range(Settings.commands_count):
        Main.process_frame_controllers[x].start()

    time.sleep(Settings.stop - Settings.start)

if __name__ == "__main__":

    # noinspection PyPep8
    try:
        error = False
        main_controller()

    except:
        error = True
        terminate_program()
        raise

    terminate_program()

    if Settings.curses is True:
        if curses.isendwin() is not True:
            terminate_program()

