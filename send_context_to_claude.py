#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Send a conversation (CSV with columns: role,content) to Anthropic Claude Messages API.

Usage:
  python send_claude_from_csv.py --csv path/to/conversation.csv \
      --system "You are a Real Estate SDR. Read these messages and suggest a follow-up message on the lead." \
      --model "claude-sonnet-4-20250514" \
      --max-tokens 2048 \
      --temperature 0.3

Environment:
  ANTHROPIC_API_KEY must be set.
"""
import argparse
import csv
import datetime
import json
import os
import sys
import time
from typing import List, Dict, Any

import requests


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"  # Messages API version
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


def read_messages_from_csv(csv_path: str) -> List[Dict[str, Any]]:
    """
    Read a CSV with columns ["role","content"] and return a list of
    Claude Messages API message dicts: {"role":"user|assistant","content":"..."}
    - Skips empty content rows.
    - Normalizes role to 'user' or 'assistant' (defaults to 'user' if unknown).
    """
    messages: List[Dict[str, Any]] = []

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        # Validate required columns
        expected_cols = {"role", "content"}
        if not expected_cols.issubset({(h or "").strip().lower() for h in reader.fieldnames or []}):
            raise ValueError(
                f"CSV must contain columns: {sorted(expected_cols)}; got {reader.fieldnames}"
            )

        for row in reader:
            role_raw = (row.get("role") or "").strip().lower()
            content = (row.get("content") or "").strip()

            if not content:
                continue

            role = "assistant" if role_raw == "assistant" else "user"  # default unknown to 'user'

            messages.append({"role": role, "content": content})

    if not messages:
        raise ValueError("No messages found in CSV (after skipping empty rows).")

    return messages


def build_payload(messages: List[Dict[str, Any]], system: str, model: str,
                  max_tokens: int, temperature: float | None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    return payload


def call_anthropic(payload: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.getenv("AT_KEY")
    if not api_key:
        raise EnvironmentError("Missing ANTHROPIC_API_KEY environment variable.")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }

    resp = requests.post(ANTHROPIC_API_URL, headers=headers, data=json.dumps(payload), timeout=60)
    try:
        data = resp.json()
    except Exception:
        resp.raise_for_status()
        raise  # if no JSON and no HTTP error, bubble up

    if resp.status_code >= 400:
        # Pretty-print API errors
        raise RuntimeError(json.dumps(data, indent=2, ensure_ascii=False))

    return data


def call_gpt(messages: List[Dict[str, Any]], system: str, model: str = "gpt-4o",
             max_tokens: int = 2048, temperature: float = 0.0) -> Dict[str, Any]:
    api_key = os.getenv("OAI_KEY")
    if not api_key:
        raise EnvironmentError("Missing OPENAI_API_KEY environment variable.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Convert messages format and add system message
    openai_messages = [{"role": "system", "content": system}]
    openai_messages.extend(messages)

    payload = {
        "model": model,
        "messages": openai_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    resp = requests.post(OPENAI_API_URL, headers=headers, data=json.dumps(payload), timeout=60)
    try:
        data = resp.json()
    except Exception:
        resp.raise_for_status()
        raise  # if no JSON and no HTTP error, bubble up

    if resp.status_code >= 400:
        # Pretty-print API errors
        raise RuntimeError(json.dumps(data, indent=2, ensure_ascii=False))

    return data


def pretty_print_response(claude_data: Dict[str, Any], gpt_data: Dict[str, Any], 
                         claude_payload: Dict[str, Any], gpt_payload: Dict[str, Any], 
                         export_json: bool = True, csv_filename: str = None) -> None:
    """
    Prints both Claude and GPT responses and exports all data to JSON files.
    """
    # Extract Claude response
    claude_content_blocks = claude_data.get("content", [])
    claude_text_chunks = []
    for block in claude_content_blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            claude_text_chunks.append(block.get("text", ""))
    claude_text = "\n".join([t for t in claude_text_chunks if t])

    # Extract GPT response
    gpt_choices = gpt_data.get("choices", [])
    gpt_text = ""
    if gpt_choices:
        gpt_text = gpt_choices[0].get("message", {}).get("content", "")

    print("\n=== Claude Reply ===\n")
    print(claude_text.strip() or "(no text content)")
    print("\n=== GPT Reply ===\n")
    print(gpt_text.strip() or "(no text content)")
    print("\n=======================\n")

    # Export to JSON files in claude_answers folder
    if export_json:
        import datetime
        from pathlib import Path
        
        # Create claude_answers directory
        output_dir = Path("ai_answers")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Include CSV filename in the export filename if provided
        file_prefix = ""
        if csv_filename:
            # Remove .csv extension and clean up filename
            clean_name = Path(csv_filename).stem.replace(" ", "_")
            file_prefix = f"{clean_name}_"
        
        # Export combined data with both AI responses
        combined_filename = output_dir / f"{file_prefix}ai_combined_{timestamp}.json"
        combined_data = {
            "timestamp": timestamp,
            "source_csv": csv_filename,
            "claude": {
                "payload": claude_payload,
                "response": claude_data
            },
            "gpt": {
                "payload": gpt_payload,
                "response": gpt_data
            }
        }
        with open(combined_filename, "w", encoding="utf-8") as f:
            json.dump(combined_data, f, indent=2, ensure_ascii=False)
        
        print(f"Combined AI responses exported to: {combined_filename}")

    # If you want to see the full JSON, uncomment:
    # print(json.dumps(claude_data, indent=2, ensure_ascii=False))
    # print(json.dumps(gpt_data, indent=2, ensure_ascii=False))


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Send CSV conversation to Claude Messages API")
    parser.add_argument("--folder", default="/Users/renantardelli/pilar/data/conversas_whatsapp/context", help="Path to folder containing CSV files with columns: role,content")
    parser.add_argument("--system", default="You are an AI agent writing one-line follow-up messages for real estate leads contacted 24+ hours ago; always output a message—be concise, clear, professional, re-engage with a question or new info, no emojis, no system text, no silence.",
                        help="System prompt")
    parser.add_argument("--model", default="claude-sonnet-4-20250514", help="Claude model name")
    parser.add_argument("--max-tokens", type=int, default=2048, help="Max tokens for the reply")
    parser.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only build and print the payload, do not call the API")

    args = parser.parse_args(argv)

    # Get all CSV files in the folder
    from pathlib import Path
    folder_path = Path(args.folder)
    
    if not folder_path.exists():
        print(f"Error: Folder does not exist: {folder_path}", file=sys.stderr)
        return 1
    
    csv_files = list(folder_path.glob("*.csv"))
    
    if not csv_files:
        print(f"No CSV files found in folder: {folder_path}", file=sys.stderr)
        return 1
    
    print(f"Found {len(csv_files)} CSV files to process in: {folder_path}")
    
    # Process each CSV file
    for csv_file in csv_files:
        print(f"\n{'='*50}")
        print(f"Processing: {csv_file.name}")
        print(f"{'='*50}")
        
        try:
            messages = read_messages_from_csv(str(csv_file))
        except Exception as e:
            print(f"Error reading CSV {csv_file.name}: {e}", file=sys.stderr)
            continue  # Skip this file and continue with others

        payload = build_payload(messages, args.system, args.model, args.max_tokens, args.temperature)

        if args.dry_run:
            print(f"Payload for {csv_file.name}:")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            continue

        try:
            # Call both Claude and GPT
            print("Calling Claude API...")
            claude_data = call_anthropic(payload)
            
            print("Calling GPT API...")
            gpt_data = call_gpt(messages, args.system, "gpt-4o", args.max_tokens, args.temperature)
            
            # Create GPT payload for export
            gpt_payload = {
                "model": "gpt-4o",
                "messages": [{"role": "system", "content": args.system}] + messages,
                "max_tokens": args.max_tokens,
                "temperature": args.temperature,
            }
            
        except Exception as e:
            print(f"API error for {csv_file.name}: {e}", file=sys.stderr)
            continue  # Skip this file and continue with others

        pretty_print_response(claude_data, gpt_data, payload, gpt_payload, csv_filename=csv_file.name)
        
        # Sleep for 20 seconds to respect rate limits (skip for last file)
        if csv_file != csv_files[-1]:  # Don't sleep after the last file
            print(f"Waiting 20 seconds before processing next file...")
            time.sleep(20)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))