#!/usr/bin/env python3
"""Catch the two ways a Brindille tag silently misparses.

1. AN ODD NUMBER OF APOSTROPHES AFTER A `|` desynchronises the tokeniser. That
   is the whole rule, and it has nothing to do with SQL:

       {{:assign z="xay"}}
       {{$z|replace:"a":"l'un"}}          -> (empty)
       {{$z|replace:"'":"''"}}            -> (empty)
       {{"l'un"|replace:"a":"l'autre"}}   -> l'un"|replace:"a":"l'autre
       {{$z|replace:"a":"l'un l'autre"}}  -> xl'un l'autrey   (even: works)

   Two symptoms, depending on whether an apostrophe precedes the pipe: without
   one the value comes out EMPTY, with one the string swallows the rest of the
   tag and prints it literally. The empty one is the dangerous half — it raises
   nothing, so `|replace:"'":"''"` meant to quote a reference yields
   `WHERE ref = ''`: a valid query, zero rows, no error.

   A `{{#select}}` is a special case of this whenever its SQL concatenates with
   `||`, because that IS the modifier pipe: everything after it is read as
   modifier arguments, and a `-- l'un` comment further along is enough to make
   the count odd. SQL string literals are always paired, so they never change
   the parity — which is why, inside a SELECT, a comment is the only place an
   unpaired apostrophe can live.

2. A ';' IN A SQL COMMENT ends the query there. `Sections::selectStart` runs
   `strtok($sql, ';')` and hands what follows to the parameter parser:

       {{#select 1 AS x -- ; ici
           LIMIT 1}}                      -> Expecting '=' after 'ici'

   It needs two tokens after the ';' to raise: `-- ; ici` with nothing after it
   renders, and truncates the query silently instead.

Both name a place that is not the cause, which is what makes them expensive.
Measured on Paheko 1.3.22.1; both date from f06bcbc973 (2023-10-14), the
check-in that introduced `{{#select}}`, so neither is a regression.

Deliberately narrow: three neighbouring shapes are fine and common, and none of
them is reported —
  - the value being modified: `{{"l'un"|escape}}`
  - a tag parameter after the chain: `{{:link href="…"|args:$n label="l'an"}}`
  - a single-quoted argument, where they are the delimiters: `{{$x|or:'—'}}`
"""

import re
import sys

SELECT = re.compile(r"\{\{#select\b.*?\}\}", re.DOTALL)

# Any tag, Brindille comments excluded. Modifier arguments are what follows
# `|name`, as a run of `:`-separated values — a parameter after a space is NOT
# one of them, which is what keeps `label="l'an"` out.
TAG = re.compile(r"\{\{(?!\*)[:#/]?[^}]*?\}\}", re.DOTALL)
MODIFIER = re.compile(r"\|\s*\w+((?::(?:\"[^\"]*\"|'[^']*'|[^\s:|}]+))+)")
DOUBLE_QUOTED = re.compile(r'"([^"]*)"')

BREAKS = "breaks"
FRAGILE = "fragile"


def modifier_arguments(text: str):
    """Apostrophes inside the double-quoted arguments of a modifier."""
    seen = set()
    for tag in TAG.finditer(text):
        for mod in MODIFIER.finditer(tag.group(0)):
            quotes = sum(
                arg.group(1).count("'") for arg in DOUBLE_QUOTED.finditer(mod.group(1))
            )
            if not quotes:
                continue
            line = text.count("\n", 0, tag.start()) + 1
            if line in seen:
                continue
            seen.add(line)
            if quotes % 2:
                yield line, tag.group(0).split("\n")[0], BREAKS, (
                    f"{quotes} apostrophe(s) in a modifier argument — an odd count "
                    "renders empty, or swallows the rest of the tag"
                )
            else:
                yield line, tag.group(0).split("\n")[0], FRAGILE, (
                    f"{quotes} apostrophes in a modifier argument — even, so it works "
                    "today; adding or removing one word breaks it"
                )


def select_bodies(text: str):
    """The two faults reachable inside a {{#select}}.

    Both are positional, which is why counting per line is not enough: what
    matters is what LIES AFTER the ';' or the '|', to the end of the tag.
    """
    for tag in SELECT.finditer(text):
        body = tag.group(0)
        first_line = text.count("\n", 0, tag.start()) + 1

        # Both faults are decided by character position, not by line: a comment
        # can sit on the very line that carries the '|' or the ';'.
        pipe = body.find("|")
        at = 0
        after_pipe = None
        for offset, line in enumerate(body.split("\n")):
            code, sep, comment = line.partition("--")
            start = at + len(code) + len(sep)
            at += len(line) + 1
            if not sep:
                continue

            if ";" in comment:
                # The query is cut at this ';'. It raises only if two tokens
                # follow, which any real SQL after the comment provides; with
                # fewer, the only thing lost is the tail of the comment.
                cut = start + comment.index(";")
                if len(body[cut + 1 :].replace("}}", " ").split()) >= 2:
                    yield (
                        first_line + offset,
                        line,
                        BREAKS,
                        (
                            "';' in a SQL comment ends the query there — the rest "
                            "of the SELECT goes to the parameter parser"
                        ),
                    )

            if "'" in comment and pipe >= 0 and start + comment.index("'") > pipe:
                after_pipe = (first_line + offset, line)

        # An apostrophe only misparses once a '|' has put the tokeniser into
        # modifier territory, so the count that decides is the one after the
        # first pipe. Paired SQL literals never change a parity, which is why a
        # comment is the only place this can come from inside a SELECT.
        if after_pipe and body.count("'", pipe) % 2:
            yield (
                *after_pipe,
                BREAKS,
                (
                    f"{body.count(chr(39), pipe)} apostrophes after the '|' of this "
                    "{{#select}} — odd, so what follows is read as a modifier"
                ),
            )


def problems(text: str):
    return sorted(
        list(select_bodies(text)) + list(modifier_arguments(text)), key=lambda i: i[0]
    )


def main(paths: list[str]) -> int:
    breaks = fragile = 0
    for path in paths:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for lineno, line, severity, reason in problems(text):
            if severity == BREAKS:
                breaks += 1
            else:
                fragile += 1
            print(f"{path}:{lineno}: [{severity}] {reason}\n    {line.strip()}")
    if breaks or fragile:
        print(f"\n{breaks} breaking, {fragile} fragile.")
    return 1 if breaks or fragile else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
