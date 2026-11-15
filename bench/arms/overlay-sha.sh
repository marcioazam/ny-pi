#!/usr/bin/env bash
# overlay_sha DIR LIST: 16-hex hash of the files under DIR named by the overlay list LIST (comments and blank
# lines skipped). A listed path that does not exist is skipped, wherever it sits in the list.
overlay_sha() {
  (cd "$1" && grep -v -e '^#' -e '^$' "$2" | while read -r rel; do
    if [ -e "$rel" ]; then find -L "$rel" -type f -print0; fi
  done | sort -z | xargs -0 -r sha256sum | sha256sum | cut -c1-16)
}
