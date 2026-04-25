#!/bin/bash
# ray: Wrapper for 'uv init' that configures the project to use the local ray mirror.

# Attempt to find the target directory from the arguments
TARGET_DIR="."
for arg in "$@"; do
  # The first argument that doesn't start with a hyphen is the path
  if [[ ! "$arg" == -* ]]; then
    TARGET_DIR="$arg"
    break
  fi
done

# Run the actual uv init command with all passed arguments
uv init "$@"

# If uv init succeeded, append the configuration
if [ $? -eq 0 ]; then
    TOML_FILE="$TARGET_DIR/pyproject.toml"
    
    if [ -f "$TOML_FILE" ]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            MARKER="darwin"
        else
            MARKER="linux"
        fi

        cat <<EOF >> "$TOML_FILE"

[[tool.uv.index]]
url="http://localhost:8080/simple/"
default=true

[tool.uv]
environments = [
    "sys_platform == '$MARKER'"
]
EOF
        echo "Successfully configured $TOML_FILE for local ray mirror ($MARKER)."
    else
        echo "Warning: Could not find pyproject.toml at $TOML_FILE"
    fi
else
    echo "uv init failed."
    exit 1
fi