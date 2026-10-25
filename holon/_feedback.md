# _feedback.md -- routing feedback (append-only, never edit or delete)

> Agent carrying out a task: when no sub-skill matches, when the sub-skill reached does not handle the task, or when one task needs several leaves, append one line below in the form
> `task sentence | path taken | outcome`
> `outcome` is one of: `miss`, `wrong -> <path actually needed>`, `multi`, `fallback -> <path found by reading descriptions after the words failed>`.
> Agent absorbing skills: handle these lines first in every absorption; append ` done` to each handled line.
