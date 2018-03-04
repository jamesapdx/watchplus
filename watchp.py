#!/usr/bin/python

import curses, sys, os, time, subprocess

def run_linux(cmd):
    result, err = subprocess.Popen(
                                cmd.split(" "),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE
                                ).communicate()
    return result, err

class Windows():
    master_windows = []

    def __init__(self, cmd, current_time):
        self.cmd = cmd
        self.creation_time = current_time
        self.frame_lines = []
        self.frame_columns = []
        self.frame_heatmap = []
        self.frame = []
        init_heatmap()
        init_frame()

    def create_frame(self):
        self.frame.append(run_linux(self.cmd))

    def init_heatmap(self):
        lines = [curses.LINES]
        columns = [curses.COLS]
        self.frame_lines.append(lines)
        self.frame_columns.append(columns)

    def init_frame():
        pass

    def new_heatmap(self):
        init_heatmap()
        frame_count = len(self.frame_lines)
        lines = [self.frame_lines[frame_count - 1], self.frame_lines[frame_count]]
        columns = [self.frame_columns[frame_count - 1], self.frame_columns[frame_count]]

    def display_frame(self):
        window_time = creation_time

        while true:

            columns = curses.COLS
            frame, error = run_linux("date")
            frame_lines = frame.splitlines()
            frame = (frame.strip("\n") + ("adf" * 60) + "\n") * 60
            stdscr.erase()
            self.create_heatmap()

            frame_lines = frame.splitlines()
            for line in range(lines):
                for column in range(columns - 1):
                    if line <= len(frame_lines) - 1:
                        if column <= len(frame_lines[line]) - 1:

                            print_char = frame_lines[line][column]
                            stdscr.addch(line,column,print_char)

            stdscr.refresh()


def main(stdscr):

    #clear frame_heatmap array
    #get term sizes
    #define history arry
    #new window, size to term sizes

    # while True:
    #     results = run linux command
    #     clear screen
    #
    #     check terminal size
    #         if not same
    #             set new sizes
    #             clear last result
    #             clear frame_heatmap array
    #             resize window
    #
    #     loop lines
    #         loop columns
    #             if now char != past char
    #                 set hot
    #             else if temp > 1
    #                 set temp - 1
    #
    #         write char
    #     refresh window
    #
    #     save results to history array
    #
    #     get char input
    #     user choices:
    #         quit
    #         pause(later)
    #         unpause(later)


    while True:
        lines = curses.LINES
        columns = curses.COLS
        frame, error = run_linux("date")
        frame = (frame.strip("\n") + ("adf" * 60) + "\n") * 60
        stdscr.erase()

        time.sleep(.02)
       # stdscr.refresh()

        frame_lines = frame.splitlines()
        for line in range(lines):
            for column in range(columns - 1):
                if line <= len(frame_lines) - 1:
                    if column <= len(frame_lines[line]) - 1:

                        print_char = frame_lines[line][column]
                        stdscr.addch(line,column,print_char)

        stdscr.refresh()


stdscr = curses.initscr()
curses.noecho()
curses.cbreak()
curses.curs_set(0)
curses.start_color()
stdscr.keypad(True)

def terminate_curses():
    curses.echo()
    curses.nocbreak()
    curses.curs_set(1)
    curses.endwin()


try:
    main(stdscr)
except:
    terminate_curses()
    raise

if curses.isendwin() is not True:
    terminate_curses()
