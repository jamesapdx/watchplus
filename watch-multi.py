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

""" order of things:
    load settings, defaults, debug as class variables (Settings, Defaults, Degub)
    load single instance of Bwatch to start everything
    Bwatch __init__:
        load args via argparse (func)
        start curses (self.start_curses())
        setup color for curses (self.curses_color_setup())

        setup the number of windows (similar to screen regions)
            store into class Windows
                self.load_windows_from_defaults()
                self.load_windows_from_flags()

        load the command values from three places (don't run them yet):
            store into class Commands
                self.load_commands_from_flags()
                self.load_commands_from_script_flag()
                self.load_commands_from_default_folder()
                
        start class Controller
        
    Controller __init__:
    
"""

# -- Settings ----------------------------------------------------------------------------------------------------------

class Settings:
    use_curses = True
    cooldown_ticks = 4
    cooldown_color_map = [0, 1] + ([2] * (cooldown_ticks + 1))

    scripts_types = [".py",".sh"]
    scripts_path = ["~/","../","."]
    scripts_folder = "bwatch.d"
    cwd = os.getcwd()
    app = os.path.basename(__file__)

    max_windows = 1
    max_instances = 20
    max_commands = 16

class Defaults:
    interval = 1
    duration = 0
    imprecise = False
    plain = False

class Debug:
    debug_level = 0
    debug_mode = False

    @classmethod
    def debug(cls, item, level=0):
        if Debug.debug_mode is True and Settings.curses is False and Debug.debug_level >= level:
            print(item)






# -- Args --------------------------------------------------------------------------------------------------------------

def process_argparse():
    parser = argparse.ArgumentParser()
    parser.add_argument("commands",
                        nargs="*",
                        help="[optional] command(s) to be run including flags. use -i for multiple instances. " +
                             "use -s for bwatch scripts and folders instead")
    parser.add_argument("-n",
                        "--interval",
                        dest="interval",
                        type=int,
                        metavar="<sec>",
                        help="interval in seconds, no min, default = 1")
    parser.add_argument("-d",
                        "--duration",
                        dest="duration",
                        type=int,
                        metavar="<sec>",
                        help="quit after <sec> seconds")
    parser.add_argument("-x",
                        "--not-precise", dest="imprecise",
                        action="store_true",
                        help="-n <seconds> inserted between frames, no dropped frames. without this flag, precise is " +
                             "used and each frame is exactly -n <seconds> apart and frames will be dropped if not fast enough")
    parser.add_argument("-p",
                        "--plain",
                        dest="plain",
                        action="store_true",
                        help="do not highlight any changes")
    parser.add_argument("-i",
                        "--instances",
                        dest="instances",
                        nargs="*",
                        metavar="<$1>",
                        help="run a seperate instance of command or script, replace $1 with <$1> arguments, one " +
                             "argument per instance. see readme for details")

    parser.add_argument("-s",
                        "--script",
                        dest="script",
                        metavar="<file|dir>",
                        help="load bwatch script or a folder containing one or more bwatch scripts")

#    parser.add_argument("-a",
#                        "--default-scripts",
#                        dest="default_scripts",
#                        action="store_true",
#                        help="also run scripts from the default folder, ./watch.d or ../watch.d or ~/watch.d")

    args = parser.parse_args()
    return args

# -- Init Bwatch -------------------------------------------------------------------------------------------------------

class Bwatch:

    def __init__(self):
        self.args = process_argparse()

        self.curses_stdscr = None
        self.start_curses()
        self.curses_color_setup()

        self.load_windows_from_defaults()
        self.load_windows_from_flags()

        self.load_commands_from_flags()
        self.load_commands_from_script_flag()

        # not using default folder for now
        # self.load_commands_from_default_folder()

        if len(Commands.commands) == 0:
            #TO DO improve
            print("no commands or scripts found")

    def load_commands_from_flags(self):
        # load commands and settings from command line into Commands class instance
        self.settings_from_flags = {"instances" : self.args.instances,
                                    "interval" : self.args.interval,
                                    "duration" : self.args.duration,
                                    "imprecise" : self.args.imprecise,
                                    "plain" : self.args.plain,
                                    }
        if self.args.commands:
            for item in self.args.commands:
                c = Commands(command = item, command_type="command")
                try:
                    c.set_all_settings(**self.settings_from_flags)
                except (TypeError, ValueError, OverflowError):
                    # TO DO handle error better
                    print("1 type error")
                c.init_command()

    def load_commands_from_script_flag(self):
        # load commands and settings from a bwatch script into Commands class instance
        # if single script, just use the script, if directory, use any eligible script in the directory
        if self.args.script:
            for item in self.args.script:
                scripts = self.process_folder_script_path(item)
                for script in scripts:
                    try:
                        c = Commands(command = script, command_type="script")
                        c.set_all_settings_from_script()
                        # if command line settings exist, use them instead
                        c.set_all_settings(**self.settings_from_flags)
                    except (TypeError, ValueError, OverflowError):
                        # TO DO file handling error
                        print("2 type error")

    def load_commands_from_default_folder(self):
        # not using this function for now
        # load commands and settings from the default bwatch folder into Commands class instance(s)
        if (not self.args.commands and not self.args.scripts) or self.args.default_scripts:
            scripts = self.load_default_folder()
            if scripts:
                for script in scripts:
                    try:
                        c = Commands(command = script, command_type="script")
                        c.set_all_settings_from_script()
                        # if command line settings exist, use them instead
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

    def start_curses(self):
        self.curses_stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        self.curses_stdscr.keypad(True)

    def curses_color_setup(self):
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_RED)

    def load_windows_from_defaults(self):
        for x in range(Settings.max_windows):
            Windows()

    def load_windows_from_flags(self):
        pass

# -- Master Controller -------------------------------------------------------------------------------------------------

class Controller:

    def __init__(self):
        self.draw_event_queues = []
        self.draw_transfer_queues = []

        self.frame_event_queues = []
        self.frame_transfer_queues = []
        self.heatmap_transfer_queues = []

        self.processes_frame_controller = []
        self.processes_frame_generator = []
        self.processes_draw = []
        self.processes_draw_controller = []

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

        self.draw_event_queues = []
        self.draw_frame_queues = []
        self.draw_heatmap_queues = []

        self.frame_event_queues = []
        self.frame_queues = []
        self.heatmap_queues = []

        self.processes_frame_controller = []
        self.processes_frame_generator = []
        self.processes_draw = []
        self.processes_draw_controller = []

    def start_key_press_process(self):
        self.process_key_press = multiprocessing.Process(
            target=self.key_press,
            args=(
            ))

    def initial_start_draw_procs(self):
        for window in Windows.windows:
            self.start_draw_frame_proc(window.window)

    def start_draw_frame_proc(self, window):
        self.draw_frame_queue.append(multiprocessing.Queue(1))
        self.draw_heatmap_queue.append(multiprocessing.Queue(1))
        self.draw_event_queue.append(multiprocessing.Queue(1))

        self.draw_window_procs = multiprocessing.Process(
            target=window.draw_window,
            args=(
                window,
                self.draw_event_queue[-1],
                self.draw_frame_queue[-1],
                self.draw_heatmap_queue[-1]
            ))

    def initial_start_frame_and_frame_generator_procs(self):
        Settings.start = timeit.default_timer()
        Settings.stop = Settings.start + Settings.duration
        Settings.start_all = [Settings.start] * Settings.commands_count
        Settings.key = Settings.start

        frame_controller_seed = FrameControllers()

        for command in Commands.commands:
            self.start_fra


    def start_frame_and_frame_generator_proc(self):


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


# -- Objects -----------------------------------------------------------------------------------------------------------

class Events:
    pass


class Windows:
    windows = []

    def __init__(self,height=0,width=0,v_position=0,h_position=0,x_position=0,y_position=0):
        self.curses_window = None
        self.heigth = height
        self.width = width
        self.v_position = v_position
        self.h_position = h_position
        self.x_position = x_position
        self.y_position = y_position
        self.window_id = len(Windows.windows)
        Windows.windows.append(self)

        # create a new curses window
        if Settings.curses is True:
            self.curses_window = curses.newwin(self.heigth, self.width, self.v_position, self.h_position)
            self.curses_window.nodelay(0)
            self.curses_window.keypad(True)

    def draw_window(self, window, draw_event_queue, frame_queue, heatmap_queue):
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

    def draw_window2(self, window, frame_queue, heatmap_queue, draw_event_queue):
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

    Frames are the text output from a command or script, run every interval.
    Heatmaps are the highlighting that occurs when a character changes from one frame to the next.

    This class is utilized only inside a multiprocess subprocess, one subprocess for each target command or script.
    This subprocess receives a frame and heatmap from the FrameGenerator subprocess, stores them, and if needed sends
    the frame and heatmap to the draw subprosses. In playback mode, this subprocess will receive a request for a
    specific old frame and heatmap from the draw subprosess.
    """

    def __init__(self):
        # storage fields
        self.frame = []
        self.frame_pointer = []
        self.frame_state = []
        self.frame_run_time = []
        self.frame_completion_time = []
        self.heatmap = []
        self.heatmap_pointer = []
        self.heatmap_state = []
        self.current = 0

    def frame_controller(self, start, window_id, event_queue, draw_event_queues, draw_frame_queues, draw_heatmap_queues):
        """ This method will simply wait for a the FrameGenerator subprocess to put a new frame and heatmap
        into the appropriate queues, which are then sent on to the draw window and file write child
        subprocesses.
        """
        self.start = start
        self.window_id = window_id
        self.draw_window_id = draw_window_id
        self.event_queue = event_queue
        self.event = None
        self.key_press = None
        self.presentation_mode = "live"
        self.current = 0

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

# -- Terminate ---------------------------------------------------------------------------------------------------------


def terminate_processes():
    """ all child subprocoesses are killed with os - signal 2, not a flag or terminate.  This leads to a clean
    stop with no error messages in the case of a user control-c. User control-c are propagated to all
    subprocesses automatically on an OS level and are not controllable. """

    # wait a tad to let the child processes stop on their own in the case of user control-c.
    time.sleep(.15)
    procs = Procs.process_frame_controllers + [Procs.process_event_controller]
    for proc in procs:
        if proc.exitcode is None:
            term_sig = 2
            os.kill(proc.pid, term_sig)

    # just in case this doesn't work because of timing or otherwise, wait a bit and kill with process.terminate
    time.sleep(.2)
    for proc in procs:
        proc.terminate()

def terminate_curses():
    curses.echo()
    curses.nocbreak()
    curses.curs_set(1)
    curses.endwin()


# -- General Function -------------------------------------------------------------------------------------------------

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

# -- Start -------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":

    # noinspection PyPep8
    terminate = True
    try:
        terminate = False #TEMP take out
        bwatch = Bwatch()
    except KeyboardInterrupt:
        print("")
        terminate = False
    finally:
        if terminate is True:
            terminate_processes()
        if Settings.curses is True:
            terminate_curses()
