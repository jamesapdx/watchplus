#!/usr/bin/python

# -*- encoding: utf8 -*-

import os
import sys
import curses
import subprocess
import multiprocessing
import threading
import time
import timeit
import argparse
import copy

# ----------------------------------------------------------------------------------------------------------------------
#       working on:
#       done:
#       working:
#       note: there are now two draw functions
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
#       Settings
# ----------------------------------------------------------------------------------------------------------------------

class Settings:
    curses = False
    curses = True
    cooldown_ticks = 4
    cooldown_color_map = [0, 1] + ([2] * (cooldown_ticks + 1))

    scripts_types = [".py",".sh"]
    scripts_path = ["~/","../","."]
    scripts_folder = "bwatch.d"
    cwd = os.getcwd()
    app = os.path.basename(__file__)

    max_windows = 6
    max_instances = 20
    max_commands = 16

class Defaults:
    interval = 1
    duration = 0
    imprecise = False
    plain = False

class Debug:
    debug_level = 0
    debug_mode = True
    debug_mode = False

    @classmethod
    def debug(cls, item, level=0):
        if Debug.debug_mode is True and Settings.curses is False and Debug.debug_level >= level:
            print(item)

# ----------------------------------------------------------------------------------------------------------------------
#       Initialize
# ----------------------------------------------------------------------------------------------------------------------

# if True:
#     commands = [
#         'date +%N; dmesg',
#         'date +%N',
#         'python -c "import timeit; print(str(timeit.default_timer()))"',
#         'echo "abcgxz abc \n123456\n7890 !@#$&^"',
#         'date +%N',
#         'date; sleep 22; sleep 11; date',
#         'date',
#         'date',
#         './test.sh',
#         'dmesg' ]

def process_argparse():
    parser = argparse.ArgumentParser()
    parser.add_argument("commands", nargs="*",
                        help="[optional] command(s) to be run including flags. use -i for multiple instances. " +
                             "use -s for bwatch scripts instead")
    parser.add_argument("-n", "--interval", dest="interval", type=int,
                        metavar="<sec>",
                        help="interval in seconds, no min, default = 1")
    parser.add_argument("-d", "--duration", dest="duration", type=int,
                        metavar="<sec>",
                        help="quit after <sec> seconds")
    parser.add_argument("-x", "--not-precise", dest="imprecise", action="store_true",
                        help="-i seconds inserted between frames, no dropped frames. without this flag, precise is " +
                             "used and each frame is exactly -i seconds apart, frame is dropped if not fast enough")
    parser.add_argument("-p", "--plain", dest="plain", action="store_true",
                        help="do not highlight any changes")
    parser.add_argument("-i", "--instances", dest="instances", nargs="*",
                        metavar="<$1>",
                        help="run a seperate instance of command or script, and replace $1 with <$1> arguments, one " +
                             "argument per instance. see readme for details")
    parser.add_argument("-s", "--scripts", dest="scripts", nargs="*",
                        metavar="<scr>",
                        help="bwatch script(s) to be run, in addition to any commands")
    parser.add_argument("-a", "--default-scripts", dest="default_scripts", action="store_true",
                        help="also run scripts from the default folder, ./watch.d or ../watch.d or ~/watch.d")
    parser.add_argument("-o", "--override", dest="override", action="store_true",
                        help="bwatch scripts read settings flags from inside the script itself, use command " +
                             "line flags instead if a flag is specified")
    args = parser.parse_args()
    return args

class Bwatch:

    def initbwatch(self):
        self.args = process_argparse()

        self.settings_from_flags = {"instances" : self.args.instances,
                                   "interval" : self.args.interval,
                                   "duration" : self.args.duration,
                                   "imprecise" : self.args.imprecise,
                                   "plain" : self.args.plain,
                                   }
        self.load_commands_from_flags()
        self.load_commands_from_script_flag()
        self.load_commands_from_default_folder()

        if len(Commands.commands) == 0:
            #TO DO improve
            print("no commands or scripts found")

        #start_procs()

    def load_commands_from_flags(self):
        # load commands and settings from command line into Commands class instance(s)
        if self.args.commands:
            for item in self.args.commands:
                c = Commands(command = item, command_type="command")
                try:
                    c.set_all_settings(**self.settings_from_flags)
                except (TypeError, ValueError, OverflowError):
                    # TO DO handel error
                    print("1 type error")
                c.init_command()

    def load_commands_from_script_flag(self):
        # load commands and settings from a bwatch script via command line script flag into Commands class instance(s)
        if self.args.scripts:
            for item in self.args.scripts:
                scripts = process_folder_script_path(item)
                for script in scripts:
                    try:
                        c = Commands(command = script, command_type="script")
                        c.set_all_settings_from_script()
                        if self.args.override:
                        # override flag to use settings from command line flags instead of from the script itself
                                c.set_all_settings(**self.settings_from_flags)
                    except (TypeError, ValueError, OverflowError):
                        # TO DO file handling error
                        print("2 type error")

    def load_commands_from_default_folder(self):
        # load commands and settings from the default bwatch folder into Commands class instance(s)
        if (not self.args.commands and not self.args.scripts) or self.args.default_scripts:
            scripts = self.load_default_folder()
            if scripts:
                for script in scripts:
                    try:
                        c = Commands(command = script, command_type="script")
                        c.set_all_settings_from_script()
                        if self.args.override:
                        # override flag to use settings from command line flags instead of from the script itself
                                c.set_all_settings(**self.settings_from_flags)
                    except (TypeError, ValueError, OverflowError):
                        # TO DO file handling error
                        print("3 type error")

    def process_folder_script_path(self, file_object):
        scripts = []
        file_object = os.path.abspath(file_object)
        if os.path.exists(file_object) is True:
            if os.path.isdir(file_object) is True:
                scripts = self.get_scripts_from_directory(file_object)
            else:
                scripts.append(file_object)
        return scripts

    def get_scripts_from_directory(self, directory):
        scripts = []
        if os.path.exists(directory) and os.path.isdir(directory):
            ls = os.listdir(directory)
            for item in ls:
                for scripts_type in Settings.scripts_types:
                    if not item.startswith(".") and not item.endswith(Settings.app) and item.endswith(scripts_type):
                        scripts.append(os.path.join(directory, item))
        return scripts

    def load_default_folder(self):
        scripts = []
        for path in Settings.scripts_path:
            # walk through all possible paths, grab scripts from the first one that exists
            path = os.path.join(path, Settings.scripts_folder)
            d1 = os.path.abspath(os.path.join(Settings.cwd, path))
            d2 = os.path.expanduser(path)
            if os.path.isdir(d1):
                scripts = self.get_scripts_from_directory(d1)
                break
            elif os.path.isdir(d2):
                scripts = self.get_scripts_from_directory(d2)
                break
        return scripts

    def curses_color_setup(self):
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_RED)

    def start_curses(self):
        stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        stdscr.keypad(True)
        return stdscr

# ----------------------------------------------------------------------------------------------------------------------
#       Master Controller
# ----------------------------------------------------------------------------------------------------------------------

class Controller:

    def __init__(self):
        self.event_queues = []
        self.draw_queues = []
        self.frame_queues = []

        self.processes_frame = []
        self.processes_frame_generator = []
        self.processes_draw = []

        self.commands = []

    def start_draw_proc(self):
        pass

    def something(self):
        frame_controller_seed = FrameControllers()
        Settings.window_id.append(x)


    def start_frame_proc(self, command):
        command.event_queues = multiprocessing.Queue(1)

        self.process_frame.append("")

        self.process_frame[x] = multiprocessing.Process(
            target=frame_controller_seed.frame_controller,
            args=(
                Settings.commands[x],
                Settings.intervals[x],
                Settings.start_all[x],
                Settings.precision[x],
                Settings.window_id[x],
                Settings.draw_window_id,
                Procs.event_queues[x],
            ))

for x in range(Settings.commands_count):
    Procs.process_frame_controllers[x].start()

class Procs:

    def __init__(self):
        event_queues = []
        process_frame_controllers = []
        process_event_controller = []


        draw_frame_procs = []
        frame_procs = []
        frame_generator_procs = []

    def start_key_press_process(self):
        self.process_key_press = multiprocessing.Process(
            target=self.key_press,
            args=(
            ))

    def start_draw_frame_proc(self):
        pass

    def start_frame_proc(self):

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

        frame_controller_seed = FrameControllers()
        for x in range(Settings.commands_count):
            # result, error = run_linux4(Settings.Settings.x])
            # print(len(result))
            # sys.exit()

            Settings.window_id.append(x)
            Debug.debug("state_timeout")
            Procs.event_queues.append("")
            Procs.process_frame_controllers.append("")


            Procs.event_queues[x] = multiprocessing.Queue(1)
            Procs.process_frame_controllers[x] = multiprocessing.Process(
                target=frame_controller_seed.frame_controller,
                args=(
                    Settings.commands[x],
                    Settings.intervals[x],
                    Settings.start_all[x],
                    Settings.precision[x],
                    Settings.window_id[x],
                    Settings.draw_window_id,
                    Procs.event_queues[x],
                ))

        for x in range(Settings.commands_count):
            Procs.process_frame_controllers[x].start()

        if True:
            Procs.process_event_controller = multiprocessing.Process(
                target=event_controller,
                args=(
                    stdscr,
                    Settings.draw_window_id,
                    Procs.event_queues,
                ))
            Procs.process_event_controller.start()
        Debug.debug("aaaaaa event start", 1)

        time.sleep(Settings.stop - Settings.start)

    def start_frame_generator_proc(self):
        pass


def event_controller(window, draw_window_id, event_queues):
    Debug.debug("event start", 1)
    try:
        #keystroke = "1"
        while True:
            if Settings.curses is True:
                keystroke = window.getch()
                try:
                    keystroke = chr(keystroke)
                except ValueError:
                    keystroke = ""
            else:
                time.sleep(2)
                keystroke = "1" if keystroke == "2" else "2"

            try:
                new_win = int(keystroke) - 1
                if new_win != draw_window_id:
                    event_queues[draw_window_id].put(("window change",new_win,"close"))
                    draw_window_id = new_win
                    time.sleep(.1)
                    event_queues[draw_window_id].put(("window change",new_win,"new"))
            except ValueError:
                pass

    except KeyboardInterrupt:
        pass


# ----------------------------------------------------------------------------------------------------------------------
#       Objects
# ----------------------------------------------------------------------------------------------------------------------

class Events:
    pass


class Windows:

    def __init__(self, window_id, mode):
        self.window_id = window_id
        self.presentation_mode = mode
        self.frame_queue = frame_queue
        self.heatmap_queue = heatmap_queue
        self.draw_event_queue = draw_event_queue
        self.frame_event_queue = frame_event_queue



    def draw_window2(window, frame_queue, heatmap_queue, draw_event_queue):
        """ draw the most recent frame
        """

        try:
            custom_height = 9999
            custom_width = 9999

            while True:
                draw_event = draw_event_queue.get()
                Debug.debug("d1")

                if Settings.curses is False:
                    # don't use curses
                    Debug.debug("d2")
                    frame = frame_queue.get()
                    Debug.debug("d3")
                    heatmap = heatmap_queue.get()
                    #subprocess.Popen("clear").communicate()
                    #print("\n".join(frame))
                    #print("\n".join(heatmap))
                    continue

                frame = frame_queue.get()
                heatmap = heatmap_queue.get()

                window.clear()

                terminal_height, terminal_width = window.getmaxyx()

                draw_height = min(len(frame), terminal_height - 1, custom_height - 1)
                width = min(terminal_width, custom_width)

                #window.addstr(str(timeit.default_timer()))

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


class Commands:
    start_all = None
    stop_all = None
    commands = []

    def __init__(self, command, command_type):
        self.command_orig = command
        self.command = None
        self.command_type = command_type

        #run settings
        self.run_settings = {}
        self.interval = Defaults.interval
        self.duration = Defaults.duration
        self.imprecise = Defaults.imprecise
        self.plain = Defaults.plain
        self.instances = None

        self.start = None
        self.stop = None
        #self.window_id = []
        self.draw_window_id = 0

        self.frame_process = None
        self.frame_generator_process = None
        self.frame_event_queue = None
        self.frame_queue = None
        self.heatmap_queue = None
        self.all_window_event_queues = None



        Commands.commands.append(self)

    def test_print(self):
        print(self.command_orig)
        print(self.command)
        print(self.command_type)
        print("")
        print(self.interval)
        print(self.duration)
        print(self.imprecise)
        print(self.plain)
        print(self.instances)
        print("")
        print(type(self.interval))
        print(type(self.duration))
        print(type(self.imprecise))
        print(type(self.plain))
        print(type(self.instances))

    def set_all_settings(self,instances=None,interval=None,duration=None,imprecise=None,plain=None):
        self.instances = self.set_instances(instances)
        self.interval = self.set_interval(interval) if interval else self.interval
        self.duration = self.set_duration(duration) if duration else self.duration
        self.imprecise = self.set_imprecise(imprecise) if imprecise else self.imprecise
        self.plain = self.set_plain(plain) if plain else self.plain

    def set_all_settings_from_script(self):
        temp_settings = {"instances":None,"interval":None, "duration":None, "imprecise":None, "plain":None}

        with open(self.command_orig) as file:
            lines = file.read().splitlines()

        for line in lines:
            for key in temp_settings:
                if line.startswith(key + "=") and temp_settings[key] is None:
                    result, error = run_linux(line + " ; echo $" + key)
                    #TO DO evaluate error
                    temp_settings[key] = result.rstrip("\n")

        self.set_all_settings(**temp_settings)

    def set_instances(self, instances):
        min_instances, max_instances = 0, 21
        instances = str(instances).split(" ")
        if len(instances) < min_instances or len(instances) >= max_instances:
            #TO DO change this to a custom error
            raise ValueError
        return instances

    def set_interval(self, interval):
        lower_range, upper_range = 0, float("inf")
        interval = float(interval)
        if interval < lower_range or interval >= upper_range:
            raise ValueError
        return interval

    def set_duration(self, duration):
        lower_range, upper_range = 1, float("inf")
        duration = int(duration)
        if duration < lower_range or duration >= upper_range:
            raise ValueError
        return duration

    def set_imprecise(self, imprecise):
        imprecise = bool(imprecise)
        return imprecise

    def set_plain(self, plain):
        plain = bool(plain)
        return plain

    def init_command(self):
        #TO DO set subcommands, instances
        pass

    def init_script(self):
        #TO DO set subcommands, instances
        pass


class Frames:
    """This is the main controlling class.

    Frames are the collection of the stdout (or stderr) of the target command or script. If the target command
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
    #delete instances = []

    def __init__(self):
        """ As this class will be isolated in a multiprocess process, most fields are initialized in the
        self.controller() function, only the storage fields are defined here"""
        # class fields
        #delete FrameControllers.instances.append(self)
        #delete self.command_id = len(FrameControllers.instances) - 1

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
        self.generator_event_queue = multiprocessing.Queue(1)
        self.process_generator = multiprocessing.Process(
            target=self.generator_seed.generator_controller,
            args=(
                self.command,
                self.interval,
                self.start,
                self.precision,
                self.generator_frame_queue,
                self.generator_heatmap_queue,
                self.generator_event_queue,
                self.event_queue
            ))

    def initialize_draw_window_childprocess(self):
        # window fields
        self.window = None
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
        self.draw_event_queue = multiprocessing.Queue(1)
        self.process_draw_window = multiprocessing.Process(
            target=self.draw_window,
            args=(
                self.window,
                self.draw_frame_queue,
                self.draw_heatmap_queue,
                self.draw_event_queue
            ))

    def initialize_all_childprocesses(self):
        self.initialize_generator_childprocess()
        self.initialize_draw_window_childprocess()

    def start_all_childprocesses(self):
        self.process_generator.start()
        self.process_draw_window.start()

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

    def frame_controller(self, command, interval, start, precision, window_id, draw_window_id, event_queue):
        """ This is the main method that will control the input, output, and storage of the frame and heatmap data.
        After initializing the fields, this method will simply wait for a the generator child subprocess to put a new
        frame and heatmap into the appropriate queues, which are then sent on to the draw window and file write child
        subprocesses. Note, all interval timing is done in the generator child subprocess.
            generator child --["generator"]--> event queue (let's us know a new frame is available)
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
        self.window_id = window_id
        self.draw_window_id = draw_window_id
        self.event_queue = event_queue
        self.event = None
        self.key_press = None
        self.presentation_mode = "live"
        self.current = 0

        # start sub-processes
        self.process_generator = None
        self.process_draw_window = None
        self.initialize_all_childprocesses()
        self.start_all_childprocesses()

        self.event_choices = {
            "new frame" : self.process_new_frame,
            "window change" : self.window_change,
        }
        try:
            while True:
                # this controller queue get is blocking, so just wait for the a new frame or a message from key_press
                self.event = self.event_queue.get()
                self.event_choices.get(self.event[0], "")()
        except KeyboardInterrupt:
            # the controller method runs as a separate process and is killed either by a ctrl-c or a term_sig 2
            # poison pill / process.terminate is not used
            self.terminate_childprocesses()

    def process_new_frame(self):
        self.new_frame()
        self.frame_state[self.current] = self.event[1]
        self.heatmap_state[self.current] = self.event[2]
        self.frame_run_time[self.current] = self.event[3]
        self.frame_completion_time[self.current] = self.event[4]
        self.store_frame()
        self.store_heatmap()
        self.write_frame()
        self.draw_live_frame()

    def window_change(self):
        self.draw_window_id = self.event[1]
        if self.event[2] == "new":
            self.draw_live_frame()

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
        Debug.debug("self.current: " + str(self.current))

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
                Debug.debug("dropped in frame")
                self.frame_state[self.current] = "dropped"
                self.heatmap_state[self.current] = "dropped"
                self.frame_pointer[self.current] = self.frame_pointer[self.current - 1]
            else:
                self.frame_pointer[self.current] = self.current
        elif self.frame_state[self.current] == "unchanged":
            self.frame_pointer[self.current] = self.frame_pointer[self.current - 1]
        elif self.frame_state[self.current] == "dropped":
            self.frame_pointer[self.current] = self.frame_pointer[self.current - 1]
            Debug.debug("dropped")

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
            Debug.debug("dropped")
        elif self.heatmap_state[self.current] == "ignored":
            self.heatmap_pointer[self.current] = self.heatmap_pointer[self.current - 1]

    def write_frame(self):
        pass

    def draw_live_frame(self):
        Debug.debug("ddd 1")
        if self.presentation_mode == "live" and self.window_id == self.draw_window_id:
            Debug.debug(str(self.window_id) + "ww:" + str(self.draw_window_id))
            Debug.debug("ddd 2")
            self.draw_event_queue.put("draw")
            self.draw_frame_queue.put(self.frame[self.frame_pointer[-1]])
            self.draw_heatmap_queue.put(self.heatmap[self.heatmap_pointer[-1]])
        if self.presentation_mode == "playback":
            pass

    def draw_window(self, window, frame_queue, heatmap_queue, draw_event_queue):
        """ draw the most recent frame
        """

        try:
            custom_height = 9999
            custom_width = 9999

            while True:
                draw_event = draw_event_queue.get()
                Debug.debug("d1")

                if Settings.curses is False:
                    # don't use curses
                    Debug.debug("d2")
                    frame = frame_queue.get()
                    Debug.debug("d3")
                    heatmap = heatmap_queue.get()
                    #subprocess.Popen("clear").communicate()
                    #print("\n".join(frame))
                    #print("\n".join(heatmap))
                    continue

                frame = frame_queue.get()
                heatmap = heatmap_queue.get()

                window.clear()

                terminal_height, terminal_width = window.getmaxyx()

                draw_height = min(len(frame), terminal_height - 1, custom_height - 1)
                width = min(terminal_width, custom_width)

                #window.addstr(str(timeit.default_timer()))

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
    def generator_controller(self, command, interval, start, precision, frame_queue, heatmap_queue,
                   generator_event_queue, event_queue):
        self.command = command
        self.interval = interval
        self.start = start
        self.precision = precision
        self.frame_queue = frame_queue
        self.heatmap_queue = heatmap_queue
        self.generator_event_queue = generator_event_queue
        self.event_queue = event_queue
        self.command_gid = None
        self.generator_event = None

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
                    self.generator_event = generator_event_queue.get(timeout=sleep_time)
                except multiprocessing.queues.Empty:
                    pass
                else:
                    pass

                if self.precision is True and self.first_run is False and sleep_time == 0:
                    self.dropped()
                    Debug.debug("dropped in generator 1")
                else:
                    Debug.debug("starting frame generator: ")
                    self.frame_generator()
                    if self.frame_state != "dropped":
                        Debug.debug("starting heatmap generator: ")
                        self.heatmap_generator()

                Debug.debug("starting put_queues generator: ")
                self.put_queues()
                Debug.debug("ending put_queues generator: ")

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
                Debug.debug("gggggt2")
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
        Debug.debug("q1")
        Debug.debug("gen command_gid: " + str(self.command_gid))
        if self.heatmap_state == "changed":
            Debug.debug("q1.1")
            self.heatmap_queue.put(self.heatmap[self.current])
            Debug.debug("q1.2")
        elif self.heatmap_state == "dropped":
            pass
        elif self.heatmap_state == "ignore":
            pass
        elif self.heatmap_state == "unchanged":
            pass
        Debug.debug("q2")

        if self.frame_state == "changed":
            self.frame_queue.put(self.frame[self.current])
            self.flip_pointers()
        elif self.frame_state == "dropped":
            pass
        elif self.frame_state == "unchanged":
            self.flip_pointers()
        Debug.debug("q3")

        self.event_queue.put((
            "new frame",
            self.frame_state,
            self.heatmap_state,
            self.run_time,
            self.completion_time
        ))

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
        Debug.debug("gen command_gid: " + str(self.command_gid))

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
        # python 2 Popen returns a string, python 3 returns bytecode, so handle both here
        # TO DO incorporate error
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

# ----------------------------------------------------------------------------------------------------------------------
#       Terminate
# ----------------------------------------------------------------------------------------------------------------------


def terminate_processes():
    time.sleep(.15)
    procs = Procs.process_frame_controllers + [Procs.process_event_controller]
    for proc in procs:
        if proc.exitcode is None:
            term_sig = 2
            os.kill(proc.pid, term_sig)
    time.sleep(.2)
    for proc in procs:
        proc.terminate()

def terminate_curses():
    curses.echo()
    curses.nocbreak()
    curses.curs_set(1)
    curses.endwin()


# ----------------------------------------------------------------------------------------------------------------------
#       General Functions
# ----------------------------------------------------------------------------------------------------------------------

def run_linux(command):
    result, error = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True
        ).communicate()
    try:
        result = result.decode()
    except AttributeError:
        result = str(result)
    try:
        error = error.decode()
    except AttributeError:
        error = str(error)
    return result, error

# ----------------------------------------------------------------------------------------------------------------------
#       Start
# ----------------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":

    # noinspection PyPep8
    terminate = True
    try:
        terminate = False #TEMP take out
        bwatch = Bwatch()
        bwatch.initbwatch()
    except KeyboardInterrupt:
        print("")
        terminate = False
    finally:
        if terminate is True:
            terminate_processes()
        if Settings.curses is True:
            terminate_curses()