#!/usr/bin/env python3
"""
Deduplicate .po entries by (msgctxt, msgid).
Keeps the first occurrence and merges `#:` reference lines from duplicates into the kept entry.

Usage:
  python scripts/dedupe_po.py path/to/django.po        # dry-run, reports duplicates
  python scripts/dedupe_po.py -i path/to/django.po     # inplace edit (creates .bak)
  python scripts/dedupe_po.py -i --backup-ext .orig path/to/django.po

Notes:
- The script parses .po blocks separated by blank lines. It handles multiline msgid/msgstr.
- It preserves original order (keeps first occurrence) and merges references (#:).
- Make a git/OS backup before running with `-i` just in case.
"""

from __future__ import annotations
import argparse
import os
import re
import shutil
from typing import List, Tuple, Optional, Dict, Set


def split_blocks(lines: List[str]) -> List[List[str]]:
    blocks: List[List[str]] = []
    cur: List[str] = []
    for ln in lines:
        if ln.strip() == "":
            if cur:
                blocks.append(cur)
                cur = []
        else:
            cur.append(ln.rstrip("\n"))
    if cur:
        blocks.append(cur)
    return blocks


def extract_quoted(block: List[str], field: str) -> Optional[str]:
    # field like 'msgid' or 'msgstr' or 'msgctxt'
    for i, ln in enumerate(block):
        if ln.startswith(field):
            # capture initial quoted part on same line
            m = re.match(rf"{re.escape(field)}\s+\"(.*)\"", ln)
            parts = []
            if m:
                parts.append(m.group(1))
            # then subsequent continued lines starting with a quote
            j = i + 1
            while j < len(block) and block[j].lstrip().startswith('"'):
                mm = re.match(r'^\s*"(.*)"', block[j])
                if mm:
                    parts.append(mm.group(1))
                j += 1
            return ''.join(parts)
    return None


def collect_references(block: List[str]) -> List[str]:
    refs: List[str] = []
    for ln in block:
        if ln.startswith('#:'):
            rest = ln[2:].strip()
            if rest:
                refs.extend(rest.split())
    return refs


def replace_refs_in_block(block: List[str], refs: List[str]) -> List[str]:
    # Remove existing '#:' lines and insert one merged '#: ' line after initial comments
    new_block: List[str] = []
    inserted = False
    # Determine insertion index: after leading comment lines (#, #., #: etc) and msgctxt if present
    # We'll insert before the first non-comment (e.g., 'msgctxt' or 'msgid').
    for i, ln in enumerate(block):
        if ln.startswith('#'):
            continue
        # found first non-comment line; we will build new_block up to i then insert refs
        insert_at = i
        break
    else:
        insert_at = len(block)

    # copy leading comments except #: (we'll skip #: and insert merged)
    for i in range(insert_at):
        ln = block[i]
        if ln.startswith('#:'):
            continue
        new_block.append(ln)
    if refs:
        merged = ' '.join(sorted(set(refs)))
        new_block.append('#: ' + merged)
    # append the rest of the block excluding original '#:' lines
    for ln in block[insert_at:]:
        if ln.startswith('#:'):
            continue
        new_block.append(ln)
    return new_block


def block_to_text(block: List[str]) -> str:
    return '\n'.join(block) + '\n\n'


def dedupe_po(path: str, inplace: bool = False, backup_ext: str = '.bak', dry_run: bool = True) -> Tuple[int, int, Dict[str, List[int]]]:
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    blocks = split_blocks(lines)
    # key -> index of first occurrence
    seen: Dict[str, int] = {}
    # keep mapping for merging refs
    refs_map: Dict[int, Set[str]] = {}
    duplicates: Dict[str, List[int]] = {}

    for idx, block in enumerate(blocks):
        msgctxt = extract_quoted(block, 'msgctxt') or ''
        msgid = extract_quoted(block, 'msgid')
        if msgid is None:
            # weird block (maybe header comments); treat as unique
            key = f'__block_{idx}'
        else:
            key = msgctxt + '\x00' + msgid
        if key in seen:
            first = seen[key]
            duplicates.setdefault(key, []).append(idx)
            # collect refs to merge into first
            refs = collect_references(block)
            refs_map.setdefault(first, set())
            refs_map[first].update(refs)
        else:
            seen[key] = idx
            # initialize refs_map with existing refs of this block
            refs_map.setdefault(idx, set())
            refs_map[idx].update(collect_references(block))

    dup_count = sum(len(v) for v in duplicates.values())
    unique_kept = len(blocks) - dup_count

    if dry_run:
        print(f'Found {len(duplicates)} duplicated msgid groups, {dup_count} duplicate entries total.')
        for key, idxs in duplicates.items():
            display = key.replace('\x00', ' | ')
            print(f'Key: {display}')
            # show indices and first few lines for context
            first = seen[key]
            print(f'  Kept index: {first}')
            for i in idxs:
                print(f'  Duplicate index: {i}')
        return len(duplicates), dup_count, duplicates

    # Build new blocks list preserving first occurrences order
    keep_indices = sorted(seen.values())
    # Create map from original index -> block (with merged refs applied)
    new_block_map: Dict[int, List[str]] = {}
    for orig_idx in keep_indices:
        block = blocks[orig_idx]
        merged_refs = sorted(refs_map.get(orig_idx, set()))
        if merged_refs:
            new_block = replace_refs_in_block(block, merged_refs)
        else:
            # remove any existing duplicated #: inside this block? keep as is
            new_block = [ln for ln in block if not ln.startswith('#:')] + []
            # but if there were refs_map empty, we shouldn't remove existing #:; so instead keep original
            new_block = block
        new_block_map[orig_idx] = new_block

    # Build final sequence: iterate through blocks, write kept ones when reaching their index
    final_blocks: List[List[str]] = []
    seen_kept = set()
    for idx, block in enumerate(blocks):
        msgctxt = extract_quoted(block, 'msgctxt') or ''
        msgid = extract_quoted(block, 'msgid')
        if msgid is None:
            # header or stray block: keep as-is
            final_blocks.append(block)
            continue
        key = msgctxt + '\x00' + msgid
        first = seen[key]
        if first == idx:
            final_blocks.append(new_block_map.get(first, blocks[first]))
            seen_kept.add(first)
        else:
            # duplicate -> skip
            continue

    # write backup then write file
    if inplace:
        bak = path + backup_ext
        shutil.copy2(path, bak)
        print(f'Backup written to {bak}')
        with open(path, 'w', encoding='utf-8') as f:
            for block in final_blocks:
                f.write(block_to_text(block))
        print(f'Wrote deduplicated file to {path} ({len(final_blocks)} blocks, kept {unique_kept}).')
        return len(duplicates), dup_count, duplicates
    else:
        # Shouldn't get here since dry_run True case returned earlier
        raise RuntimeError('Non-dry run not inplace is unsupported')


def main():
    ap = argparse.ArgumentParser(description='Deduplicate .po by msgid (keep first, merge references)')
    ap.add_argument('po', help='path to .po file')
    ap.add_argument('-i', '--inplace', action='store_true', help='Edit file inplace (create backup)')
    ap.add_argument('--backup-ext', default='.bak', help='Backup extension for inplace edits')
    ap.add_argument('--run', action='store_true', help='Actually perform changes (without this flag it is a dry-run)')
    args = ap.parse_args()

    po = args.po
    if not os.path.exists(po):
        print('File not found:', po)
        raise SystemExit(1)

    if args.run:
        dedupe_po(po, inplace=args.inplace, backup_ext=args.backup_ext, dry_run=False)
    else:
        dedupe_po(po, inplace=False, dry_run=True)


if __name__ == '__main__':
    main()
