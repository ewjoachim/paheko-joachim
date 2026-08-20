#!/usr/bin/env python3
"""Catch the two SQL comments that break a Brindille {{#select}}.

Sections::selectStart does not parse SQL. It runs strtok($sql, ';') and hands
what follows to _parseArguments, whose tokeniser tracks string state by counting
apostrophes. A `--` comment is invisible to both.

1. A ';' in a comment ends the query there and sends the rest of the SELECT to
   the parameter parser:

       {{#select 1 AS x FROM t -- point-virgule ; ici
           WHERE id = :p LIMIT 1; :p=2}}
       -> Line 1: Expecting '=' after 'ici'

2. An ODD number of apostrophes across a tag's comments flips the string state
   for everything that follows, and some later token is then read as a modifier:

       -- Branche 2 : cheques recus en reglement d'une creance
       -> Line 56: Unknown modifier name: json_extract(ov.document, ...

   Parity is what matters, not the apostrophe: on the real _list.html query,
   1 and 3 apostrophes break, 2 render fine, twice each with the template cache
   cleared. Small probes do NOT reproduce it — a two-line SELECT with one
   apostrophe renders happily, which is how this trap got talked out of existence
   twice before being measured on the query that actually breaks.

Both errors name a place that is not the cause, which is what makes them
expensive.
"""

import re
import sys

SELECT = re.compile(r"\{\{#select\b.*?\}\}", re.DOTALL)


def problems(text: str):
    """Yield (line number within the file, offending line, reason)."""
    for tag in SELECT.finditer(text):
        first_line = text.count("\n", 0, tag.start()) + 1
        quotes = 0
        last_quoted = None
        for offset, line in enumerate(tag.group(0).split("\n")):
            _, sep, comment = line.partition("--")
            if not sep:
                continue
            if ";" in comment:
                yield first_line + offset, line, "';' in a SQL comment ends the query there"
            if "'" in comment:
                quotes += comment.count("'")
                last_quoted = (first_line + offset, line)
        if quotes % 2 and last_quoted:
            yield (
                *last_quoted,
                f"{quotes} apostrophe(s) in this {{{{#select}}}}'s comments — an odd "
                "count desynchronises the tokeniser",
            )


def main(paths: list[str]) -> int:
    found = 0
    for path in paths:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for lineno, line, reason in problems(text):
            found += 1
            print(f"{path}:{lineno}: {reason}\n    {line.strip()}")
    if found:
        print(f"\n{found} problem(s). Rephrase: no ';', and no lone apostrophe.")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
