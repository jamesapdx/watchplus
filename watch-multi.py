#!/usr/bin/python3

# -*- encoding: utf8 -*-

import os
import sys
import curses
import subprocess
import multiprocessing
import threading
import time
import timeit

# ======================================================================================================================
#   Settings
# ======================================================================================================================

class Settings:
    duration = 41
    curses = True
    curses = False
    debug_mode = True
    debug_mode = False
    start = None
    stop = None
    start_all = None
    stop_all = None
    commands = [
        'dmesg;date +%N',
        'date; sleep 22; sleep 11; date',
        'echo "abcgxz abc \n123456\n7890 !@#$&^"',
        'python -c "import timeit; print(str(timeit.default_timer()))"',
        'date',
        'date',
        './test.sh',
        'dmesg' ]
    commands_count = len(commands)
    intervals = [1] * commands_count
    precision = [True] * commands_count
    cooldown_ticks = 4
    cooldown_color_map = [0, 1] + ([2] * (cooldown_ticks + 1))
    windows_count = 1

    @classmethod
    def debug(cls, item):
        if Settings.debug_mode is True:
            print(item)


# ======================================================================================================================
#   Arguments and flags
# ======================================================================================================================

# ======================================================================================================================
#   Classes/methods that run as subprocesses
# ======================================================================================================================

class FrameControllers:
    """This is the main controlling class.

    Frames are merely the collection of the stdout (or stderr) of the target command or script. If the target command
    or script is run every second for 10 seconds, 10 frames (outputs) will be generated and stored.  Heatmaps are
    numerical representation for the change state of each character in a frame, it's the highlighting that occurs when
    a character changes from one frame to the next.  See the FrameGenerators class for more details.

    This class is utilized inside a multiprocess subprocess, one subprocess for each target command or script.  Think
    of this as the brains for each of the watch's target commands - it controls the input, storage, and output for
    each target command or script.

    Class data can only be accessed from within the subprocess, multiprocess queues are utilized to share data between
    processes.

    Methods and fields in this class do the following:
        Starts child subprocesses, including:
            generator controller - as a method of an isolated FrameGenerators class instance
            draw window - as a function
        Receives frame and heatmap data from the generator subprocess via a queue
        Stores all frame and heatmap data
        Pushes the frame and heatmap data to the draw window via a queue
    """
    instances = []

    def __init__(self):
        """ As this class will be isolated in a multiprocess process, most fields are initialized in the
        self.controller() function"""
        # class fields
        FrameControllers.instances.append(self)
        self.command_id = len(FrameControllers.instances) - 1

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

    def initialize_generator_childprocess(self):
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

    def initialize_draw_window_childprocess(self):
        # window fields
        self.window = None
        self.window_id = None
        self.key_press = None
        self.heigth = 0
        self.width = 0
        self.v_position = 0
        self.h_position = 0
        self.x_position = 0
        self.y_position = 0

        # create a new curses window
        self.window = None
        if Settings.curses is True:
            self.window = curses.newwin(self.heigth, self.width, self.v_position, self.h_position)
            self.window.nodelay(0)
            self.window.keypad(True)
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

    def initialize_all_childprocesses(self):
        self.initialize_generator_childprocess()
        self.initialize_draw_window_childprocess()

    def start_all_childprocesses(self):
        self.process_generator.start()
        self.process_draw_window.start()

    def controller(self, command, interval, start, precision, instruction_queue, system_queue):
        """ This is the main method that will control the input, output, and storage of the frame and heatmap data.
        After initializing the fields, this method will simply wait for a the generator child subprocess to put a new
        frame and heatmap into the appropriate queues, which are then sent on to the draw window and file write child
        subprocesses. Note, all interval timing is done in the generator child subprocess.
            generator child --["generator"]--> controller_instruction queue (let's us know a new frame is available)
                generator child --[state]-->   |state_queue  | --> controller --> self.state
                generator child --[frame]-->   |frame_queue  | --> controller --> self.frame
                generator child --[heatmap]--> |heatmap_queue| --> controller --> self.heatmap
                    ...
                        controller --[frame]-->   |draw_frame_queue  | --> draw_window child
                        controller --[heatmap]--> |draw_heatmap_queue| --> draw_window child
        """
        self.command = command
        self.interval = interval
        self.start = start
        self.precision = precision
        self.controller_instruction_queue = instruction_queue
        self.system_queue = system_queue
        self.controller_instruction = None
        self.key_press = None
        self.presentation_mode = "live"
        self.current = 0

        # start sub-processes
        self.process_generator = None
        self.process_draw_window = None
        self.initialize_all_childprocesses()
        self.start_all_childprocesses()

        try:
            while True:
                # this controller queue get is blocking, so just wait for the a new frame or a message from key_press
                self.controller_instruction = self.controller_instruction_queue.get()
                if self.controller_instruction == "generator":
                    if self.get_frame_state() is True:
                        self.store_frame()
                        self.store_heatmap()
                        self.write_frame()
                        if self.presentation_mode == "live":
                            self.draw_live_frame()
                        if self.presentation_mode == "playback":
                            pass
                if self.controller_instruction == "key_press":
                    self.processes_key_press()
        except KeyboardInterrupt:
            # the controller method runs as a separate process and is killed either by a ctrl-c or a term_sig 2
            # poison pill / process.terminate is not used
            self.terminate_childprocesses()

    def terminate_childprocesses(self):
        """ all child subprocoesses are killed with os - signal 2, not a flag or terminate.  This leads to a clean
        stop with no error messages in the case of a user control-c. User control-c are propagated to all
        subprocesses automatically on an OS level and are not controllable. """
        # wait a tad to let the child processes stop on their own in the case of user control-c.
        time.sleep(.05)
        term_sig = 2
        if self.process_generator.exitcode is None:
            os.kill(self.process_generator.pid, term_sig)
        if self.process_draw_window.exitcode is None:
            os.kill(self.process_draw_window.pid, term_sig)
        # just in case this doesn't work because of timing or otherwise, wait a bit and kill with process.terminate
        time.sleep(.1)
        self.process_generator.terminate()
        self.process_draw_window.terminate()

    def processes_key_press(self):
        # DELETE, OBSOLETE
        keystroke = self.key_press_queue.get()
        keystroke = chr(keystroke)
        if keystroke == "1":
            draw_id.value = 1
        elif keystroke == "2":
            draw_id.value = 2
        #elif keystroke == "q":

    def get_frame_state(self):
        """ unload from the frame_state queue, this done before the frame and heatmap"""
        try:
            # only give it 1 second to unload the queue, don't want to get stuck forever
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
        """ frames and heatmaps are stored in lists, so just append a new blank element to the fields """
        self.frame.append("")
        self.frame_pointer.append("")
        self.frame_state.append("")
        self.frame_run_time.append("")
        self.frame_completion_time.append("")
        self.heatmap.append("")
        self.heatmap_pointer.append("")
        self.heatmap_state.append("")
        self.current = len(self.frame) - 1
        Settings.debug("self.current: " + str(self.current))

    def store_frame(self):
        """ if the state is "changed", this function will try unload and store a single frame from the queue,
        otherwise the pointer will simply be set to the previous frame"""
        if self.current == 0:
            # first frame
            self.frame_pointer[self.current] = 0
        if self.frame_state[self.current] == "changed":
            try:
                frame_timeout = 1
                self.frame[self.current] = self.generator_frame_queue.get(block=True,timeout=frame_timeout)
            except multiprocessing.queues.Empty:
                # unable to get anything from the queue, just consider this an error and drop the frame
                Settings.debug("dropped in frame")
                self.frame_state[self.current] = "dropped"
                self.heatmap_state[self.current] = "dropped"
                self.frame_pointer[self.current] = self.frame_pointer[self.current - 1]
            else:
                self.frame_pointer[self.current] = self.current
        elif self.frame_state[self.current] == "unchanged":
            self.frame_pointer[self.current] = self.frame_pointer[self.current - 1]
        elif self.frame_state[self.current] == "dropped":
            self.frame_pointer[self.current] = self.frame_pointer[self.current - 1]
            Settings.debug("dropped")

    def store_heatmap(self):
        """ if the state is "changed", this function will try unload and store single a heatmap from the queue,
        otherwise the pointer will simply be set to the previous heatmap"""
        if self.current == 0:
            self.heatmap_pointer[self.current] = self.current
        if self.heatmap_state[self.current] == "changed":
            try:
                heatmap_timeout = 1
                self.heatmap[self.current] = self.generator_heatmap_queue.get(block=True,timeout=heatmap_timeout)
            except multiprocessing.queues.Empty:
                # unable to get anything from the queue, just consider this an error and ignore the heatmap
                self.heatmap_state[self.current] = "ignore"
                self.heatmap_pointer[self.current] = self.heatmap_pointer[self.current - 1]
            else:
                self.heatmap_pointer[self.current] = self.current
        elif self.heatmap_state[self.current] == "unchanged":
            self.heatmap_pointer[self.current] = self.heatmap_pointer[self.current - 1]
        elif self.heatmap_state[self.current] == "dropped":
            self.heatmap_pointer[self.current] = self.heatmap_pointer[self.current - 1]
            Settings.debug("dropped")
        elif self.heatmap_state[self.current] == "ignored":
            self.heatmap_pointer[self.current] = self.heatmap_pointer[self.current - 1]

    def write_frame(self):
        pass

    def draw_live_frame(self):
        if self.presentation_mode == "live" and self.window_id is not None:
            pass
        self.draw_instruction_queue.put("draw")
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
        self.command_gid = None
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

        current_time = timeit.default_timer()
        try:
            while True:
                sleep_time = max(self.key_time - current_time, 0)

                try:
                    self.instruction = instruction_queue.get(timeout=sleep_time)
                except multiprocessing.queues.Empty:
                    pass
                else:
                    pass

                if self.precision is True and self.first_run is False and sleep_time == 0:
                    self.dropped()
                    Settings.debug("dropped in generator 1")
                else:
                    Settings.debug("starting frame generator: ")
                    self.frame_generator()
                    if self.frame_state != "dropped":
                        Settings.debug("starting heatmap generator: ")
                        self.heatmap_generator()

                Settings.debug("starting put_queues generator: ")
                self.put_queues()
                Settings.debug("ending put_queues generator: ")

                self.first_run = False
                self.frame_state = None
                self.heatmap_state = None

                current_time = timeit.default_timer()
                if self.precision is True:
                    self.key_time = self.key_time + self.interval
                else:
                    self.key_time = current_time + self.interval

        except KeyboardInterrupt:
            if self.command_gid != 0:
                Settings.debug("gggggt2")
                term_sig = 15
                os.killpg(os.getpgid(self.command_gid), term_sig)
            pass

    def dropped(self, run_time=None, completion_time=None):
        self.command_gid = 0
        self.frame_state = "dropped"
        self.heatmap_state = "dropped"
        current_time = timeit.default_timer()
        self.run_time = current_time if run_time is None else run_time
        self.completion_time = current_time if completion_time is None else completion_time

    def put_queues(self):
        Settings.debug("q1")
        Settings.debug("gen command_gid: " + str(self.command_gid))
        if self.heatmap_state == "changed":
            Settings.debug("q1.1")
            self.heatmap_queue.put(self.heatmap[self.current])
            #except Full:
            Settings.debug("q1.2")
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
        Settings.debug("q3")

        self.state_queue.put((
            self.frame_state,
            self.heatmap_state,
            self.run_time,
            self.completion_time
        ))
        Settings.debug("q4")

        self.controller_instruction_queue.put("generator")

    def flip_pointers(self):
        self.current = 1 if self.current == 0 else 0
        self.last = 1 if self.current == 0 else 0

    # self.key_time = self.key_time * int((current_time - key_time) / self.interval) * self.interval

    def terminate_gid(self, gid):
        term_sig = 15
        os.killpg(gid, term_sig)
        self.frame_state = "dropped"

    # noinspection PyShadowingNames
    def frame_generator(self):
        """ create a new frame. a frame is composed of a line by line list of the output from
            the assigned command for this window """

        self.run_time = timeit.default_timer()
        proc = subprocess.Popen(
            self.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            preexec_fn=os.setsid
        )
        gid = os.getpgid(proc.pid)
        self.command_gid = gid
        Settings.debug("gen command_gid: " + str(self.command_gid))

        if self.precision is True:
            safe_margin = .02
            end_timer = ((self.key_time + self.interval) - safe_margin) - self.run_time

            timer = threading.Timer(end_timer, self.terminate_gid, args=(gid,))
            timer.start()

            result, error = proc.communicate()
            timer.cancel()

            if self.frame_state == "dropped":
                self.dropped(self.run_time)
                return
        else:
            result, error = proc.communicate()

        self.command_gid = 0
        self.completion_time = timeit.default_timer()

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


# ======================================================================================================================
#   Functions that run as subprocesses
# ======================================================================================================================


def draw_window(window, frame_queue, heatmap_queue, instruction_queue, controller_instruction_queue):
    """ draw the most recent frame

    :param window:
    :param frame_queue:
    :param heatmap_queue:
    :param instruction_queue:
    :param controller_instruction_queue:
    :return:
    """

    try:
        custom_height = 9999
        custom_width = 9999

        while True:
            instruction = instruction_queue.get()
            Settings.debug("d1")

            if Settings.curses is False:
                # don't use curses
                Settings.debug("d2")
                frame = frame_queue.get()
                Settings.debug("d3")
                heatmap = heatmap_queue.get()
                Settings.debug("d4")
                #subprocess.Popen("clear").communicate()
                #print("\n".join(frame))
                #print("\n".join(heatmap))
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

    except KeyboardInterrupt:
        pass


def key_controller(window, system_queue):
    try:
        while True:
            keystroke = window.getkey()
            keystroke = chr(keystroke)
            if keystroke == "1":
                draw_id.value = 1
            elif keystroke == "2":
                draw_id.value = 2
    except KeyboardInterrupt:
        pass



# ======================================================================================================================
#   Functions
# ======================================================================================================================


def run_linux(command):
    start = timeit.default_timer()
    result, error = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True
        ).communicate()
    print(str(timeit.default_timer() - start))
    return result, error

def run_linux2(command):
    result, error = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    ).communicate()
    return result, error

def run_linux3(command):
    p = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True
        ,preexec_fn=os.setsid
    )
    #timerp = lambda p: p.wait()
    #timer = multiprocessing.Process(target=timerp, args=(p,))
    #timer.start()
    #timer.join(5)

    start = timeit.default_timer()
    end = timeit.default_timer() + 4 - .02
    while True:
        time.sleep(.005)
        if p.poll() is not None:
            print("ssss")
            break
        elif timeit.default_timer() > end:
            os.killpg(os.getpgid(p.pid), 15)
            break
    #time.sleep(3)
    #os.killpg(os.getpgid(p.pid), 15)
    result, error = p.communicate()
    print(str(timeit.default_timer() - start))
    return result, error

def run_linux4(command):
    start = timeit.default_timer()
    p = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True
        ,preexec_fn=os.setsid
    )

    pg = os.getpgid(p.pid)
    tend = lambda pg: os.killpg(pg, 15)
    end = 2

    t = threading.Timer(6, tend, [pg])
    t.start()
    result, error = p.communicate()
    t.cancel()
    print(str(timeit.default_timer() - start))
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


def terminate_processes():
    time.sleep(.15)
    for proc in Main.process_frame_controllers:
        if proc.exitcode is None:
            term_sig = 2
            os.kill(proc.pid, term_sig)
    time.sleep(.2)
    for proc in Main.process_frame_controllers:
        proc.terminate()


def terminate_curses():
    curses.echo()
    curses.nocbreak()
    curses.curs_set(1)
    curses.endwin()


class Main:
    instruction_queues = []
    system_queues = []
    process_frame_controllers = []


def initialize_key_press_process(self):
    self.process_key_press = multiprocessing.Process(
        target=self.key_press,
        args=(
            self.system_queue
        ))

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

    Main.system_queue = multiprocessing.Queue(1)
    frame_controller_seed = FrameControllers()
    for x in range(Settings.commands_count):
        # result, error = run_linux4(Settings.commands[x])
        # print(len(result))
        # sys.exit()

        Main.instruction_queues.append("")
        Main.system_queues.append("")
        Main.process_frame_controllers.append("")

        Main.instruction_queues[x] = multiprocessing.Queue(1)
        Main.process_frame_controllers[x] = multiprocessing.Process(
            target=frame_controller_seed.controller,
            args=(
                Settings.commands[x],
                Settings.intervals[x],
                Settings.start_all[x],
                Settings.precision[x],
                Main.instruction_queues[x],
                Main.system_queue
            ))

    for x in range(Settings.commands_count):
        Main.process_frame_controllers[x].start()

    time.sleep(Settings.stop - Settings.start)


if __name__ == "__main__":

    # noinspection PyPep8
    terminate = True
    try:
        main_controller()
        #time.sleep("dd")
    except KeyboardInterrupt:
        print("")
        terminate = False
    finally:
        if terminate is True:
            terminate_processes()
        if Settings.curses is True:
            terminate_curses()

        #curses.isendwin() is not True:
        # filename = "/tmp/watchp" + str(x) + ".tmp"
        # with open(filename, "w") as f:
        #     f.write("#!/bin/sh\n")
        #     f.write(Settings.commands[x])
        # run_linux("chmod +x " + str(filename))
        # #Settings.commands[x] = filename
        # result, error = run_linux3(Settings.commands[x])
        # print(result)
        # print(error)
        # sys.exit()
