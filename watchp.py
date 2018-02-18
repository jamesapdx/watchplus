#!/usr/bin/python

import curses, sys, os, time, subprocess

def run_linux(cmd):
    result, err = subprocess.Popen(
                                cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE
                                ).communicate()
    return result, err
                

def main(stdscr):
    pass


stdscr = curses.initscr()
curses.noecho()
curses.cbreak()
stdscr.keypad(True)

done = False
try:
    main(stdscr)
except:
    curses.echo()
    curses.nocbreak()
    curses.endwin()
    done = True
    raise

if done is not True:
    curses.echo()
    curses.nocbreak()
    curses.endwin()

