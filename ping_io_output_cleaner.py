#!/usr/bin/env python3
import sys, re, io, threading

def clean_stream_sync(input_stream: io.TextIOBase, output_stream: io.TextIOBase):
    outputRegex = re.compile(r"^\s?(RB: \d+, SB: \d+, TC: \d+, AC: \d+\s*)+$")
    exclude = ("Pseudo-terminal will not be allocated because stdin is not a terminal.", "You are not authenticated.")
    for line in input_stream:
        if outputRegex.match(line):
            continue
        if len(line) > 0 and line[-1] == "\n":
            lineCleaned = line[:-1]
            if len(lineCleaned) > 0 and lineCleaned[-1] == "\r":
                lineCleaned = lineCleaned[:-1]
        else:
            lineCleaned = line
        if lineCleaned not in exclude:
            print(line, end="", flush=True, file=output_stream)


def clean_stream_async(input_stream: io.TextIOBase, output_stream: io.TextIOBase, daemon: bool = True) -> threading.Thread:
    thread = threading.Thread(target=clean_stream_sync, args=(input_stream, output_stream), daemon=daemon)
    thread.start()
    return thread


if __name__ == "__main__":
    if not (isinstance(sys.stdin, io.TextIOBase) and isinstance(sys.stdout, io.TextIOBase)):
        raise TypeError(f"Expected sys.stdin and sys.stdout to be TextIOBase instances, but got:\nstdin type: {type(sys.stdin)} , stdin repr: {repr(sys.stdin)}\nstdout type: {type(sys.stdout)} , stdout repr: {repr(sys.stdout)}")
    clean_stream_sync(sys.stdin, sys.stdout)
