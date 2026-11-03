# Vault rules

Why: the graph must show how things relate. A date in a name, a note with no parent, and a log linking to everything each make it noise. These apply in a vault with `noteCheck` on, and the Stop hook blocks a note that breaks them.

## Shape

```
Home
 ├ Homey map ── Rules, Facts, Tools, Agents, system notes
 ├ <Area> map ── project ── decision, resource, spec
 └ Inbox notes, until sorted
Hidden from the graph: Daily/, Tasks/, System/, CLAUDE.md
```

## Every note

| Rule | Detail |
|---|---|
| Name | What it is, in plain words: `Harness inventory`. Never a date, time, or `Sample`, `Test`, `Temp` |
| `up` | Exactly one parent, as `up: "[[Parent]]"`. A property link counts in the graph |
| `created` | The date, as a property. Sort and show by this |
| `type`, `summary` | As the template has them |
| `tags` | Keywords as a list: the note type, the area, then the topic. Lowercase, one word or `nested/word`. They let the graph and search group notes |
| `aliases` | Other names people use for it, and any old name it had |
| Writing | Follow skill `obsidian-markdown`: properties, `[[wikilinks]]`, callouts, embeds. Load it before writing a note, also from Bash |
| Folder | The area it belongs to |

## Parents

| Note | `up` |
|---|---|
| Area map | `[[Home]]` |
| Project | Its area map |
| Decision, resource, spec | Its project, or the area map if it has none |
| Inbox note | `[[Home]]` until sorted |
| Finished plan or check | Keep `up`, move to `System/Archive/` |

## Links in the text
Wikilink a keyword the first time it names another note. Only where one note really depends on or explains another. Use `[[Note|shown words]]` to keep a sentence readable. The daily log links freely: it is hidden from the graph.

## Names that keep a date
| Folder | Why |
|---|---|
| `Daily/` | The date is the note |
| `Tasks/` | Must be unique; hidden from the graph |

## Do not
- Do not create sample, demo or test notes in a real vault. One exception: the bootstrap demo, when the user chose it; those notes carry the tag `demo` and are removed after.
- Do not add a second parent to make a link.
