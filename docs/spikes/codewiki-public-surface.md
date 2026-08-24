# CodeWiki Public-Surface Spike

- CodeWiki version: `codewiki 0.6.5`
- Probe repository commit: `f207b4f37b1375a9b9bf7fae0b89361c6e39aa86`
- Decision: `go`

## CLI observations

| Command | Exit | Machine-readable JSON |
|---|---:|---|
| `version` | 2 | no |
| `repos_add` | 0 | yes |
| `analyze` | 0 | yes |
| `repos_scan` | 0 | yes |
| `graph_search` | 0 | yes |
| `graph_explore` | 0 | yes |
| `package_version` | 0 | no |
| `graph_affected` | 0 | yes |
| `update` | 0 | yes |
| `graph_search_after_update` | 0 | yes |

## MCP fallback observations

MCP fallback was not required.

## Capability matrix

| Capability | Status | Evidence |
|---|---|---|
| `version` | `supported` | `bundle:codewiki_version` |
| `repository_registration` | `supported` | `cli:repos_add` |
| `full_index` | `supported` | `cli:analyze` |
| `repository_survey` | `supported` | `cli:repos_scan`, `cli:graph_search`, `cli:graph_explore`, `cli:graph_search_after_update` |
| `symbols` | `supported` | `cli:graph_explore`, `cli:graph_affected` |
| `imports` | `supported` | `cli:graph_explore` |
| `calls` | `supported` | `cli:graph_explore` |
| `source_references` | `supported` | `cli:graph_search`, `cli:graph_explore`, `cli:graph_search_after_update` |
| `topic_exploration` | `supported` | `cli:graph_explore` |
| `affected` | `supported` | `cli:graph_affected` |
| `incremental_update` | `supported` | `cli:update`, `cli:graph_search_after_update` |
| `bounded_machine_output` | `supported` | `cli:parseable-json` |

## Missing or ambiguous capabilities

None.

## Adapter recommendation

Proceed to the Fake Provider vertical slice using only the captured public-surface contract.
