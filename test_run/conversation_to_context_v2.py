#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Parse WhatsApp-style exports like:
DD/MM/YYYY HH:MM - Sender: message
…including multi-line messages and system lines without a sender.
Writes a CSV with columns: date, time, sender, message.
"""

import re
import csv
import sys
import os

import unicodedata as _ud
from pathlib import Path

# -------- configuration --------
PATH = os.getcwd()
# INPUT_PATH = sys.argv[1] if len(sys.argv) > 1 else "chat.txt"
# OUTPUT_PATH = sys.argv[2] if len(sys.argv) > 2 else "chat_parsed.csv"

ASSISTANT_REFERENCE_DICT = {
    'Mavi – Mosaic': 'assistant' 
    }

# --------------------------------

# Regex for the start of a message block.
# Examples it should match:
# 24/07/2025 11:22 - As mensagens e ligações...
# 24/07/2025 11:22 - Mavi - Mosaic: Olá! ...

HEADER = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})\s+-\s(.*)",
    flags=re.MULTILINE
)

def get_files_names(path: str):
    p = Path(path)
    files = [f for f in p.iterdir() if f.is_file() and ('txt' in f.suffix)]
    return files

def split_sender_and_text(rest: str):
    """
    Try to split the 'Sender: message' part.
    If no colon, treat entire text as a system message (sender=None).
    """
    # Some names may contain " - " (e.g., "Mavi - Mosaic"), so we split on ': ' only.
    if ": " in rest:
        sender, msg = rest.split(": ", 1)
        # Handle lines that were just a header with nothing after the dash:
        if sender.strip() == "" and msg.strip() == "":
            return None, ""
        return sender.strip(), msg
    else:
        # Entire remainder is the message (system message / no sender)
        return None, rest

def parse_chat(text: str):
    """
    Yields dicts with date, time, sender, message (message may be multi-line).
    """
    messages = []
    # Find all header matches with their positions
    matches = list(HEADER.finditer(text))

    for i, m in enumerate(matches):
        date, time, rest = m.group(1), m.group(2), m.group(3)

        # The body goes from end of this match up to the start of the next header (or end of text)
        start_of_body = m.end()
        end_of_body = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        body = text[start_of_body:end_of_body]

        # The first line after the dash is already captured in 'rest' (same line as header).
        # Concatenate 'rest' (which may include "Sender: first line") with any following lines in 'body'.
        # Ensure we don't double-add a newline if body already starts with one.
        if body.startswith("\n"):
            full = f"{rest}{body}"
        else:
            # This covers cases where the header line ended exactly at EOL with no content
            full = f"{rest}\n{body}" if body else rest

        # Normalize Windows/Mac line endings but preserve message newlines
        full = full.replace("\r\n", "\n").replace("\r", "\n")

        # Trim only trailing newline that belongs to the block, not internal ones
        full = full.rstrip("\n")

        sender, msg = split_sender_and_text(full)

        # Clean up message whitespace while keeping intentional newlines
        # (strip only leading/trailing spaces around the whole block)
        msg = msg.strip()

        messages.append({
            "date": date,
            "time": time,
            "sender": sender,   # None for system messages
            "message": msg
        })

    return messages


def parse_to_context(messages: list):
    """
    Convert parsed messages to a AI context format.
    """
    context = []
    for message in messages:
        context.append({
            "role": ASSISTANT_REFERENCE_DICT.get(message["sender"], "user"),
            "content": message["message"]
        })
    return context

def write_messages_to_csv(rows, output_path):
    EXPECTED = ["date", "time", "sender", "message"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        # header
        w.writerow(EXPECTED)
        # linhas
        for r in rows:
            w.writerow([
                r.get("date", ""),
                r.get("time", ""),
                r.get("sender", ""),
                r.get("message", ""),
            ])
        print(f"Wrote {len(rows)} messages to {output_path}")

def write_context_to_csv(rows, output_path):
    EXPECTED = ["role", "content"]

    with open('context_' + output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        # header
        w.writerow(EXPECTED)
        # linhas
        for r in rows:
            w.writerow([
                r.get("role", ""),
                r.get("content", ""),
            ])
        print(f"Wrote {len(rows)} context messages to context_{output_path}")


def main():
    files = get_files_names(PATH)
    for file in files:
        print(f"Processing file: {file.name}")
        output_path = file.stem + "_parsed.csv"

        raw = file.read_text(encoding="utf-8-sig")
        rows = parse_chat(raw)
        context = parse_to_context(rows)

        write_messages_to_csv(rows, output_path)
        write_context_to_csv(context, output_path)


if __name__ == "__main__":
    main()


