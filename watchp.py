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

    clear heat array
    get term sizes
    define history arry
    new window, size to term sizes
    
    while True:
        results = run linux command
        clear screen

        check terminal size
            if not same
                set new sizes
                clear last result
                clear heat array
                resize window
                
        loop lines
            loop columns
                if now char != past char
                    set hot
                else if temp > 1
                    set temp - 1

            write char
        refresh window
        
        save results to history array

        get char input
        user choices:
            quit
            pause(later)
            unpause(later)
        


    term_lines, term_columns = 0,0
    if term_lines, term_columns != curses.LINES, curses.COLS:
        term_lines, term_columns = curses.LINES, curses.COLS

    for line in range(term_lines - 1):
        for column in range(term_columns - 1):




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
