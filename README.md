# Watchplus
A better Linux watch command with advanced features.

[![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/)

# Feature Comparison
|                                                           | **watchplus** | **watch** |
|-----------------------------------------------------------|:-------------:|:---------:|
| Line wrapping                                             | :heavy_check_mark:       | :heavy_check_mark: |
| Precise mode                                              | :heavy_check_mark:       | :heavy_check_mark: |
| Show change history                                       | :heavy_check_mark:       | :heavy_check_mark: |
| **Multiple tabs running commands simultaneously**         | :heavy_check_mark:       | :x:                |
| **Pause, rewind and fast-forward.**                       | :heavy_check_mark:       | :x:                |
| **Scroll up and down with long output**                   | :heavy_check_mark:       | :x:                |
| **Follow new output, similar to tail -f**                 | :heavy_check_mark:       | :x:                |
| **Read commonly used commands from a file**               | :heavy_check_mark:       | :x:                |
| **Save, load, and distribute runs**                       | :heavy_check_mark:       | :x:                |
| **Support for streaming commands such as ping**           | :heavy_check_mark:       | :x:                |
| **Interactive commands while running**                    | :heavy_check_mark:       | :x:                |
| **Extensive use of multiprocessing for minimal overhead** | :heavy_check_mark:       | :x:                |

# Sample Screenshots

[![live](https://github.com/jamesapdx/watchplus/raw/master/screenshots/thumbnails/screenshot_1t.png)](https://github.com/jamesapdx/watchplus/raw/master/screenshots/screenshot_1.png)
[![paused](https://github.com/jamesapdx/watchplus/raw/master/screenshots/thumbnails/screenshot_2t.png)](https://github.com/jamesapdx/watchplus/raw/master/screenshots/screenshot_2.png)
[![live2](https://github.com/jamesapdx/watchplus/raw/master/screenshots/thumbnails/screenshot_3t.png)](https://github.com/jamesapdx/watchplus/raw/master/screenshots/screenshot_3.png)
[![paused2](https://github.com/jamesapdx/watchplus/raw/master/screenshots/thumbnails/screenshot_4t.png)](https://github.com/jamesapdx/watchplus/raw/master/screenshots/screenshot_4.png)

# Uses 

* Testing and validation: Capture results and bugs and share with developers.
* Troubleshooting software development: OS issues, Networking, etc. Capture the issue, review it, share it.
* System monitoring: capture log files, proc files, etc. and review the results any time later.

# Installation

Simply copy `watchplus` to location of your choice. `watchplus` is a single file, no installation needed.

# Startup Usage
Manually specify commands:
```python
watchplus "free -h" -- -b "dmesg" -- -s "ping 1.1.1.1" -- "top -b -n 1"
```
Use a command file:
```python
watchplus -f <sample_command_file>
```
Load a previously saved run:
```python
watchplus -o <run_file>
```
**See sample_command_file for more examples**

All command line options:
```
System options (applies to all tabs):
  -n <s>, --interval <s>  Interval in <seconds>, minimum .01, default = 1.0.
  -p, --precise           Attempt to maintain interval, drop frame if not completed in time.
  -v, --version           Show version number.
  -h, --help              Show this help.

Tab/Command options:
  --                      Separator for commands on command line. Not needed for the first one.
                          Example: watchplus -n 1 "dmesg" -- -s "ping -4 1.1.1.1" -- "nstat"
  -s, --streaming         Use with continual streaming commands such as tcpdump and ping.
  -b, --bottom            Start this tab at the bottom of the output, similar to follow option.
  -x, --change            Do not display change history. Can be toggled on/off with 'x'.
  -l, --line_wrap         Disable line wrap. Can be toggled on/off with 'l'.
  -g, --green             Use green text.
  -t <t>, --tab <t>       Assign this command to tab <t> if possible, 1-20.
  "command"               Command to be run, up to 20 allowed, each in in a separate tab.
                          Note: enclose in DOUBLE quotes with inside escaped quotes as needed.
```
# Interactive Usage
```
Playback controls (all tabs at once):
   Space ............................... Play | Pause  (does not stop recording)
   r ................................... Start | Stop recording Frames
   A a s | d f F ....................... 100 | 10 | 1 << >> 1 | 10 | 100  Frames
   Left | Right Arrows (ctrl, shift) ... 100 | 10 | 1 << >> 1 | 10 | 100  Frames
   w | e ............................... First << >> Last  Frames
Viewing controls:
   1-0, shift 1-0 ...................... Change tab
                                         1-0 = tab 1-10, shft-1-0 = tab 11-20
   k j ................................. Up | Down
   Up | Down Arrows .................... Up | Down
   Ctrl-u | Ctrl-d ..................... Half page up | down
   Ctrl-b | Ctrl-f ..................... Page up | down
   Page-Up | Page-Down ................. Page up | down
   g | G ............................... Top | Bottom
   x ................................... Toggle change history display on/off
   l ................................... Toggle line wrap
   ctrl-g .............................. Toggle green text
Other controls:
   ctrl-w .............................. Write frames and tabs to ~/[date_time].wp
                                         Stops recording during write. Load: -o <f>
   ctrl-h .............................. View this help and tab assignments
   ctrl-c .............................. Quit
```
