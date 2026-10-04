#!/usr/bin/env python3
import sys, re

outputRegex = re.compile(r"^\s?(RB: \d+, SB: \d+, TC: \d+, AC: \d+\s*)+$")
exclude = ("Pseudo-terminal will not be allocated because stdin is not a terminal.", "You are not authenticated.")
for line in sys.stdin:
    if outputRegex.match(line):
        continue
    if len(line) > 0 and line[-1] == "\n":
        lineCleaned = line[:-1]
        if len(lineCleaned) > 0 and lineCleaned[-1] == "\r":
            lineCleaned = lineCleaned[:-1]
    else:
        lineCleaned = line
    if lineCleaned not in exclude:
        print(line, end="", flush=True)
